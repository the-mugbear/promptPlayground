# workers/execution_tasks.py
import time
import json
import logging
import traceback
from datetime import datetime
from celery import shared_task, group, chord # Removed chain as it's not used by orchestrator directly
from celery.exceptions import SoftTimeLimitExceeded, TaskRevokedError
from celery_app import celery
import logging as py_logging # Use a different alias to avoid conflict if 'logger' is module-level

simple_task_logger = py_logging.getLogger(__name__ + ".simple_test_task")


from extensions import db, socketio
from models.model_TestRun import TestRun
from models.model_TestSuite import TestSuite
from models.model_TestCase import TestCase
from models.model_TestRunAttempt import TestRunAttempt
from models.model_Endpoints import Endpoint # Ensure this is the correct model name (vs. Endpoints)
from models.model_PromptFilter import PromptFilter
from models.model_TestExecution import TestExecution
from sqlalchemy import func

from services.common.http_request_service import replay_post_request # Your import
from services.transformers.registry import apply_transformation # Your import

# Get a logger for this module
logger = py_logging.getLogger(__name__)

PARALLEL_BATCH_SIZE = 8 # You can tune this

# --- Helper Function to Emit SocketIO Events ---
def emit_run_update(run_id, event_name, data):
    room_name = f'test_run_{run_id}'
    logger.info(f"EmitHelper (Celery Worker): Attempting to emit SocketIO event. Event: '{event_name}', Room: '{room_name}', RunID: {run_id}, Data: {str(data)[:300]}...")
    try:
        # Assuming socketio instance is correctly configured with message_queue for Celery
        socketio.emit(event_name, data, room=room_name, namespace='/')
        # It's hard to get the current Celery task ID reliably in a global helper like this
        # without passing it. Logging from within the task is better for task-specific ID.
        logger.info(f"EmitHelper: Emitted '{event_name}' to room '{room_name}'. Status: {data.get('status', '(no status in data)')}")
    except Exception as e:
        logger.error(f"EmitHelper: FAILED to emit SocketIO event '{event_name}' for run {run_id}. Error: {e}", exc_info=True)

# --- Orchestrator Task ---
@celery.task(bind=True, acks_late=True, name='tasks.orchestrate_test_run')
def orchestrate_test_run_task(self, test_run_id):
    logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Starting orchestration.")
    test_run = None

    try:
        test_run = db.session.get(TestRun, test_run_id)
        if not test_run:
            logger.error(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: TestRun not found. Aborting.")
            return {'status': 'FAILED', 'reason': f'TestRun {test_run_id} not found'}

        test_run.celery_task_id = self.request.id
        test_run.start_time = datetime.utcnow()
        test_run.end_time = None
        test_run.progress_current = 0

        all_test_cases_for_run = []
        if not test_run.test_suites or not any(ts.test_cases for ts in test_run.test_suites): # Simplified check
            logger.warning(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: No test suites or test cases found.")
            test_run.progress_total = 0
        else:
            for test_suite in test_run.test_suites:
                for tc_model in test_suite.test_cases:
                    all_test_cases_for_run.append({
                        'test_case_id': tc_model.id,
                        'prompt_text': tc_model.prompt
                    })
            test_run.progress_total = len(all_test_cases_for_run)

        if test_run.progress_total == 0:
            test_run.status = 'completed' # Or 'skipped' or 'empty' depending on your desired states
            test_run.end_time = datetime.utcnow()
            db.session.commit()
            emit_run_update(test_run_id, 'run_completed', test_run.get_status_data())
            logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: No test cases. Marked {test_run.status}.")
            return {'status': test_run.status.upper(), 'reason': 'No test cases'}

        test_run.status = 'running'
        db.session.commit()
        logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Status 'running'. Total cases: {test_run.progress_total}.")
        emit_run_update(test_run_id, 'progress_update', test_run.get_status_data())

        endpoint = db.session.get(Endpoint, test_run.endpoint_id)
        if not endpoint:
            logger.error(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Endpoint ID {test_run.endpoint_id} not found.")
            raise ValueError(f"Endpoint not found for TestRun {test_run_id}")

        run_level_filters_data = []
        if test_run.filters: # These are PromptFilter instances
            for pf_instance in test_run.filters:
                run_level_filters_data.append({
                    'id': pf_instance.id,
                    'name': pf_instance.name,
                    'invalid_characters': pf_instance.invalid_characters,
                    'words_to_replace': pf_instance.words_to_replace
                })
        logger.debug(f"Orchestrator TR_ID:{test_run_id}: Prepared {len(run_level_filters_data)} run-level filters.")

        current_run_attempt = TestRunAttempt(
            test_run_id=test_run.id,
            attempt_number=(db.session.query(func.max(TestRunAttempt.attempt_number)).filter_by(test_run_id=test_run.id).scalar() or 0) + 1,
            status='running', started_at=datetime.utcnow()
        )
        db.session.add(current_run_attempt)
        db.session.flush()
        current_run_attempt_id = current_run_attempt.id
        db.session.commit()
        logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Created TestRunAttempt ID {current_run_attempt_id}.")

        current_batch_signatures = []
        for i, case_data_from_loop in enumerate(all_test_cases_for_run):
            # --- Pause/Cancel Check Loop ---
            while True: # Loop to handle pausing state
                # Ensure self.is_revoked() calls the stub in ContextTask or actual Celery method
                if self.is_revoked():
                    logger.warning(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Task revoked during case processing.")
                    raise TaskRevokedError("Task revoked by external signal")

                # Fetch current status directly from DB to reflect external changes
                current_db_status_for_case = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
                if current_db_status_for_case == 'cancelling':
                    logger.warning(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Cancellation requested.")
                    raise ValueError("Run cancellation requested.")
                
                if current_db_status_for_case == 'pausing':
                    db.session.query(TestRun).filter_by(id=test_run_id).update({'status': 'paused'})
                    db.session.commit()

                    # Detach all loaded objects, return conn to pool
                    db.session.expunge_all()
                    db.session.remove()

                    test_run.status = 'paused' # Update local object
                    emit_run_update(test_run_id, 'run_paused', test_run.get_status_data())
                    logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Run PAUSED.")
                
                if current_db_status_for_case == 'paused':
                    time.sleep(3) # Check every 3 seconds while paused
                    continue # Re-check revocation and status
                
                # If status is 'running' or any other, break pause loop and proceed
                if current_db_status_for_case == 'running' and test_run.status == 'paused': # Check if it was previously paused by this task
                     logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Run RESUMING.")
                     test_run.status = 'running' # Update local object
                     emit_run_update(test_run_id, 'run_resuming', test_run.get_status_data())
                break # Exit pause loop

            current_test_case_id = case_data_from_loop['test_case_id']
            processed_prompt = case_data_from_loop['prompt_text']
            logger.info(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Original prompt: '{processed_prompt[:100]}...'")

            # --- 1. Apply TestCase-specific Transformations ---
            test_case_instance = db.session.get(TestCase, current_test_case_id)
            if test_case_instance and test_case_instance.transformations:
                case_transformations_list = test_case_instance.transformations
                if isinstance(case_transformations_list, list):
                    logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Found {len(case_transformations_list)} TestCase transformations.")
                    for t_info in case_transformations_list:
                        if not isinstance(t_info, dict):
                            logger.warning(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Skipping non-dict transformation item: {t_info}")
                            continue
                        
                        transform_type = t_info.get('type')
                        params_for_transform_apply = None
                        if 'config' in t_info and isinstance(t_info['config'], dict):
                            params_for_transform_apply = t_info['config']
                        elif 'value' in t_info: # Support for simpler {"type": "...", "value": "..."} structure
                            params_for_transform_apply = {'value': t_info['value']}
                        
                        # Handle transformations that might not need explicit params from TestCase.transformations
                        # if they use defaults or no params (e.g. base64_encode)
                        if transform_type and params_for_transform_apply is None:
                            params_for_transform_apply = {} # Pass empty dict if config/value missing but type exists

                        if transform_type:
                            try:
                                logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Applying TC transform '{transform_type}' with params {params_for_transform_apply}.")
                                processed_prompt = apply_transformation(transform_type, processed_prompt, params_for_transform_apply)
                                logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Prompt after TC transform '{transform_type}': '{processed_prompt[:100]}...'")
                            except Exception as trans_exc:
                                logger.warning(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Error applying TestCase transformation '{transform_type}': {trans_exc}", exc_info=True)
                        else:
                            logger.warning(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Skipping TestCase transformation due to missing type: original_info='{t_info}'")
                else:
                    logger.warning(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: TestCase.transformations is not a list. Value: {case_transformations_list}")
            else:
                logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: No TestCase-specific transformations.")

            # --- 2. Apply TestRun-level Filters ---
            if run_level_filters_data:
                logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Applying {len(run_level_filters_data)} TestRun filters.")
                for filter_entry in run_level_filters_data:
                    filter_name = filter_entry.get('name', 'Unnamed Filter')
                    invalid_chars = filter_entry.get('invalid_characters')
                    words_map = filter_entry.get('words_to_replace')
                    try:
                        if invalid_chars and isinstance(invalid_chars, str):
                            logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Applying Run filter '{filter_name}': removing chars '{invalid_chars}'.")
                            for char_to_remove in invalid_chars:
                                processed_prompt = processed_prompt.replace(char_to_remove, "")
                        if words_map and isinstance(words_map, dict):
                            logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Applying Run filter '{filter_name}': replacing words.")
                            for word, replacement in words_map.items():
                                processed_prompt = processed_prompt.replace(word, replacement)
                        if invalid_chars or (words_map and isinstance(words_map, dict)): # Log only if action taken
                            logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Prompt after Run filter '{filter_name}': '{processed_prompt[:100]}...'")
                    except Exception as filter_exc:
                        logger.warning(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Error applying TestRun filter '{filter_name}': {filter_exc}", exc_info=True)
            else:
                logger.debug(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: No TestRun-level filters.")

            final_prompt_for_subtask = processed_prompt
            logger.info(f"Orchestrator TR_ID:{test_run_id}, TC_ID:{current_test_case_id}: Final processed prompt for subtask: '{final_prompt_for_subtask[:100]}...'")
            
            current_sequence_number = i # Use the enumeration index as the sequence number (0-based)
                                       # Or i + 1 if you want 1-based sequence numbers

            # Inside orchestrate_test_run_task, before single_case_sig = ...
            logger.info(f"Orchestrator: Preparing to call execute_single_test_case_task with:"
                        f" test_run_attempt_id={current_run_attempt_id},"
                        f" test_case_id={current_test_case_id},"
                        f" endpoint_id={endpoint.id if endpoint else None},"
                        f" prompt_text='{final_prompt_for_subtask[:50]}...', " 
                        f" sequence_num={current_sequence_number}")

            # Make sure execute_single_test_case_task is defined in this module or imported
            single_case_sig = execute_single_test_case_task.s(
                test_run_attempt_id=current_run_attempt_id,
                test_case_id=current_test_case_id,
                endpoint_id=endpoint.id,
                prompt_text=final_prompt_for_subtask,
                sequence_num=current_sequence_number
            )

            if test_run.run_serially:
                # ... (serial execution logic as you had, ensuring db.session.refresh(test_run) after commit) ...
                logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Executing TC_ID:{current_test_case_id} serially.")
                try:
                    result = single_case_sig.delay().get(timeout=360) 
                    db.session.query(TestRun).filter_by(id=test_run_id).update(
                        {TestRun.progress_current: TestRun.progress_current + 1}, synchronize_session=False)
                    db.session.commit()
                    db.session.refresh(test_run)
                    emit_run_update(test_run_id, 'progress_update', test_run.get_status_data())
                    if result and result.get('status') == 'FAILED':
                        logger.warning(f"Orchestrator: Serial sub-task for TC_ID:{current_test_case_id} FAILED: {result.get('reason')}")
                except Exception as e_serial:
                    logger.error(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Error/Timeout in serial sub-task for TC_ID:{current_test_case_id}: {e_serial}", exc_info=True)
                    db.session.query(TestRun).filter_by(id=test_run_id).update(
                        {TestRun.progress_current: TestRun.progress_current + 1}, synchronize_session=False) # Count as processed
                    db.session.commit()
                    db.session.refresh(test_run)
                    emit_run_update(test_run_id, 'progress_update', test_run.get_status_data())
            else: # Parallel
                current_batch_signatures.append(single_case_sig)
                if len(current_batch_signatures) >= PARALLEL_BATCH_SIZE or \
                   (i == len(all_test_cases_for_run) - 1 and current_batch_signatures):
                    logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Launching parallel batch of {len(current_batch_signatures)}.")
                    # Make sure handle_batch_completion_task is defined or imported
                    callback_sig = handle_batch_completion_task.s(test_run_id=test_run_id, num_cases_in_batch=len(current_batch_signatures))
                    # Ensure chord and group are imported from celery
                    from celery import chord, group 
                    active_chord = chord(group(current_batch_signatures), callback_sig).apply_async()
                    logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Batch chord {active_chord.id} launched.")
                    current_batch_signatures = []
        
        # --- Finalization Loop for Parallel Runs ---
        if not test_run.run_serially:
            # ... (finalization loop for parallel runs, similar to what you had, ensuring db.session.refresh(test_run) inside) ...
            # ... and checks for self.is_revoked() and current_db_status_final_loop ...
            timeout_seconds = 180 
            sleep_interval = 5
            logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Entering final wait loop for parallel progress.")
            db.session.refresh(test_run) # Initial refresh before loop
            while timeout_seconds > 0:
                if test_run.progress_current >= test_run.progress_total:
                    logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: All parallel progress accounted for.")
                    break
                if self.is_revoked():
                    logger.warning(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Revoked during final progress wait.")
                    raise TaskRevokedError("Revoked during final progress wait")
                current_db_status_final_loop = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
                if current_db_status_final_loop == 'cancelling':
                    logger.warning(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Cancellation signal during final progress wait.")
                    raise ValueError("Run cancellation requested during final wait")
                # (Handle 'pausing'/'paused' states here as in the per-case loop if necessary)
                logger.info(f"Orchestrator TR_ID:{test_run_id}: Waiting for parallel. Progress: {test_run.progress_current}/{test_run.progress_total}. Timeout in {timeout_seconds}s")
                time.sleep(sleep_interval)
                timeout_seconds -= sleep_interval
                db.session.refresh(test_run)
            if test_run.progress_current < test_run.progress_total:
                logger.warning(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: TIMEOUT waiting for full parallel progress. Reached {test_run.progress_current}/{test_run.progress_total}.")

        # --- Final Status Determination ---
        db.session.refresh(test_run) # Get final state
        final_status_check_on_db = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()

        if self.is_revoked() or final_status_check_on_db == 'cancelling':
            if final_status_check_on_db != 'cancelled': # Avoid double update if already cancelled
                db.session.query(TestRun).filter_by(id=test_run_id).update({'status': 'cancelled', 'end_time': datetime.utcnow()})
                db.session.commit()
            test_run.status = 'cancelled'
            emit_run_update(test_run_id, 'run_cancelled', test_run.get_status_data())
            logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Finalized as CANCELLED.")
            return {'status': 'CANCELLED', 'reason': 'Task revoked or run cancelled'}
        else:
            if test_run.progress_current >= test_run.progress_total:
                test_run.status = 'completed'
            else: # Should only happen if timed out in parallel, or serial had issues not caught
                test_run.status = 'failed'
                logger.error(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Finalizing as FAILED due to incomplete progress ({test_run.progress_current}/{test_run.progress_total}).")
            
            test_run.end_time = datetime.utcnow()
            if test_run.status == 'completed':
                test_run.progress_current = test_run.progress_total # Ensure consistency
            
            db.session.commit()
            emit_event_name = 'run_completed' if test_run.status == 'completed' else 'run_failed'
            emit_run_update(test_run_id, emit_event_name, test_run.get_status_data())
            logger.info(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Finalized as {test_run.status.upper()}.")
            return {'status': test_run.status.upper()}

    except (TaskRevokedError, SoftTimeLimitExceeded) as e_revoke_timeout:
        logger.warning(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: Task REVOKED or TIMED OUT: {type(e_revoke_timeout).__name__}")
        if test_run:
            current_status = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
            if current_status not in ['failed', 'completed', 'cancelled']:
                db.session.query(TestRun).filter_by(id=test_run_id).update({'status': 'cancelled', 'end_time': datetime.utcnow()})
                db.session.commit()
                test_run.status = 'cancelled'
                emit_run_update(test_run_id, 'run_cancelled', test_run.get_status_data())
        return {'status': 'REVOKED', 'reason': str(e_revoke_timeout)}
    except ValueError as ve:
        logger.error(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: ValueError: {ve}")
        if test_run:
            error_status = 'cancelled' if "cancel" in str(ve).lower() else 'failed'
            current_status = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
            if current_status not in ['failed', 'completed', 'cancelled']:
                db.session.query(TestRun).filter_by(id=test_run_id).update({'status': error_status, 'end_time': datetime.utcnow()})
                db.session.commit()
                test_run.status = error_status
                emit_event = 'run_cancelled' if error_status == 'cancelled' else 'run_failed'
                emit_run_update(test_run_id, emit_event, test_run.get_status_data())
        return {'status': error_status.upper() if test_run else 'FAILED', 'reason': str(ve)}
    except Exception as e_general:
        logger.error(f"Orchestrator TR_ID:{test_run_id}, TaskID:{self.request.id}: UNEXPECTED ERROR: {e_general}", exc_info=True)
        if test_run:
            current_status = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
            if current_status not in ['failed', 'completed', 'cancelled']:
                db.session.query(TestRun).filter_by(id=test_run_id).update({'status': 'failed', 'end_time': datetime.utcnow()})
                db.session.commit()
                test_run.status = 'failed'
                emit_run_update(test_run_id, 'run_failed', test_run.get_status_data())
        return {'status': 'FAILED', 'reason': str(e_general)}
    finally:
        if db.session and db.session.is_active:
            db.session.remove()

# --- Single Test Case Execution Task ---
@celery.task(bind=True, acks_late=True, name='tasks.execute_single_case')
def execute_single_test_case_task(self, test_run_attempt_id, test_case_id, endpoint_id, prompt_text, sequence_num):
    task_id = self.request.id
    logger.info(f"SingleCaseTask {task_id}: Start TCID={test_case_id}, Seq={sequence_num}")

    attempt = None # Initialize
    case = None # Initialize
    record = None # Initialize

    try:
        attempt, case, endpoint = fetch_objects(test_run_attempt_id, test_case_id, endpoint_id)
        payload = build_payload(endpoint.http_payload, prompt_text)  
        status_code, body, error = call_endpoint(endpoint, payload)  
        record = create_execution_record(attempt, case, sequence_num, payload, status_code, body, error)
        db.session.add(record); db.session.commit()

        emit_execution_update(attempt, record)
        return {"status":"SUCCESS","execution_id":record.id,"test_case_id":case.id,"disposition":record.status}

    except Exception as ex:
        logger.error(f"SingleCaseTask {task_id}: EXCEPTION for TCID={test_case_id}, AttemptID={test_run_attempt_id} - Type: {type(ex).__name__}, Error: {ex}", exc_info=True)
        db.session.rollback() # Rollback any partial changes from the try block

        current_payload_for_error = "Payload not generated"
        if 'payload' in locals() and locals()['payload'] is not None:
            current_payload_for_error = str(locals()['payload']) # Convert to string just in case

        # Use the new create_error_record function
        # It's crucial that test_run_attempt_id and test_case_id are valid here.
        # They are direct arguments to the task, so they should be.
        record = create_error_record(
            attempt_id=test_run_attempt_id,
            case_id=test_case_id,
            sequence_num=sequence_num,
            error_exception=ex,
            payload=current_payload_for_error,
            task_id=task_id
        )
        
        try:
            db.session.add(record)
            db.session.commit()
            logger.info(f"SingleCaseTask {task_id}: CREATED error TestExecution record ID {record.id} for TCID={test_case_id}")
            
            # Attempt to fetch 'attempt' object if it wasn't fetched successfully before the exception
            # This is for emit_execution_update. If it's still None, emit_execution_update might need to handle it or skip.
            if not attempt and test_run_attempt_id:
                try:
                    attempt = db.session.get(TestRunAttempt, test_run_attempt_id)
                    if not attempt:
                         logger.warning(f"SingleCaseTask {task_id}: Could not re-fetch TestRunAttempt {test_run_attempt_id} for emit_execution_update after error.")
                except Exception as e_refetch:
                    logger.error(f"SingleCaseTask {task_id}: Error re-fetching TestRunAttempt {test_run_attempt_id} for emit: {e_refetch}")

            if attempt and record: # Ensure both are available
                emit_execution_update(attempt, record)
            else:
                logger.warning(f"SingleCaseTask {task_id}: Skipped emit_execution_update for error on TCID={test_case_id} due to missing attempt or record object.")

        except Exception as e_commit_err:
            # This is a critical failure: failed to even record the error.
            logger.critical(f"SingleCaseTask {task_id}: FAILED TO COMMIT ERROR RECORD for TCID={test_case_id}: {e_commit_err}", exc_info=True)
            # At this point, the record is lost.

        return {"status":"FAILED","reason":str(ex),"test_case_id":test_case_id,"disposition":"error"}

    finally:
        if db.session and db.session.is_active:
            logger.debug(f"SingleCaseTask {task_id}: Removing DB session for TCID={test_case_id}")
            db.session.remove()

# --- Callback Task for Parallel Batches ---
@celery.task(bind=True, acks_late=True, name='tasks.handle_batch_completion')
def handle_batch_completion_task(self, results, test_run_id, num_cases_in_batch):
    logger.info(f"BatchCallback {self.request.id}: TR:{test_run_id}. BatchSize:{num_cases_in_batch}. ResultsRcvd:{len(results)}")
    test_run = None
    try:
        test_run = db.session.get(TestRun, test_run_id)
        if not test_run:
            logger.error(f"BatchCallback {self.request.id}: TR:{test_run_id} NOT FOUND.")
            return {'status': 'FAILED', 'reason': 'TestRun not found'}

        # Atomically update progress_current in DB
        updated_rows = db.session.query(TestRun).filter_by(id=test_run_id).update(
            {TestRun.progress_current: TestRun.progress_current + num_cases_in_batch}, # Increment by batch size
            synchronize_session=False
        )
        db.session.commit()

        if updated_rows == 0:
            logger.warning(f"BatchCallback {self.request.id}: Progress update for TR:{test_run_id} affected 0 rows. Refreshing state.")
        
        db.session.refresh(test_run) # Get the absolute latest state after update
        
        # Cap progress_current just in case of over-increment due to any logic error/retry
        if test_run.progress_current > test_run.progress_total:
            logger.warning(f"BatchCallback {self.request.id}: Correcting over-incremented progress for TR:{test_run_id}. From {test_run.progress_current} to {test_run.progress_total}")
            db.session.query(TestRun).filter_by(id=test_run_id).update(
                {TestRun.progress_current: test_run.progress_total},
                synchronize_session=False
            )
            db.session.commit()
            db.session.refresh(test_run)
        
        logger.info(f"BatchCallback {self.request.id}: TR:{test_run_id} progress updated to {test_run.progress_current}/{test_run.progress_total}.")
        emit_run_update(test_run_id, 'progress_update', test_run.get_status_data())
        return {'status': 'SUCCESS', 'updated_progress': test_run.progress_current}

    except Exception as e_batch:
        logger.error(f"BatchCallback {self.request.id}: Error for TR:{test_run_id}: {e_batch}", exc_info=True)
        if test_run:
             emit_run_update(test_run_id, 'progress_update', test_run.get_status_data()) # Emit last known good state
        return {'status': 'FAILED', 'reason': str(e_batch)}
    finally:
        if db.session and db.session.is_active:
            db.session.remove()


def fetch_objects(attempt_id, case_id, endpoint_id):
    attempt  = db.session.get(TestRunAttempt, attempt_id)
    case     = db.session.get(TestCase, case_id)
    endpoint = db.session.get(Endpoint, endpoint_id)
    missing = [n for n,o in [("Attempt",attempt),("Case",case),("Endpoint",endpoint)] if not o]
    if missing:
        raise ValueError(f"Missing: {', '.join(missing)}")
    return attempt, case, endpoint

def build_payload(template, prompt):
    if not template:
        return json.dumps({"prompt": prompt})
    injected = json.dumps(prompt)[1:-1]
    if "{{INJECT_PROMPT}}" in template:
        return template.replace("{{INJECT_PROMPT}}", injected)
    raise ValueError("Payload template missing placeholder")

def call_endpoint(endpoint, payload):
    headers = {h.key: h.value for h in endpoint.headers or []}
    result = replay_post_request(endpoint.hostname, endpoint.endpoint, payload, "\n".join(f"{k}: {v}" for k,v in headers.items()))
    if not result:
        return None, None, "No response from HTTP service"
    code = result.get("status_code")
    body = result.get("response_text")
    if code is None:
        return None, None, body
    return code, body, None

def create_execution_record(attempt, case, seq, payload, status_code, body, error_msg):
    disposition = ("pass" if status_code and 200<=status_code<300 else
                   "fail" if status_code else
                   "error")
    return TestExecution(
        test_run_attempt_id=attempt.id,
        test_case_id=case.id,
        sequence=seq,
        processed_prompt=None,         # or move into args
        request_payload=payload,
        response_data=body,
        status_code=status_code,
        error_message=error_msg,
        status=disposition,
        started_at=attempt.started_at, # or track time earlier
        finished_at=datetime.utcnow()
    )

def create_error_record(
    attempt_id: int,
    case_id: int,
    sequence_num: int,
    error_exception: Exception,
    payload: str = "Payload not generated or available in error context",
    task_id: str = "Unknown Celery Task ID"
) -> TestExecution:
    """
    Creates a TestExecution record for a failed task execution.
    """
    logger.error(
        f"Task {task_id}: Creating error record for AttemptID: {attempt_id}, CaseID: {case_id}, Seq: {sequence_num}. Error: {str(error_exception)}"
    )
    
    # Extract a more detailed error message, including traceback
    error_message_detail = f"Exception Type: {type(error_exception).__name__}\n"
    error_message_detail += f"Error: {str(error_exception)}\n"
    error_message_detail += f"Traceback:\n{traceback.format_exc()}"

    # Ensure that payload and error_message_detail are truncated if they are too long for the DB fields
    # Assuming your TestExecution model has length limits on request_payload and error_message
    # You might need to check your model definition for actual limits (e.g., String(2000))
    MAX_PAYLOAD_LENGTH = 2000  # Example, adjust as per your model
    MAX_ERROR_LENGTH = 4000   # Example, adjust as per your model

    truncated_payload = payload
    if payload and len(payload) > MAX_PAYLOAD_LENGTH:
        truncated_payload = payload[:MAX_PAYLOAD_LENGTH - 3] + "..."
        logger.warning(f"Task {task_id}: Truncated payload for error record for CaseID: {case_id}")

    truncated_error_message = error_message_detail
    if len(error_message_detail) > MAX_ERROR_LENGTH:
        truncated_error_message = error_message_detail[:MAX_ERROR_LENGTH - 3] + "..."
        logger.warning(f"Task {task_id}: Truncated error message for error record for CaseID: {case_id}")

    # Fetch attempt object to get started_at time, if available
    # This is optional, can default if attempt_id is somehow invalid, though it shouldn't be
    started_at_time = datetime.utcnow() # Default to now if attempt cannot be fetched
    try:
        if attempt_id: # Should always have attempt_id here
            attempt = db.session.get(TestRunAttempt, attempt_id)
            if attempt:
                started_at_time = attempt.started_at
            else:
                logger.warning(f"Task {task_id}: Could not find TestRunAttempt {attempt_id} when creating error record for CaseID: {case_id}. Using current time for started_at.")
    except Exception as e_fetch:
        logger.error(f"Task {task_id}: Error fetching TestRunAttempt {attempt_id} for error record (CaseID: {case_id}): {e_fetch}")


    return TestExecution(
        test_run_attempt_id=attempt_id,
        test_case_id=case_id,
        sequence=sequence_num,
        request_payload=truncated_payload,
        response_data=None,  # No successful response
        status_code=None,    # No HTTP status code from a successful call
        error_message=truncated_error_message,
        status="error",      # Clearly mark as an error record
        started_at=started_at_time,
        finished_at=datetime.utcnow()
    )

def emit_execution_update(attempt, record):
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
