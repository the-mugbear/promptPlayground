# tasks/case.py
# Single test case execution task and its helpers

import json
import logging
import traceback 
from datetime import datetime

from celery_app import celery 
from tasks.base import ContextTask 
from extensions import db 

from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestCase import TestCase
from models.model_TestExecution import TestExecution 
from models.model_TestRun import TestRun 
from models.model_Endpoints import Endpoint
from models.model_APIChain import APIChain

from services.common.templating_service import render_template_string
from services.common.http_request_service import execute_api_request
from services.chain_execution_service import APIChainExecutor, ChainExecutionError

from .helpers import emit_run_update, emit_execution_update, with_session, process_prompt_for_case
from sqlalchemy.orm import selectinload, joinedload 

logger = logging.getLogger(__name__) # Module-level logger

@celery.task(
    bind=True, # Gives access to 'self' (the task instance) for things like self.request.id
    acks_late=True, # Task acknowledged after completion/failure (good for reliability)
    base=ContextTask, # Uses your custom base task to ensure Flask app context is available
    name='tasks.execute_single_test_case', # Explicit Celery task name
    rate_limit='1/s' # Added rate limiting: 1 task of this type per second across all workers
)
@with_session 
def execute_single_test_case(
    self,                     # The Celery task instance itself
    test_run_attempt_id: int, # ID of the parent TestRunAttempt
    test_case_id: int,        # ID of the TestCase to execute
    endpoint_id: int,         # ID of the Endpoint to target (passed by orchestrator)
    test_run_id: int,         # ID of the parent TestRun (passed by orchestrator)
    sequence_num: int,        # Sequence number of this test case in the run
    iteration_num: int = 1    # Iteration number for this execution
):
    task_id = self.request.id
    logger.info(f"Task {task_id} - TC_ID:{test_case_id}, Seq:{sequence_num}, Iter:{iteration_num}, AttID:{test_run_attempt_id}: Starting.")
    
    payload_info_for_record = {"error": "Payload not generated due to an early task error."}
    execution_record = None
    actual_execution_started_at = datetime.utcnow()

    try:
        # --- Initial Data Fetching --- 
        attempt = db.session.get(TestRunAttempt, test_run_attempt_id)
        run = db.session.query(TestRun).options(
            selectinload(TestRun.filters),
            selectinload(TestRun.endpoint)
        ).get(test_run_id)
        case_obj = db.session.get(TestCase, test_case_id)
        endpoint_obj = run.endpoint if run else None
        
        # Derive the Endpoint object from the loaded 'run' object.
        # The 'endpoint_id' argument passed to this task is mainly for confirmation or direct use
        # if 'run.endpoint' was not available (though it should be with joinedload).
        endpoint_obj = run.endpoint if run else None 

        # --- Critical Object Validation ---
        # Ensure all necessary ORM objects were successfully fetched before proceeding.
        if not all([attempt, run, case_obj, endpoint_obj]):
            missing = []
            if not attempt: missing.append(f"AttemptID {test_run_attempt_id}")
            if not run: missing.append(f"RunID {test_run_id}")
            if not case_obj: missing.append(f"CaseID {test_case_id}")
            if not endpoint_obj: 
                missing.append(f"Endpoint (from RunID {test_run_id}, expected for EndpointID {endpoint_id})")
            
            err_msg = f"Missing critical data: {', '.join(missing)}."
            logger.error(f"Task {task_id}: {err_msg}")
            
            execution_record = create_error_record( 
                 test_run_attempt_id, test_case_id, sequence_num, iteration_num, ValueError(err_msg), 
                 payload_info_for_record, task_id
            )
            # This exception will be caught by the outer `except Exception as task_e` block,
            # which will then add the record to the session and proceed to finally.
            raise ValueError(err_msg) 

        # --- 1) Build the final prompt (only once) ---
        original_prompt = case_obj.prompt

        # Call the helper function from tasks.helpers to apply filters and transformations.
        final_prompt = process_prompt_for_case(
            original_prompt,
            list(run.filters),             # Pass the list of PromptFilter ORM objects
            run.run_transformations or []  # Pass the list of transformation config dicts (or empty list)
        )

        http_payload_str_for_request = "{}" # Default to empty JSON object string
        if endpoint_obj.payload_template:
            try:
                # 1. Define the context for rendering the Jinja2 template.
                #    This context will contain all variables your templates might need.
                render_context = {
                    "INJECT_PROMPT": final_prompt,
                    "MODEL_NAME": "gemma-3-12b-it" # USED FOR LOCAL TESTING ONLY
                }

                # 2. Use the templating service to render the entire payload string.
                #    This replaces the old, complex logic of recursively injecting the prompt.
                http_payload_str_for_request = render_template_string(
                    endpoint_obj.payload_template.template,
                    render_context
                )

                # 3. Parse the final rendered string to store as a dict in the execution record.
                #    This also serves as validation that the template rendered valid JSON.
                payload_info_for_record = json.loads(http_payload_str_for_request)

            except json.JSONDecodeError as e:
                # Catch JSON errors specifically if the template renders invalid JSON
                logger.error(f"Task {task_id}: Rendered payload is not valid JSON. Error: {e}. Template: '{endpoint_obj.http_payload}'", exc_info=True)
                raise # Re-raise to be caught by the main exception handler
            except Exception as e:
                # Catch any other errors during template rendering
                logger.error(f"Task {task_id}: Failed to build payload from template. Error: {e}. Template: '{endpoint_obj.http_payload}'", exc_info=True)
                raise # Re-raise to be caught by the main exception handler
        else:
            # The improved fallback logic creates a 'messages' array automatically
            logger.warning(f"Task {task_id}: Endpoint {endpoint_obj.id} has no http_payload. Falling back to default 'messages' array.")
            payload_dict = {
                "messages": [{"role": "user", "content": final_prompt}]
            }
            http_payload_str_for_request = json.dumps(payload_dict)
            payload_info_for_record = payload_dict
        
        # Prepare headers directly as a dictionary. No need to convert to a raw string.
        headers_dict = {h.key: h.value for h in (endpoint_obj.headers or [])}
        
        # Apply any run-specific header overrides (e.g., updated Authorization tokens)
        if run.header_overrides:
            logger.debug(f"Task {task_id}: Applying header overrides: {run.header_overrides}")
            headers_dict.update(run.header_overrides)
        logger.info(f"HTTP payload being sent: {http_payload_str_for_request}")

        # --- Debug Logging for Test Case Execution ---
        logger.debug(f"Task {task_id}: Detailed Request Info - Method: {endpoint_obj.method}, URL: {endpoint_obj.base_url}/{endpoint_obj.path}, Headers: {headers_dict}")
        logger.debug(f"Task {task_id}: Request Payload: {http_payload_str_for_request}")
        
        # Specific cookie debugging
        cookie_header = headers_dict.get('Cookie') or headers_dict.get('cookie')
        if cookie_header:
            logger.debug(f"Task {task_id}: Cookie header found: {cookie_header}")
        else:
            logger.debug(f"Task {task_id}: No cookie header found in headers")

        # --- 2) Make HTTP call ---
        # This nested try-except is specifically for handling errors from the HTTP request itself
        # or from processing its immediate response.
        try:
            # Construct full URL for debugging
            full_url = f"{endpoint_obj.base_url.rstrip('/')}/{endpoint_obj.path.lstrip('/')}"
            
            # Use the refactored service function. Note the cleaner arguments.
            resp = execute_api_request(
                method=endpoint_obj.method,
                hostname_url=endpoint_obj.base_url,
                endpoint_path=endpoint_obj.path,
                raw_headers_or_dict=headers_dict,
                http_payload_as_string=http_payload_str_for_request
            )
            status_code = resp.get("status_code")
            body = resp.get("response_body")     
            error_msg_http = resp.get("error_message")
            
            # --- Debug Logging for Response ---
            logger.debug(f"Task {task_id}: Response - Status: {status_code}, Headers: {resp.get('response_headers', {})}")
            logger.debug(f"Task {task_id}: Response Body (first 500 chars): {str(body)[:500]}")
            if error_msg_http:
                logger.debug(f"Task {task_id}: HTTP Error: {error_msg_http}") 

            # Collect detailed request information for debugging
            request_details = {
                'method': endpoint_obj.method,
                'full_url': full_url,
                'headers_sent': resp.get("request_headers_sent", headers_dict),
                'cookies_sent': resp.get("request_cookies_sent", {}),
                'headers_with_cookies': resp.get("request_headers_with_cookies", headers_dict),
                'response_headers': resp.get("response_headers", {}),
                'request_successful': status_code is not None,
                'error_type': None,
                'error_context': {}
            }
            
            # Enhanced cookie debugging logging
            cookies_sent = resp.get("request_cookies_sent", {})
            if cookies_sent:
                logger.debug(f"Task {task_id}: Cookies successfully extracted and sent: {cookies_sent}")
            elif cookie_header:
                logger.warning(f"Task {task_id}: Cookie header was present but no cookies were extracted: {cookie_header}")

            # Determine error message for the TestExecution record based on HTTP outcome.
            if error_msg_http and status_code is None: # E.g. connection error, ReadTimeout
                 error_msg_for_record = error_msg_http
                 request_details['error_type'] = 'connection_error'
                 request_details['error_context'] = {'original_error': error_msg_http}
            elif status_code and not (200 <= status_code < 300): # HTTP error status (4xx, 5xx)
                 error_msg_for_record = f"HTTP Error {status_code}. Response: {str(body)[:200]}" # Include part of response
                 request_details['error_type'] = 'http_error'
                 request_details['error_context'] = {'status_code': status_code, 'response_preview': str(body)[:200]}
            else: # HTTP success or no specific error to log beyond body/status_code
                 error_msg_for_record = None 
            
            # Determine disposition (pass/fail/error) for the TestExecution.
            disposition = (
                "pass" if status_code and 200 <= status_code < 300 else
                "fail" if status_code else # Includes non-2xx codes
                "error" # For when status_code is None (e.g., connection error, timeout)
            )
            if disposition == "error" and not error_msg_for_record: # General fallback for error status
                error_msg_for_record = "Request failed, no status code or specific connection error."
                request_details['error_type'] = 'unknown_error'

            # --- 3) Create TestExecution record for successful or failed HTTP call ---
            # Uses your create_execution_record helper.
            # Pass payload_info_for_record (the DICT) for request_payload (JSONB).
            execution_record = create_execution_record(
                attempt, case_obj, sequence_num, iteration_num,
                payload_info_for_record, 
                status_code, body, error_msg_for_record, 
                actual_execution_started_at,
                processed_prompt_str=final_prompt,
                request_details=request_details
            )

        except Exception as http_e: # Catches errors from execute_api_request or subsequent logic within this try
            logger.error(f"Task {task_id}: HTTP call or response processing failed for TC_ID:{case_obj.id if 'case_obj' in locals() else test_case_id}: {http_e}", exc_info=True)
            # payload_info_for_record will contain the actual payload if generated, or the default error dict.
            execution_record = create_error_record(
                test_run_attempt_id, test_case_id, sequence_num, iteration_num, http_e, 
                payload_info_for_record
            )
            # create_error_record helper sets its own started_at/finished_at timestamps.

    except Exception as task_e: # Catches any preceding errors (data fetch, prompt processing, initial setup)
        logger.error(f"Task {task_id}: Broader error for TC_ID:{test_case_id}: {task_e}", exc_info=True)
        # payload_info_for_record will be the default error payload if task_e occurred very early.
        execution_record = create_error_record(
            test_run_attempt_id, test_case_id, sequence_num, iteration_num, task_e,
            payload_info_for_record
        )

    finally: # This block will always execute, ensuring record persistence and updates.
        if execution_record:
            db.session.add(execution_record)

            # --- Debugging logs for test_run_id (can be removed after confirming type) ---
            logger.info(f"Task {task_id}: Attempting to update progress for TestRun ID: {test_run_id}")
            logger.info(f"Task {task_id}: Type of test_run_id before update: {type(test_run_id)}")
            # --- End Debugging ---

            # --- 4) Atomically increment TestRun.progress_current by 1 ---
            if isinstance(test_run_id, int): # Safety check for test_run_id type
                db.session.query(TestRun).filter_by(id=test_run_id).update(
                    {TestRun.progress_current: TestRun.progress_current + 1},
                    synchronize_session=False # Important for concurrent updates by multiple tasks
                )
            else:
                logger.error(f"Task {task_id}: Invalid type for test_run_id: {type(test_run_id)}. Skipping progress update.")
            
            # Re-fetch 'run' and 'attempt' to ensure they have the latest data for emits,
            # especially after the progress update and if an early error might have affected their state in this scope.
            run_for_emit = db.session.get(TestRun, test_run_id) 
            attempt_for_emit = db.session.get(TestRunAttempt, test_run_attempt_id)

            if attempt_for_emit and run_for_emit and execution_record: # Ensure all are present for emitting
                # --- 5a) Emit execution_result_update ---
                emit_execution_update(attempt_for_emit, execution_record)
                # --- 5b) Emit progress_update ---
                emit_run_update(test_run_id, 'progress_update', run_for_emit.get_status_data())
            else:
                logger.error(f"Task {task_id}: Could not emit updates for TC_ID:{test_case_id}, missing run/attempt/record for emit after record processing.")
        else:
            # This case might occur if an error happens before any execution_record is assigned in the try blocks,
            # though the broad try/except aims to always create one.
            logger.error(f"Task {task_id}: No execution_record was created for TC_ID:{test_case_id}. Cannot update progress or emit.")

    # Return status and ID of the execution record.
    return {'status': 'PROCESSED', 'execution_id': execution_record.id if execution_record else None}

# --- Helper Functions ---
def create_execution_record(attempt, case, seq, iteration_num, payload_dict, status_code, body, error_msg, started_at_time, processed_prompt_str, request_details=None):
    disposition = (
        "pass" if status_code and 200 <= status_code < 300 else
        "fail" if status_code else # Includes non-2xx codes
        "error"  # For cases where status_code is None (e.g., connection error, timeout)
    )
    
    # Calculate request duration if timing info is available
    duration_ms = None
    if started_at_time:
        duration_ms = int((datetime.utcnow() - started_at_time).total_seconds() * 1000)
    
    execution = TestExecution(
        test_run_attempt_id=attempt.id,
        test_case_id=case.id,
        sequence=seq,
        iteration=iteration_num or 1,  # Default to 1 if None
        request_payload=payload_dict, # Store the Python dictionary directly (SQLAlchemy handles for JSONB)
        response_data=str(body) if body is not None else None, # Ensure body is stored as string
        status_code=status_code,
        error_message=error_msg,
        status=disposition,
        started_at=started_at_time,  # Use the accurately captured start time
        finished_at=datetime.utcnow(),
        processed_prompt=processed_prompt_str,
        request_duration_ms=duration_ms
    )
    
    # Add enhanced debugging information if provided
    if request_details:
        execution.request_headers = request_details.get('headers_sent')
        execution.request_url = request_details.get('full_url')
        execution.request_method = request_details.get('method')
        execution.response_headers = request_details.get('response_headers')
        
        # Store structured error details for better debugging
        error_details = {}
        if error_msg and request_details.get('error_type'):
            error_details.update({
                'error_type': request_details.get('error_type'),
                'error_context': request_details.get('error_context', {}),
                'request_sent': request_details.get('request_successful', False)
            })
        
        # Add cookie debugging information
        cookies_sent = request_details.get('cookies_sent', {})
        headers_with_cookies = request_details.get('headers_with_cookies', {})
        if cookies_sent or headers_with_cookies:
            error_details.update({
                'cookies_sent': cookies_sent,
                'headers_with_cookies': headers_with_cookies,
                'cookie_processing_success': bool(cookies_sent) if headers_with_cookies.get('Cookie') else None
            })
        
        if error_details:
            execution.error_details = error_details
    
    return execution

def create_error_record(attempt_id, case_id, sequence_num, iteration_num, error_exception, payload_dict, processed_prompt_str=None):
    err_detail = ( # Format a detailed error message including traceback
        f"Exception {type(error_exception).__name__}: {error_exception}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )
    return TestExecution(
        test_run_attempt_id=attempt_id,
        test_case_id=case_id,
        sequence=sequence_num,
        iteration=iteration_num or 1,  # Default to 1 if None
        request_payload=payload_dict, # Store the Python dictionary (original payload or default error dict)
        response_data=None, # No response data in case of such errors
        status_code=None,   # No status code
        error_message=err_detail, # Store the detailed error and traceback
        status="error", # Explicitly mark status as 'error'
        processed_prompt=processed_prompt_str, 
        started_at=datetime.utcnow(), # Timestamp when this error record is created
        finished_at=datetime.utcnow()
    )


@celery.task(
    bind=True,
    acks_late=True,
    base=ContextTask,
    name='tasks.execute_single_test_case_chain',
    rate_limit='1/s'
)
@with_session
def execute_single_test_case_chain(
    self,
    test_run_attempt_id: int,
    test_case_id: int,
    chain_id: int,
    test_run_id: int,
    sequence_num: int,
    iteration_num: int = 1
):
    """
    Execute a single test case against a chain instead of an endpoint.
    This injects the test case prompt into the chain execution and records results.
    """
    task_id = self.request.id
    logger.info(f"Chain Task {task_id} - TC_ID:{test_case_id}, Seq:{sequence_num}, Iter:{iteration_num}, AttID:{test_run_attempt_id}: Starting chain execution.")
    
    payload_info_for_record = {"error": "Chain execution not started due to early task error."}
    execution_record = None
    actual_execution_started_at = datetime.utcnow()

    try:
        # --- Initial Data Fetching ---
        attempt = db.session.get(TestRunAttempt, test_run_attempt_id)
        run = db.session.query(TestRun).options(
            selectinload(TestRun.filters),
            selectinload(TestRun.chain)
        ).get(test_run_id)
        case_obj = db.session.get(TestCase, test_case_id)
        chain_obj = run.chain if run else None

        # --- Critical Object Validation ---
        if not all([attempt, run, case_obj, chain_obj]):
            missing = []
            if not attempt: missing.append(f"AttemptID {test_run_attempt_id}")
            if not run: missing.append(f"RunID {test_run_id}")
            if not case_obj: missing.append(f"CaseID {test_case_id}")
            if not chain_obj: 
                missing.append(f"Chain (from RunID {test_run_id}, expected for ChainID {chain_id})")
            
            err_msg = f"Missing critical data for chain execution: {', '.join(missing)}."
            logger.error(f"Chain Task {task_id}: {err_msg}")
            
            execution_record = create_error_record( 
                 test_run_attempt_id, test_case_id, sequence_num, iteration_num, ValueError(err_msg), 
                 payload_info_for_record, task_id
            )
            raise ValueError(err_msg)

        # --- Process the prompt with filters and transformations ---
        original_prompt = case_obj.prompt
        final_prompt = process_prompt_for_case(
            original_prompt,
            list(run.filters),
            run.run_transformations or []
        )

        # --- Execute Chain with Test Case Context ---
        try:
            # Create initial context for chain execution with the test case prompt
            initial_context = {
                "INJECT_PROMPT": final_prompt,
                "TEST_CASE_ID": test_case_id,
                "ITERATION": iteration_num
            }
            
            # Find the first step that contains {{INJECT_PROMPT}} in payload or headers
            # to determine where to inject the test case prompt
            chain_steps = sorted(chain_obj.steps, key=lambda s: s.step_order)
            injection_step = None
            
            for step in chain_steps:
                step_payload = step.payload or ""
                step_headers = step.headers or ""
                if "{{INJECT_PROMPT}}" in step_payload or "{{INJECT_PROMPT}}" in step_headers:
                    injection_step = step
                    break
            
            if not injection_step:
                logger.warning(f"Chain Task {task_id}: No step found with {{{{INJECT_PROMPT}}}} template. Chain may not use test case prompt.")
            
            # Execute the chain using the chain execution service
            logger.info(f"Chain Task {task_id}: Executing chain '{chain_obj.name}' (ID: {chain_obj.id}) with initial context: {initial_context}")
            
            # Apply any run-specific header overrides to the chain context
            if run.header_overrides:
                logger.debug(f"Chain Task {task_id}: Applying header overrides to chain context: {run.header_overrides}")
                initial_context.update(run.header_overrides)
            
            executor = APIChainExecutor()
            chain_result = executor.execute_chain(chain_obj.id, initial_context=initial_context)
            
            # Extract information for the execution record
            final_context = chain_result.get("final_context", {})
            step_results = chain_result.get("step_results", [])
            
            logger.info(f"Chain Task {task_id}: Chain execution completed. Steps executed: {len(step_results)}, Final context keys: {list(final_context.keys())}")
            
            # Determine overall chain execution status
            chain_success = all(step.get("status") == "success" for step in step_results)
            failed_steps = [step for step in step_results if step.get("status") != "success"]
            
            # Create a summary of the chain execution for the record
            chain_summary = {
                "chain_id": chain_obj.id,
                "chain_name": chain_obj.name,
                "steps_executed": len(step_results),
                "successful_steps": len(step_results) - len(failed_steps),
                "failed_steps": len(failed_steps),
                "final_context": final_context,
                "step_results": step_results,
                "injection_step_order": injection_step.step_order if injection_step else None,
                "test_case_prompt": final_prompt[:200] + "..." if len(final_prompt) > 200 else final_prompt
            }
            
            payload_info_for_record = chain_summary
            
            # Determine status code and response based on final step
            final_step_result = step_results[-1] if step_results else {}
            status_code = final_step_result.get("response_status_code")
            
            # Combine all step responses for the response data
            combined_response = {
                "chain_execution_summary": chain_summary,
                "all_step_results": step_results
            }
            
            if chain_success:
                error_msg_for_record = None
                logger.info(f"Chain Task {task_id}: All {len(step_results)} steps completed successfully")
            else:
                error_details = []
                for step in failed_steps:
                    step_order = step.get("step_order", "unknown")
                    step_msg = step.get("message", "Unknown error")
                    error_details.append(f"Step {step_order}: {step_msg}")
                error_msg_for_record = f"Chain execution failed - {len(failed_steps)}/{len(step_results)} steps failed. Details: " + "; ".join(error_details)
                logger.error(f"Chain Task {task_id}: Chain execution failed with {len(failed_steps)} failed steps: {error_msg_for_record}")
            disposition = "pass" if chain_success else "fail"
            
            # Prepare debugging information for chain execution
            request_details = {
                'method': 'CHAIN',
                'full_url': f"Chain: {chain_obj.name} (ID: {chain_obj.id})",
                'headers_sent': {'chain_steps': len(chain_steps), 'injection_step': injection_step.step_order if injection_step else None},
                'response_headers': {'final_context_keys': list(final_context.keys())},
                'request_successful': chain_success,
                'error_type': 'chain_execution_error' if not chain_success else None,
                'error_context': {'failed_steps': len(failed_steps), 'total_steps': len(step_results)} if not chain_success else {}
            }
            
            # Create execution record for successful chain execution
            execution_record = create_execution_record(
                attempt, case_obj, sequence_num, iteration_num,
                payload_info_for_record,
                status_code, json.dumps(combined_response), error_msg_for_record,
                actual_execution_started_at,
                processed_prompt_str=final_prompt,
                request_details=request_details
            )
            
        except ChainExecutionError as chain_e:
            logger.error(f"Chain Task {task_id}: Chain execution failed for TC_ID:{case_obj.id}: {chain_e}", exc_info=True)
            execution_record = create_error_record(
                test_run_attempt_id, test_case_id, sequence_num, iteration_num, chain_e,
                payload_info_for_record, final_prompt
            )
        except Exception as chain_e:
            logger.error(f"Chain Task {task_id}: Unexpected error during chain execution for TC_ID:{case_obj.id}: {chain_e}", exc_info=True)
            execution_record = create_error_record(
                test_run_attempt_id, test_case_id, sequence_num, iteration_num, chain_e,
                payload_info_for_record, final_prompt
            )

    except Exception as task_e:
        logger.error(f"Chain Task {task_id}: Broader error for TC_ID:{test_case_id}: {task_e}", exc_info=True)
        execution_record = create_error_record(
            test_run_attempt_id, test_case_id, sequence_num, iteration_num, task_e,
            payload_info_for_record
        )

    finally:
        if execution_record:
            db.session.add(execution_record)

            logger.info(f"Chain Task {task_id}: Attempting to update progress for TestRun ID: {test_run_id}")
            
            # Atomically increment TestRun.progress_current by 1
            if isinstance(test_run_id, int):
                db.session.query(TestRun).filter_by(id=test_run_id).update(
                    {TestRun.progress_current: TestRun.progress_current + 1},
                    synchronize_session=False
                )
            else:
                logger.error(f"Chain Task {task_id}: Invalid type for test_run_id: {type(test_run_id)}. Skipping progress update.")
            
            # Re-fetch objects for emits
            run_for_emit = db.session.get(TestRun, test_run_id)
            attempt_for_emit = db.session.get(TestRunAttempt, test_run_attempt_id)

            if attempt_for_emit and run_for_emit and execution_record:
                emit_execution_update(attempt_for_emit, execution_record)
                emit_run_update(test_run_id, 'progress_update', run_for_emit.get_status_data())
            else:
                logger.error(f"Chain Task {task_id}: Could not emit updates for TC_ID:{test_case_id}, missing run/attempt/record for emit after record processing.")
        else:
            logger.error(f"Chain Task {task_id}: No execution_record was created for TC_ID:{test_case_id}. Cannot update progress or emit.")

    return {'status': 'PROCESSED', 'execution_id': execution_record.id if execution_record else None}