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
        logger.debug(f"PromptProcessor: Applying {len(run_filters)} prompt filter(s).")
        for pf_obj in run_filters: # pf_obj is a PromptFilter ORM instance
            # logger.debug(f"PromptProcessor: Applying filter '{pf_obj.name}'.") # Optional detailed log
            if pf_obj.invalid_characters:
                chars_to_remove_list = pf_obj.invalid_characters.split()
                for char_to_remove in chars_to_remove_list:
                    if char_to_remove:
                        current_prompt = current_prompt.replace(char_to_remove, "")
            
            if pf_obj.words_to_replace and isinstance(pf_obj.words_to_replace, dict):
                for old_word, new_word_val in pf_obj.words_to_replace.items():
                    new_word_str = str(new_word_val) if new_word_val is not None else ""
                    current_prompt = current_prompt.replace(old_word, new_word_str)
    # else:
        # logger.debug(f"PromptProcessor: No prompt filters to apply.")

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
    # else:
        # logger.debug(f"PromptProcessor: No run-level transformations.")
        
    logger.debug(f"PromptProcessor: Final prompt: '{current_prompt[:100]}...'")
    return current_prompt

def _recursively_inject_prompt(data_structure, placeholder: str, replacement_value: str) -> bool:
    """
    Recursively traverses a data structure (dict or list) and replaces any string
    value matching the placeholder with the replacement_value.

    Args:
        data_structure: The dict or list to traverse.
        placeholder: The string placeholder to search for (e.g., "{{INJECT_PROMPT}}").
        replacement_value: The string value to replace the placeholder with.

    Returns:
        True if at least one replacement was made, False otherwise.
    """
    injected = False
    if isinstance(data_structure, dict):
        for key, value in data_structure.items():
            if isinstance(value, str) and value == placeholder:
                data_structure[key] = replacement_value
                injected = True
            elif isinstance(value, (dict, list)):
                if _recursively_inject_prompt(value, placeholder, replacement_value):
                    injected = True
    elif isinstance(data_structure, list):
        for i, item in enumerate(data_structure):
            if isinstance(item, str) and item == placeholder:
                data_structure[i] = replacement_value
                injected = True
            elif isinstance(item, (dict, list)):
                if _recursively_inject_prompt(item, placeholder, replacement_value):
                    injected = True
    return injected

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
