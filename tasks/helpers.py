# tasks/helpers.py
# Shared helper functions for Celery tasks

import logging
from typing import List, Dict, Any
from extensions import db, socketio
from services.transformers.registry import apply_transformation
from functools import wraps
logger = logging.getLogger(__name__)


def emit_run_update(run_id: int, event_name: str, data: Dict[str, Any]) -> None:
    """
    Emit a SocketIO event to all clients in the test-run room.
    """
    room = f'test_run_{run_id}'
    logger.info(f"EmitHelper: Emitting '{event_name}' to room '{room}', data={{ ... }}")
    try:
        socketio.emit(event_name, data, room=room, namespace='/')
        logger.info(f"EmitHelper: Emitted '{event_name}' successfully.")
    except Exception as e:
        logger.error(f"EmitHelper: Failed to emit '{event_name}' for run {run_id}: {e}", exc_info=True)


def emit_execution_update(attempt, record) -> None:
    """
    Emit a detailed execution_result_update event after a single test-case execution.
    """
    data = {
        "test_run_id": attempt.test_run_id,
        "test_case_id": record.test_case_id,
        "attempt_number": attempt.attempt_number,
        "execution_id": record.id,
        "response_data": record.response_data,
        "status": record.status,
        "status_code": record.status_code,
        "error_message": record.error_message
    }
    emit_run_update(attempt.test_run_id, "execution_result_update", data)

def with_session(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise
        finally:
            db.session.remove()
    return wrapper
