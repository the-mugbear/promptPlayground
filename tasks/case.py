# tasks/case.py
# Single test case execution task and its helpers

import json # Used for handling JSON data (dumps for strings, loads for parsing)
import logging # For logging task activity and errors
import traceback # For formatting exception tracebacks in error records
from datetime import datetime # For accurately timestamping events

from celery_app import celery # Your Celery application instance
from tasks.base import ContextTask # Your custom base task for Flask app context
from extensions import db # Your SQLAlchemy instance for database operations
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestCase import TestCase
# Endpoint model is referenced via run.endpoint, direct import might be optional
# from models.model_Endpoints import Endpoint 
from models.model_TestExecution import TestExecution # To create execution records
from models.model_TestRun import TestRun # To update progress and get run-level info
from models.model_Endpoints import Endpoint
from services.common.http_request_service import replay_post_request # Your function for making HTTP calls
# Helper functions for emitting SocketIO updates, SQLAlchemy session management, and prompt processing
from .helpers import emit_run_update, emit_execution_update, with_session, process_prompt_for_case, _recursively_inject_prompt
from sqlalchemy.orm import selectinload, joinedload # For optimizing database queries

logger = logging.getLogger(__name__) # Module-level logger

@celery.task(
    bind=True, # Gives access to 'self' (the task instance) for things like self.request.id
    acks_late=True, # Task acknowledged after completion/failure (good for reliability)
    base=ContextTask, # Uses your custom base task to ensure Flask app context is available
    name='tasks.execute_single_test_case', # Explicit Celery task name
    rate_limit='1/s' # Added rate limiting: 1 task of this type per second across all workers
)
@with_session # Decorator to manage SQLAlchemy session lifecycle (commit/rollback/remove)
def execute_single_test_case(
    self, # The Celery task instance itself
    test_run_attempt_id: int, # ID of the parent TestRunAttempt
    test_case_id: int,        # ID of the TestCase to execute
    endpoint_id: int,         # ID of the Endpoint to target (passed by orchestrator)
    test_run_id: int,         # ID of the parent TestRun (passed by orchestrator)
    sequence_num: int         # Sequence number of this test case in the run
):
    task_id = self.request.id # Celery's unique ID for this specific task execution
    logger.info(f"Task {task_id} - TC_ID:{test_case_id}, Seq:{sequence_num}, AttID:{test_run_attempt_id}: Starting.")

    # Initialize variables for robust error reporting and record keeping.
    # payload_info_for_record will hold the payload dictionary (or an error default)
    # to be stored in the TestExecution record.
    payload_info_for_record = {"error": "Payload not generated due to an early task error."}
    execution_record = None # Will hold the TestExecution ORM object to be saved.
    # Capture a more accurate start time for this specific task execution.
    actual_execution_started_at = datetime.utcnow() 

    try:
        # --- Initial Data Fetching ---
        # Fetch the TestRunAttempt which links to the TestRun.
        attempt = db.session.get(TestRunAttempt, test_run_attempt_id)
        # Fetch the TestRun, eagerly loading its related filters and endpoint.
        # 'test_run_id' is passed by the orchestrator.
        run = db.session.query(TestRun).options(
            selectinload(TestRun.filters),    # Eagerly load the 'filters' relationship
            joinedload(TestRun.endpoint)    # Eagerly load the 'endpoint' relationship
        ).get(test_run_id)
        # Fetch the specific TestCase object.
        case_obj = db.session.get(TestCase, test_case_id)
        
        # Derive the Endpoint object from the loaded 'run' object.
        # The 'endpoint_id' argument passed to this task is mainly for confirmation or direct use
        # if 'run.endpoint' was not available (though it should be with joinedload).
        endpoint_obj = run.endpoint if run else None 

        # --- Critical Object Validation ---
        # Ensure all necessary ORM objects were successfully fetched before proceeding.
        if not all([attempt, run, case_obj, endpoint_obj]):
            missing = [] # List to accumulate names of missing objects
            if not attempt: missing.append(f"AttemptID {test_run_attempt_id}")
            if not run: missing.append(f"RunID {test_run_id}")
            if not case_obj: missing.append(f"CaseID {test_case_id}")
            if not endpoint_obj: 
                missing.append(f"Endpoint (from RunID {test_run_id}, expected for EndpointID {endpoint_id})")
            
            err_msg = f"Missing critical data: {', '.join(missing)}."
            logger.error(f"Task {task_id}: {err_msg}")
            
            # Use your create_error_record helper to create a TestExecution record for this setup failure.
            # payload_info_for_record will still contain the default error message.
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

        payload_dict = None 
        if endpoint_obj.http_payload: # Check if the endpoint has an http_payload template string
            try:
                # Step 1: Parse the original template string (which should be valid JSON) into a Python dict
                template_as_dict = json.loads(endpoint_obj.http_payload)
                
                # Step 2: Recursively find and replace the placeholder
                # The _recursively_inject_prompt function will modify template_as_dict in place.
                prompt_injected = _recursively_inject_prompt(
                    template_as_dict, 
                    "{{INJECT_PROMPT}}", # The placeholder string to find
                    final_prompt         # The actual processed prompt string to inject
                )
                
                if not prompt_injected:
                    logger.warning(f"Task {task_id}: Placeholder '{{INJECT_PROMPT}}' not found anywhere in the parsed http_payload template for TC_ID:{case_obj.id}. The prompt was not injected.")
                # If other placeholders like {{model}} also need replacement,
                # you could call _recursively_inject_prompt again for them,
                # or make it handle a dictionary of replacements.

                payload_dict = template_as_dict # template_as_dict is now modified (or not, if placeholder wasn't found)

            except json.JSONDecodeError as jde:
                logger.error(f"Task {task_id}: Failed to parse http_payload template as JSON. Error: {jde}. Template: '{endpoint_obj.http_payload}'")
                raise # Re-raise to be caught by the main 'except Exception as task_e'
            except Exception as e_build: # Catch other potential errors during dict manipulation
                logger.error(f"Task {task_id}: Error processing http_payload template dictionary: {e_build}", exc_info=True)
                raise
        else:
            # Fallback if no http_payload template is defined on the endpoint.
            logger.warning(f"Task {task_id}: Endpoint {endpoint_obj.id} has no http_payload. Using default {{'prompt': ...}}.")
            payload_dict = {"prompt": final_prompt}
        
        # Update payload_info_for_record with the actual payload dictionary.
        # This dictionary is suitable for storing in TestExecution.request_payload (JSONB).
        payload_info_for_record = payload_dict 

        logger.info(f"Task {task_id}: Making POST to {endpoint_obj.hostname}{endpoint_obj.endpoint} for TC_ID:{case_obj.id}")
        
        # headers_dict is correctly created as a Python dictionary:
        headers_dict = {h.key: h.value for h in (endpoint_obj.headers or [])}
        
        # Convert the headers_dict to a multi-line string format
        # that parse_raw_headers_with_cookies expects.
        raw_headers_string_for_request = "\n".join(f"{k}: {v}" for k, v in headers_dict.items())
        
        # Convert payload_dict to a JSON string because replay_post_request expects a string
        # for its internal json.loads() call.
        http_payload_str_for_request = json.dumps(payload_dict)

        # --- 2) Make HTTP call ---
        # This nested try-except is specifically for handling errors from the HTTP request itself
        # or from processing its immediate response.
        try:
            resp = replay_post_request(
                endpoint_obj.hostname,
                endpoint_obj.endpoint,
                http_payload_str_for_request, # Pass the JSON STRING to replay_post_request
                raw_headers_string_for_request,
                timeout=10                    # Set a timeout for the request
            )
            status_code = resp.get("status_code")
            body = resp.get("response_text") # Raw text or pretty-printed JSON string from replay_post_request
            error_msg_http = resp.get("error") # Error message from replay_post_request (e.g., connection error)

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

        except Exception as http_e: # Catches errors from replay_post_request or subsequent logic within this try
            logger.error(f"Task {task_id}: HTTP call or response processing failed for TC_ID:{case_obj.id if 'case_obj' in locals() else test_case_id}: {http_e}", exc_info=True)
            # Use your create_error_record helper.
            # payload_info_for_record will contain the actual payload if generated, or the default error dict.
            execution_record = create_error_record(
                test_run_attempt_id, test_case_id, sequence_num, http_e, 
                payload_info_for_record
            )
            # create_error_record helper sets its own started_at/finished_at timestamps.

    except Exception as task_e: # Catches any preceding errors (data fetch, prompt processing, initial setup)
        logger.error(f"Task {task_id}: Broader error for TC_ID:{test_case_id}: {task_e}", exc_info=True)
        # Use your create_error_record helper.
        # payload_info_for_record will be the default error payload if task_e occurred very early.
        execution_record = create_error_record(
            test_run_attempt_id, test_case_id, sequence_num, task_e,
            payload_info_for_record
        )

    finally: # This block will always execute, ensuring record persistence and updates.
        if execution_record:
            db.session.add(execution_record)
            # The @with_session decorator handles db.session.commit() or rollback() & db.session.remove()

            # --- Debugging logs for test_run_id (can be removed after confirming type) ---
            logger.info(f"Task {task_id}: Attempting to update progress for TestRun ID: {test_run_id}")
            logger.info(f"Task {task_id}: Type of test_run_id before update: {type(test_run_id)}")
            # --- End Debugging ---

            # --- 4) Atomically increment TestRun.progress_current by 1 ---
            # This IS needed for the "simple group diagnostic" test where handle_batch_completion is not used.
            # It should only run if an execution_record was successfully created (either a success or error record).
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


# --- Helper Functions (as you provided in your file) ---
# These helpers are defined locally in this file.

def fetch_objects(attempt_id, case_id, endpoint_id):
    # This helper is NOT currently used by the main execute_single_test_case function above.
    # The main function performs direct fetches. Consider refactoring to use this or removing it.
    attempt = db.session.get(TestRunAttempt, attempt_id)
    case = db.session.get(TestCase, case_id)
    endpoint = db.session.get(Endpoint, endpoint_id) 
    missing = [name for name, obj in (('Attempt', attempt), ('Case', case), ('Endpoint', endpoint)) if obj is None]
    if missing:
        raise ValueError(f"Missing objects: {', '.join(missing)}")
    return attempt, case, endpoint

def build_payload(template, prompt):
    # This helper is NOT currently used by the main execute_single_test_case function above.
    # The main function has its own, more robust, inline logic for payload creation.
    # This helper also uses a different placeholder "{{INJECT_PROMPT}}" and a potentially risky
    # string manipulation `json.dumps(prompt)[1:-1]`. It's recommended to use the inline logic
    # from the main task or adapt this helper significantly if it's to be used.
    if not template:
        return json.dumps({"prompt": prompt}) # Returns a JSON string. Main task works with dicts then dumps.
    injected = json.dumps(prompt)[1:-1] # Strips quotes, can be problematic.
    if "{{INJECT_PROMPT}}" in template: # Different placeholder.
        return template.replace("{{INJECT_PROMPT}}", injected)
    raise ValueError("Payload template missing placeholder")

def call_endpoint(endpoint, payload):
    # This helper is NOT currently used by the main execute_single_test_case function above.
    # Main task calls replay_post_request directly. This helper also constructs header_str
    # differently than how replay_post_request might expect if it takes a dict.
    headers = {h.key: h.value for h in (endpoint.headers or [])}
    header_str = "\n".join(f"{k}: {v}" for k, v in headers.items()) # replay_post_request takes a dict
    result = replay_post_request(endpoint.hostname, endpoint.endpoint, payload, header_str) # Header mismatch
    # ... (rest of this helper needs review if used) ...
    if not result:
        return None, None, "No response from HTTP service"
    code = result.get("status_code")
    body = result.get("response_text")
    if code is None: # This implies an error in the request itself
        return None, None, body # 'body' here might be an error message from replay_post_request
    return code, body, None # error_msg is None if code is present

# Ensure this helper's 'payload_dict' argument receives the Python dictionary,
# as TestExecution.request_payload is JSONB.
# The call in the main function passes 9 arguments (including task_id, started_at_time).
# Your definition from the file takes 7 (missing task_id, started_at_time).
# I'm updating the definition here to match the 9-argument call.
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

# This helper takes IDs and the payload_dict (which is correct for TestExecution.request_payload being JSONB).
# It also correctly takes task_id.
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