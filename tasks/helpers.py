# tasks/helpers.py
# Shared helper functions for Celery tasks

import logging
from typing import List, Dict, Any
from extensions import db, socketio
from services.transformers.registry import apply_transformation
from functools import wraps
logger = logging.getLogger(__name__)

def process_prompt_for_case(original_prompt: str, run_filters: list, run_level_transformations: list) -> str:
    """
    Applies run-level filters and transformations to an original prompt.
    'run_filters' is a list of PromptFilter ORM objects.
    'run_level_transformations' is a list of transformation config dicts.
    """
    logger = logging.getLogger(__name__) # Obtain a logger instance
    current_prompt = original_prompt
    # You can add more specific logging here if needed, perhaps by passing case_id

    # STAGE 1: APPLY PROMPT FILTERS (Adapted from your orchestrator.py)
    if run_filters:
        for pf_obj in run_filters:
            inv = pf_obj.invalid_characters or ""
            # Build a list of single chars to strip, ignoring commas/spaces
            chars_to_remove_list = [c for c in inv if (not c.isspace() and c != ",")]

            for char_to_remove in chars_to_remove_list:
                # (Optional) log which character is being removed
                logger.debug(f"[PromptProcessor] Removing invalid char {char_to_remove!r} from prompt")
                current_prompt = current_prompt.replace(char_to_remove, "")

            # If you also have words_to_replace, handle them here:
            if pf_obj.words_to_replace:
                for bad_word, replacement in pf_obj.words_to_replace.items():
                    logger.debug(
                        f"[PromptProcessor] Replacing word {bad_word!r} with {replacement!r}"
                    )
                    current_prompt = current_prompt.replace(bad_word, replacement)

    # STAGE 2: APPLY RUN-LEVEL TRANSFORMATIONS (Adapted from your orchestrator.py)
    if run_level_transformations: # This is a list of config dicts
        # logger.debug(f"PromptProcessor: Applying {len(run_level_transformations)} run-level transformation(s).")
        for tfm_config in run_level_transformations:
            tfm_name = tfm_config.get("name")
            instance_params = tfm_config.get("params", {})
            if tfm_name:
                # logger.debug(f"PromptProcessor: Applying transform '{tfm_name}'.") # Optional
                current_prompt = apply_transformation(
                    t_id=tfm_name,
                    prompt=current_prompt,
                    params=instance_params if isinstance(instance_params, dict) else {}
                )
        
    logger.debug(f"PromptProcessor: Final prompt: '{current_prompt[:100]}...'")
    return current_prompt

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


def emit_execution_update(session, record) -> None:
    """
    Emit a detailed execution_result_update event after a single test-case execution.
    """
    data = {
        "test_run_id": session.test_run_id,
        "test_case_id": record.test_case_id,
        "session_id": session.id,
        "execution_id": record.id,
        "response_data": record.response_data,
        "success": record.success,
        "status_code": record.status_code,
        "error_message": record.error_message,
        "sequence_number": record.sequence_number
    }
    emit_run_update(session.test_run_id, "execution_result_update", data)
    
    # Also emit status code statistics update
    emit_status_code_update(session.test_run_id)

def emit_status_code_update(run_id: int) -> None:
    """
    Emit HTTP status code statistics for the current test run.
    """
    try:
        from sqlalchemy import func
        from models.model_TestRun import TestRun
        from models.model_ExecutionSession import ExecutionSession, ExecutionResult
        
        # Get status code counts for the current run
        status_counts = db.session.query(
            ExecutionResult.status_code,
            func.count(ExecutionResult.id).label('count')
        ).join(
            ExecutionSession, ExecutionResult.session_id == ExecutionSession.id
        ).filter(
            ExecutionSession.test_run_id == run_id,
            ExecutionResult.status_code.isnot(None)
        ).group_by(
            ExecutionResult.status_code
        ).all()
        
        # Format into status code groups
        status_groups = {
            '2xx': 0,  # Success
            '4xx': 0,  # Client errors
            '5xx': 0,  # Server errors
            'other': 0  # Other status codes
        }
        
        detailed_counts = {}
        total_requests = 0
        
        for status_code, count in status_counts:
            total_requests += count
            detailed_counts[status_code] = count
            
            if 200 <= status_code < 300:
                status_groups['2xx'] += count
            elif 400 <= status_code < 500:
                status_groups['4xx'] += count
            elif 500 <= status_code < 600:
                status_groups['5xx'] += count
            else:
                status_groups['other'] += count
        
        data = {
            "run_id": run_id,
            "status_groups": status_groups,
            "detailed_counts": detailed_counts,
            "total_requests": total_requests
        }
        
        emit_run_update(run_id, "status_code_update", data)
        
    except Exception as e:
        logger.error(f"Failed to emit status code update for run {run_id}: {e}", exc_info=True)

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
