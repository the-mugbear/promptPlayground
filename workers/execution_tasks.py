import datetime
import json
import os

from extensions import db
from models.model_TestExecution import TestExecution
from models.model_Endpoints import Endpoint
from models.model_PromptFilter import PromptFilter

from services.transformers.registry import apply_transformation
from services.common.http_request_service import replay_post_request
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from celery_app import celery 


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def execute_single_test_case_task(self, execution_id, endpoint_id,
                                  test_case_prompt,
                                  test_case_transformations_data,
                                  run_filter_ids_data,
                                  original_payload_str,
                                  raw_headers_str):
    """
    Background task to fully process and execute one test case.
    Handles transformations, filters, API call, and DB updates.
    """
    execution = None
    try:
        # --- Fetch DB objects within the task context ---
        execution = db.session.get(TestExecution, execution_id)
        if not execution:
             print(f"Error: TestExecution record with ID {execution_id} not found.")
             # Cannot proceed if the core record is missing
             # Implicitly returns None here
             return # Stop processing

        endpoint_obj = db.session.get(Endpoint, endpoint_id)
        if not endpoint_obj:
            print(f"Error: Endpoint record with ID {endpoint_id} not found for Execution {execution_id}.")
            execution.status = 'ERROR'
            execution.response_data = f"Endpoint ID {endpoint_id} not found."
            db.session.commit()
            # Implicitly returns None here
            return # Stop processing

        active_filters = []
        if run_filter_ids_data:
            active_filters = PromptFilter.query.filter(PromptFilter.id.in_(run_filter_ids_data)).all()

        # --- Update execution start time ---
        execution.start_time = datetime.datetime.utcnow()
        execution.status = 'RUNNING'
        # Ensure response_data is clear before potential warnings/errors
        execution.response_data = None
        db.session.commit() # Commit start time and running status

        # --- 1. Start with original prompt ---
        prompt = test_case_prompt

        # --- 2. Apply Transformations ---
        if isinstance(test_case_transformations_data, list):
            for tinfo in test_case_transformations_data:
                transform_type = tinfo.get('type')
                transform_params = {'value': tinfo.get('value')}
                if transform_type:
                    try:
                        prompt = apply_transformation(transform_type, prompt, transform_params)
                    except Exception as trans_exc:
                         print(f"Error applying transformation {transform_type} to Execution {execution_id}: {trans_exc}")
                         execution.status = 'WARNING' # Mark as warning
                         execution.response_data = (execution.response_data or "") + f"\nWarning: Transformation '{transform_type}' failed: {trans_exc}"
                         # Logged and continues

        # --- 3. Apply Filters ---
        for prompt_filter in active_filters:
            try:
                if prompt_filter.invalid_characters:
                    for char in prompt_filter.invalid_characters:
                        prompt = prompt.replace(char, "")
                if prompt_filter.words_to_replace and isinstance(prompt_filter.words_to_replace, dict):
                    for word, replacement in prompt_filter.words_to_replace.items():
                        prompt = prompt.replace(word, replacement)
            except Exception as filter_exc:
                print(f"Error applying filter '{prompt_filter.name}' (ID: {prompt_filter.id}) to Execution {execution_id}: {filter_exc}")
                execution.status = 'WARNING' # Mark as warning
                execution.response_data = (execution.response_data or "") + f"\nWarning: Filter '{prompt_filter.name}' failed: {filter_exc}"
                # Logged and continues

        # --- Store the final, processed prompt ---
        execution.processed_prompt = prompt # Assumes field exists in model

        # --- 4. Inject into Payload ---
        try:
            escaped_prompt = json.dumps(prompt)[1:-1]
            if "{{INJECT_PROMPT}}" in original_payload_str:
                replaced_payload_str = original_payload_str.replace("{{INJECT_PROMPT}}", escaped_prompt)
            else:
                print(f"Warning: '{{{{INJECT_PROMPT}}}}' not found in payload template for Execution {execution_id}.")
                replaced_payload_str = original_payload_str

            execution.payload_sent = replaced_payload_str # Assumes field exists in model

        except Exception as payload_exc:
             print(f"Error preparing payload for Execution {execution_id}: {payload_exc}")
             execution.status = 'ERROR'
             execution.response_data = (execution.response_data or "") + f"\nError preparing payload: {payload_exc}"
             execution.finish_time = datetime.datetime.utcnow()
             db.session.commit()
             # Implicitly returns None here
             return # Stop if payload prep fails

        # --- 5. Make HTTP Request ---
        try:
            result = replay_post_request(
                endpoint_obj.hostname,
                endpoint_obj.endpoint,
                replaced_payload_str,
                raw_headers_str,
                timeout=60
            )

            # --- Update execution based on result ---
            execution.finish_time = datetime.datetime.utcnow()
            execution.response_data = result.get("response_text", "No response text received.")
            execution.status_code = result.get("status_code")

            # Determine final status - Keep 'WARNING' if set previously
            if execution.status != 'WARNING':
                if execution.status_code and 200 <= execution.status_code < 300:
                    execution.status = 'PASSED' # Or PENDING_REVIEW based on your logic
                else:
                    execution.status = 'PENDING_REVIEW' # Or FAILED

        except Exception as req_exc:
            print(f"Error during HTTP request for Execution {execution_id}: {req_exc}")
            execution.finish_time = datetime.datetime.utcnow()
            execution.status = 'FAILED'
            execution.response_data = (execution.response_data or "") + f"\nRequest Error: {req_exc}"
            # Let Celery handle retry via OperationalError if applicable

        # --- Commit final changes for THIS execution ---
        db.session.commit()
        # Implicitly returns None here if successful

    except OperationalError as exc:
        # --- Handle DB connection errors ---
        print(f"Database operational error for Execution {execution_id}: {exc}. Retrying...")
        db.session.rollback() # Rollback session before retry
        # Celery's retry logic will handle the actual retry attempt
        self.retry(exc=exc)
        # Implicitly returns None here (as retry raises an exception)

    except Exception as e:
        # --- Handle any other unexpected errors ---
        print(f"Unexpected error processing Execution {execution_id}: {e}")
        db.session.rollback() # Rollback any partial changes
        if execution: # If we fetched the execution record before the error
            try:
                # Try to mark the execution as errored
                execution.status = 'ERROR'
                execution.finish_time = datetime.datetime.utcnow()
                execution.response_data = (execution.response_data or "") + f"\nUnexpected Task Error: {e}"
                db.session.commit()
            except Exception as commit_err:
                print(f"Failed to commit error status for Execution {execution_id} after main error: {commit_err}")
                db.session.rollback()
        # Implicitly returns None here

    finally:
        # Optional: Close session if using scoped sessions, though Flask-SQLAlchemy often handles this.
        # db.session.remove()
        pass

    # No explicit 'return' statement needed here unless you want to store a specific value in the result backend.