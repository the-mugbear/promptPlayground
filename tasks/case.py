# tasks/case.py
# Single test case execution task and its helpers

import json
import logging
import traceback
from datetime import datetime

from celery_app import celery
from tasks.base import ContextTask, with_session
from extensions import db
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestCase import TestCase
from models.model_Endpoints import Endpoint
from models.model_TestExecution import TestExecution
from services.common.http_request_service import replay_post_request
from services.transformers.registry import apply_transformation
from .helpers import emit_run_update, emit_execution_update

logger = logging.getLogger(__name__)

@celery.task(
    bind=True,
    acks_late=True,
    base=ContextTask,
    name='tasks.execute_single_case'
)
def execute_single_test_case(self, test_run_attempt_id, test_case_id, endpoint_id, prompt_text, sequence_num):
    """
    Executes one test case: applies transformations, calls the endpoint,
    records the result, and emits an execution update.
    """
    task_id = self.request.id
    logger.info(f"SingleCaseTask {task_id}: Start TCID={test_case_id}, Seq={sequence_num}")

    try:
        attempt, case, endpoint = fetch_objects(test_run_attempt_id, test_case_id, endpoint_id)

        payload = build_payload(endpoint.http_payload, prompt_text)
        status_code, body, error = call_endpoint(endpoint, payload)

        record = create_execution_record(attempt, case, sequence_num, payload, status_code, body, error)
        db.session.add(record)
        db.session.commit()
        # 🔥 Return this connection immediately:
        db.session.remove()

        emit_execution_update(attempt, record)
        return {"status": "SUCCESS", "execution_id": record.id, "test_case_id": case.id, "disposition": record.status}

    except Exception as ex:
        logger.error(
            f"SingleCaseTask {task_id}: EXCEPTION for TCID={test_case_id}, "
            f"AttemptID={test_run_attempt_id} - {type(ex).__name__}: {ex}",
            exc_info=True
        )
        db.session.rollback()

        record = create_error_record(
            attempt_id=test_run_attempt_id,
            case_id=test_case_id,
            sequence_num=sequence_num,
            error_exception=ex,
            payload=str(payload) if 'payload' in locals() else "",
            task_id=task_id
        )
        try:
            db.session.add(record)
            db.session.commit()
            # 🔥 Return this connection immediately:
            db.session.remove()
            
            logger.info(f"SingleCaseTask {task_id}: Created error record ID {record.id} for TCID={test_case_id}")
            emit_execution_update(attempt, record)
        except Exception:
            logger.critical(f"SingleCaseTask {task_id}: Failed to commit error record", exc_info=True)

        return {"status": "FAILED", "reason": str(ex), "test_case_id": test_case_id, "disposition": "error"}

# --- Helper Functions ---
@with_session
def fetch_objects(attempt_id, case_id, endpoint_id):
    attempt = db.session.get(TestRunAttempt, attempt_id)
    case = db.session.get(TestCase, case_id)
    endpoint = db.session.get(Endpoint, endpoint_id)
    missing = [name for name, obj in (('Attempt', attempt), ('Case', case), ('Endpoint', endpoint)) if obj is None]
    if missing:
        raise ValueError(f"Missing objects: {', '.join(missing)}")
    return attempt, case, endpoint

@with_session
def build_payload(template, prompt):
    if not template:
        return json.dumps({"prompt": prompt})
    injected = json.dumps(prompt)[1:-1]
    if "{{INJECT_PROMPT}}" in template:
        return template.replace("{{INJECT_PROMPT}}", injected)
    raise ValueError("Payload template missing placeholder")

@with_session
def call_endpoint(endpoint, payload):
    headers = {h.key: h.value for h in (endpoint.headers or [])}
    header_str = "\n".join(f"{k}: {v}" for k, v in headers.items())
    result = replay_post_request(endpoint.hostname, endpoint.endpoint, payload, header_str)
    if not result:
        return None, None, "No response from HTTP service"
    code = result.get("status_code")
    body = result.get("response_text")
    if code is None:
        return None, None, body
    return code, body, None

@with_session
def create_execution_record(attempt, case, seq, payload, status_code, body, error_msg):
    disposition = (
        "pass" if status_code and 200 <= status_code < 300 else
        "fail" if status_code else
        "error"
    )

    final_response_data = body
    final_error_message = error_msg

    if disposition == "pass":
        if body is None:
            final_response_data = "" # Ensure empty string for successful empty responses
        # error_msg should ideally be None for pass, but keep as is if pre-populated
    elif disposition == "fail": # HTTP error from endpoint
        # body contains the error response from the endpoint.
        # error_msg should ideally be None.
        pass # final_response_data is already body
    elif disposition == "error": # Client-side error (status_code is None)
        final_response_data = None
        # error_msg from call_endpoint already contains the detailed error in this case.
        # If error_msg was None (e.g. if call_endpoint changed), ensure some default.
        if final_error_message is None and body is not None: # Defensive: if error_msg was lost, use body
             final_error_message = body if isinstance(body, str) else "Client-side execution error"

    return TestExecution(
        test_run_attempt_id=attempt.id,
        test_case_id=case.id,
        sequence=seq,
        request_payload=payload,
        response_data=final_response_data,
        status_code=status_code,
        error_message=final_error_message,
        status=disposition,
        started_at=attempt.started_at,
        finished_at=datetime.utcnow()
    )

@with_session
def create_error_record(attempt_id, case_id, sequence_num, error_exception, payload, task_id):
    # Build detailed error message
    err_detail = (
        f"Exception {type(error_exception).__name__}: {error_exception}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )
    return TestExecution(
        test_run_attempt_id=attempt_id,
        test_case_id=case_id,
        sequence=sequence_num,
        request_payload=payload,
        response_data=None,
        status_code=None,
        error_message=err_detail,
        status="error",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow()
    )