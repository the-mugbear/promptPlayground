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

from services.common.templating_service import render_template_string
from services.common.http_request_service import execute_api_request

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
    sequence_num: int         # Sequence number of this test case in the run
):
    task_id = self.request.id
    logger.info(f"Task {task_id} - TC_ID:{test_case_id}, Seq:{sequence_num}, AttID:{test_run_attempt_id}: Starting.")
    
    payload_info_for_record = {"error": "Payload not generated due to an early task error."}
    execution_record = None
    actual_execution_started_at = datetime.utcnow()

    try:
        # --- Initial Data Fetching --- 
        attempt = db.session.get(TestRunAttempt, test_run_attempt_id)
        run = db.session.query(TestRun).options(
            selectinload(TestRun.filters),
            joinedload(TestRun.endpoint)
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
                 test_run_attempt_id, test_case_id, sequence_num, ValueError(err_msg), 
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
        logger.info(f"HTTP payload being sent: {http_payload_str_for_request}")

        # --- 2) Make HTTP call ---
        # This nested try-except is specifically for handling errors from the HTTP request itself
        # or from processing its immediate response.
        try:
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

            # Determine error message for the TestExecution record based on HTTP outcome.
            if error_msg_http and status_code is None: # E.g. connection error, ReadTimeout
                 error_msg_for_record = error_msg_http
            elif status_code and not (200 <= status_code < 300): # HTTP error status (4xx, 5xx)
                 error_msg_for_record = f"HTTP Error {status_code}. Response: {str(body)[:200]}" # Include part of response
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

            # --- 3) Create TestExecution record for successful or failed HTTP call ---
            # Uses your create_execution_record helper.
            # Pass payload_info_for_record (the DICT) for request_payload (JSONB).
            execution_record = create_execution_record(
                attempt, case_obj, sequence_num, 
                payload_info_for_record, 
                status_code, body, error_msg_for_record, 
                actual_execution_started_at,
                processed_prompt_str=final_prompt 
            )

        except Exception as http_e: # Catches errors from execute_api_request or subsequent logic within this try
            logger.error(f"Task {task_id}: HTTP call or response processing failed for TC_ID:{case_obj.id if 'case_obj' in locals() else test_case_id}: {http_e}", exc_info=True)
            # payload_info_for_record will contain the actual payload if generated, or the default error dict.
            execution_record = create_error_record(
                test_run_attempt_id, test_case_id, sequence_num, http_e, 
                payload_info_for_record
            )
            # create_error_record helper sets its own started_at/finished_at timestamps.

    except Exception as task_e: # Catches any preceding errors (data fetch, prompt processing, initial setup)
        logger.error(f"Task {task_id}: Broader error for TC_ID:{test_case_id}: {task_e}", exc_info=True)
        # payload_info_for_record will be the default error payload if task_e occurred very early.
        execution_record = create_error_record(
            test_run_attempt_id, test_case_id, sequence_num, task_e,
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
def create_execution_record(attempt, case, seq, payload_dict, status_code, body, error_msg, started_at_time,processed_prompt_str):
    disposition = (
        "pass" if status_code and 200 <= status_code < 300 else
        "fail" if status_code else # Includes non-2xx codes
        "error"  # For cases where status_code is None (e.g., connection error, timeout)
    )
    return TestExecution(
        test_run_attempt_id=attempt.id,
        test_case_id=case.id,
        sequence=seq,
        request_payload=payload_dict, # Store the Python dictionary directly (SQLAlchemy handles for JSONB)
        response_data=str(body) if body is not None else None, # Ensure body is stored as string
        status_code=status_code,
        error_message=error_msg,
        status=disposition,
        started_at=started_at_time,  # Use the accurately captured start time
        finished_at=datetime.utcnow(),
        processed_prompt=processed_prompt_str
    )

def create_error_record(attempt_id, case_id, sequence_num, error_exception, payload_dict, processed_prompt_str=None):
    err_detail = ( # Format a detailed error message including traceback
        f"Exception {type(error_exception).__name__}: {error_exception}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )
    return TestExecution(
        test_run_attempt_id=attempt_id,
        test_case_id=case_id,
        sequence=sequence_num,
        request_payload=payload_dict, # Store the Python dictionary (original payload or default error dict)
        response_data=None, # No response data in case of such errors
        status_code=None,   # No status code
        error_message=err_detail, # Store the detailed error and traceback
        status="error", # Explicitly mark status as 'error'
        processed_prompt=processed_prompt_str, 
        started_at=datetime.utcnow(), # Timestamp when this error record is created
        finished_at=datetime.utcnow()
    )