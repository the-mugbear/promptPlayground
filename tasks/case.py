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
from models.model_Endpoints import Endpoint
from models.model_TestExecution import TestExecution
from services.common.http_request_service import replay_post_request
from .helpers import emit_run_update, emit_execution_update, with_session

logger = logging.getLogger(__name__)

@celery.task(
    bind=True,
    acks_late=True,
    base=ContextTask,
    name='tasks.execute_single_case'
)
@with_session
def execute_single_test_case(
    self,
    test_run_attempt_id: int,
    test_case_id: int,
    endpoint_id: int,
    prompt_text: str,
    sequence_num: int
):
    
    """
    Executes one test case: applies transformations, calls the endpoint,
    records the result, and emits an execution update.
    """
    logger.debug(
        f"execute_single_test_case was called with args="
        f"(self={self}, test_run_attempt_id={test_run_attempt_id}, "
        f"test_case_id={test_case_id}, endpoint_id={endpoint_id}, "
        f"prompt_text='{prompt_text}', sequence_num={sequence_num})"
    )

    task_id = self.request.id
    logger.info(f"SingleCaseTask {task_id}: Start TCID={test_case_id}, Seq={sequence_num}")

    # 1) Fetch all ORM objects in THIS session
    attempt = db.session.get(TestRunAttempt, test_run_attempt_id)
    case    = db.session.get(TestCase, test_case_id)
    endpoint= db.session.get(Endpoint, endpoint_id)
    missing = [name for name, obj in (('Attempt', attempt), ('Case', case), ('Endpoint', endpoint)) if obj is None]
    if missing:
        raise ValueError(f"Missing objects: {', '.join(missing)}")

    try:
        # 2) Build the payload (no DB reads inside; just string manipulation)
        payload = build_payload(endpoint.http_payload, prompt_text)

        # 3) Call the endpoint (no DB reads inside; only uses "endpoint" attributes)
        status_code, body, error = call_endpoint(endpoint, payload)

        # 4) Create and add the TestExecution record into OUR session
        record = TestExecution(
            test_run_attempt_id=attempt.id,
            test_case_id=case.id,
            sequence=sequence_num,
            request_payload=payload,
            response_data=body,
            status_code=status_code,
            error_message=error,
            # Determine disposition based on status_code
            status=(
                "pass" if status_code and 200 <= status_code < 300 else
                "fail" if status_code else
                "error"
            ),
            started_at=attempt.started_at,
            finished_at=datetime.utcnow()
        )
        db.session.add(record)

        
        # 5) Update the attempt status in this same session
        attempt.status = record.status
        attempt.finished_at = datetime.utcnow()

        # 6) Emit a real‐time update to WebSocket
        #    Note: attempt is still session‐bound, record is too
        emit_execution_update(attempt, record)

        # 7) Return; the @with_session decorator will commit() and remove() the session here
        return {
            "status": "SUCCESS",
            "execution_id": record.id,
            "test_case_id": case.id,
            "disposition": record.status
        }

    except Exception as ex:
        logger.error(
            f"SingleCaseTask {task_id}: EXCEPTION for TCID={test_case_id}, "
            f"AttemptID={test_run_attempt_id} - {type(ex).__name__}: {ex}",
            exc_info=True
        )


        # 8) Create and add the error record in THIS session
        record = create_error_record(
            attempt_id=test_run_attempt_id,
            case_id=test_case_id,
            sequence_num=sequence_num,
            error_exception=ex,
            payload=str(payload) if 'payload' in locals() else "",
            task_id=task_id
        )
        db.session.add(record)

        # 9) Emit an execution‐error update
        #    Because attempt was loaded earlier, it is still session‐bound here.
        emit_execution_update(attempt, record)

        # 10) Return an error structure. Decorator will rollback or commit+remove as appropriate.
        return {
            "status": "FAILED",
            "reason": str(ex),
            "test_case_id": test_case_id,
            "disposition": "error"
        }

# --- Helper Functions ---
def fetch_objects(attempt_id, case_id, endpoint_id):
    attempt = db.session.get(TestRunAttempt, attempt_id)
    case = db.session.get(TestCase, case_id)
    endpoint = db.session.get(Endpoint, endpoint_id)
    missing = [name for name, obj in (('Attempt', attempt), ('Case', case), ('Endpoint', endpoint)) if obj is None]
    if missing:
        raise ValueError(f"Missing objects: {', '.join(missing)}")
    return attempt, case, endpoint

def build_payload(template, prompt):
    if not template:
        return json.dumps({"prompt": prompt})
    injected = json.dumps(prompt)[1:-1]
    if "{{INJECT_PROMPT}}" in template:
        return template.replace("{{INJECT_PROMPT}}", injected)
    raise ValueError("Payload template missing placeholder")

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

def create_execution_record(attempt, case, seq, payload, status_code, body, error_msg):
    disposition = (
        "pass" if status_code and 200 <= status_code < 300 else
        "fail" if status_code else
        "error"
    )
    return TestExecution(
        test_run_attempt_id=attempt.id,
        test_case_id=case.id,
        sequence=seq,
        request_payload=payload,
        response_data=body,
        status_code=status_code,
        error_message=error_msg,
        status=disposition,
        started_at=attempt.started_at,
        finished_at=datetime.utcnow()
    )

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