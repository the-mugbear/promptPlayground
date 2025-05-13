# workers/execution_tasks.py
import time
import json
import logging
from datetime import datetime
from celery import shared_task, group, chord # Removed chain as it's not used by orchestrator directly
from celery.exceptions import SoftTimeLimitExceeded, TaskRevokedError
import logging # Import the logging module

from extensions import db, socketio
from models.model_TestRun import TestRun
from models.model_TestSuite import TestSuite
from models.model_TestCase import TestCase
from models.model_TestRunAttempt import TestRunAttempt
from models.model_Endpoints import Endpoint # Ensure this is the correct model name (vs. Endpoints)
from models.model_PromptFilter import PromptFilter
from sqlalchemy import func

from services.common.http_request_service import replay_post_request # Your import
from services.transformers.registry import apply_transformation # Your import

# Get a logger for this module
logger = logging.getLogger(__name__)

PARALLEL_BATCH_SIZE = 20 # You can tune this

# --- Helper Function to Emit SocketIO Events ---
def emit_run_update(run_id, event_name, data):
    room_name = f'test_run_{run_id}'
    try:
        # Assuming socketio instance is correctly configured with message_queue for Celery
        socketio.emit(event_name, data, room=room_name, namespace='/')
        # It's hard to get the current Celery task ID reliably in a global helper like this
        # without passing it. Logging from within the task is better for task-specific ID.
        logger.info(f"EmitHelper: Emitted '{event_name}' to room '{room_name}'. Status: {data.get('status', '(no status in data)')}")
    except Exception as e:
        logger.error(f"EmitHelper: FAILED to emit SocketIO event '{event_name}' for run {run_id}. Error: {e}", exc_info=True)


# --- Orchestrator Task ---
@shared_task(bind=True, acks_late=True, name='tasks.orchestrate_test_run')
def orchestrate_test_run_task(self, test_run_id):
    logger.info(f"Orchestrator {self.request.id}: Starting for TestRun ID: {test_run_id}")
    test_run = None
    active_chord_result = None

    try:
        # It's often better to work with a detached object or re-fetch frequently in long tasks
        # to avoid detached instance errors if the session is managed per request/task.
        # For now, db.session.get should work if the session remains valid or is handled by a custom task base class.
        test_run = db.session.get(TestRun, test_run_id)
        if not test_run:
            logger.error(f"Orchestrator {self.request.id}: TestRun {test_run_id} not found. Aborting.")
            return {'status': 'FAILED', 'reason': f'TestRun {test_run_id} not found'}

        # --- Initial Setup ---
        test_run.celery_task_id = self.request.id
        test_run.start_time = datetime.utcnow()
        test_run.end_time = None
        test_run.progress_current = 0

        all_test_cases_for_run = []
        if not test_run.test_suites or not any(list(ts.test_cases) for ts in test_run.test_suites):
            logger.warning(f"Orchestrator {self.request.id}: TestRun {test_run_id} has no test suites or no test cases in them.")
            test_run.progress_total = 0
        else:
            for test_suite in test_run.test_suites:
                for tc in test_suite.test_cases:
                    all_test_cases_for_run.append({
                        'test_case_id': tc.id,
                        'prompt_text': tc.prompt
                    })
            test_run.progress_total = len(all_test_cases_for_run)

        if test_run.progress_total == 0:
            logger.info(f"Orchestrator {self.request.id}: TestRun {test_run_id} - No test cases. Marking completed.")
            test_run.status = 'completed'
            test_run.end_time = datetime.utcnow()
            db.session.commit()
            emit_run_update(test_run_id, 'run_completed', test_run.get_status_data())
            return {'status': 'COMPLETED', 'reason': 'No test cases'}

        test_run.status = 'running'
        db.session.commit()
        logger.info(f"Orchestrator {self.request.id}: TestRun {test_run_id} now 'running'. Total cases: {test_run.progress_total}.")
        emit_run_update(test_run_id, 'progress_update', test_run.get_status_data())

        endpoint = db.session.get(Endpoint, test_run.endpoint_id) if test_run.endpoint_id else None
        if not endpoint:
            logger.error(f"Orchestrator {self.request.id}: Endpoint not found for TestRun {test_run_id}. Failing run.")
            raise ValueError(f"Endpoint not found for TestRun {test_run_id}") # This will go to the general exception handler

        filters_for_subtasks = []
        if test_run.filters: # Assuming test_run.filters relation is loaded
            for pf in test_run.filters:
                filters_for_subtasks.append({'id': pf.id, 'type': pf.type, 'config': pf.config})

        current_batch_signatures = []
        # Create ONE TestRunAttempt for this entire orchestration pass
        current_run_attempt = TestRunAttempt(
            test_run_id=test_run.id,
            attempt_number=(db.session.query(func.max(TestRunAttempt.attempt_number)).filter_by(test_run_id=test_run.id).scalar() or 0) + 1,
            status='running', # This attempt is now running
            started_at=datetime.utcnow()
        )
        db.session.add(current_run_attempt)
        db.session.flush() # To get current_run_attempt.id for sub-tasks
        current_run_attempt_id = current_run_attempt.id
        logger.info(f"Orchestrator {self.request.id}: Created TestRunAttempt ID {current_run_attempt_id} for TestRun {test_run_id}.")
        db.session.commit() # Commit the new attempt

        for i, case_data in enumerate(all_test_cases_for_run):
            # Pause/Cancel Check
            current_db_status = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
            while current_db_status == 'pausing' or current_db_status == 'paused':
                if current_db_status == 'pausing':
                    db.session.query(TestRun).filter_by(id=test_run_id).update({'status': 'paused'})
                    db.session.commit()
                    test_run.status = 'paused'
                    emit_run_update(test_run_id, 'run_paused', test_run.get_status_data())
                    logger.info(f"Orchestrator {self.request.id}: TestRun {test_run_id} PAUSED.")
                time.sleep(3)
                if self.is_revoked(): raise TaskRevokedError()
                current_db_status = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
                if current_db_status == 'cancelling':
                    logger.warning(f"Orchestrator {self.request.id}: Cancellation requested during pause for TR:{test_run_id}")
                    raise ValueError("Run cancellation requested during pause.")
                if current_db_status == 'running':
                    logger.info(f"Orchestrator {self.request.id}: TestRun {test_run_id} RESUMING.")
                    test_run.status = 'running'
                    emit_run_update(test_run_id, 'run_resuming', test_run.get_status_data())
                    break
            
            if self.is_revoked(): raise TaskRevokedError()
            if current_db_status == 'cancelling': raise ValueError("Run cancellation requested.")

            transformed_prompt = apply_transformation(case_data['prompt_text'], filters_for_subtasks)
            
            single_case_sig = execute_single_test_case_task.s(
                test_run_attempt_id=current_run_attempt_id, # Pass the ID of the single attempt for this run
                test_case_id=case_data['test_case_id'],
                endpoint_id=endpoint.id,
                prompt_text=transformed_prompt,
                # http_method and headers can be passed if they are dynamic per case,
                # or sub-task can fetch endpoint and derive them. For now, assume endpoint details are stable.
                # http_method_override = endpoint.http_method, 
                # headers_override_json = json.dumps({h.key: h.value for h in endpoint.api_headers}) if endpoint.api_headers else None
            )

            if test_run.run_serially:
                logger.info(f"Orchestrator {self.request.id}: Executing case {case_data['test_case_id']} serially for TR:{test_run_id}.")
                try:
                    result = single_case_sig.delay().get(timeout=360) # Increased timeout
                    # For serial, the sub-task creates TestExecution. Orchestrator updates TestRun progress.
                    db.session.query(TestRun).filter_by(id=test_run_id).update(
                        {TestRun.progress_current: TestRun.progress_current + 1},
                        synchronize_session=False
                    )
                    db.session.commit()
                    db.session.refresh(test_run)
                    emit_run_update(test_run_id, 'progress_update', test_run.get_status_data())
                    if result and result.get('status') == 'FAILED':
                        logger.warning(f"Orchestrator: Serial sub-task for case {case_data['test_case_id']} (TR:{test_run_id}) FAILED: {result.get('reason')}")
                except Exception as e_serial_subtask:
                    logger.error(f"Orchestrator {self.request.id}: Error in serial sub-task for case {case_data['test_case_id']} (TR:{test_run_id}): {e_serial_subtask}", exc_info=True)
                    db.session.query(TestRun).filter_by(id=test_run_id).update(
                        {TestRun.progress_current: TestRun.progress_current + 1}, # Count as processed
                        synchronize_session=False
                    )
                    db.session.commit()
                    db.session.refresh(test_run)
                    emit_run_update(test_run_id, 'progress_update', test_run.get_status_data())
            else: # Parallel
                current_batch_signatures.append(single_case_sig)
                if len(current_batch_signatures) == PARALLEL_BATCH_SIZE or \
                   (i == len(all_test_cases_for_run) - 1 and current_batch_signatures):
                    logger.info(f"Orchestrator {self.request.id}: Launching parallel batch of {len(current_batch_signatures)} for TR:{test_run_id}.")
                    callback_sig = handle_batch_completion_task.s(
                        test_run_id=test_run_id,
                        num_cases_in_batch=len(current_batch_signatures)
                    )
                    active_chord_result = chord(group(current_batch_signatures), callback_sig).apply_async()
                    logger.info(f"Orchestrator {self.request.id}: Batch chord {active_chord_result.id} launched for TR:{test_run_id}.")
                    current_batch_signatures = []

                    # Non-blocking wait for chord with checks. The orchestrator does not block here for each chord.
                    # It continues dispatching other chords if any.
                    # The final "wait for parallel progress" loop at the end handles ensuring all are done.
                    # If cancellation is needed, revoking the 'active_chord_result' can stop its callback.
                    # Revoking individual tasks in the group is more complex and usually not done from orchestrator
                    # unless it stores all sub-task IDs, which is feasible but adds more state.
        
        # --- Finalization ---
        if not test_run.run_serially:
            timeout_seconds = 180  # Max wait for parallel batches to report back
            sleep_interval = 5
            logger.info(f"Orchestrator {self.request.id}: Entering final wait loop for parallel progress on TR:{test_run_id}.")
            while timeout_seconds > 0:
                db.session.refresh(test_run)
                if test_run.progress_current >= test_run.progress_total:
                    logger.info(f"Orchestrator {self.request.id}: All parallel progress accounted for on TR:{test_run_id}.")
                    break
                
                current_db_status_final = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
                if self.is_revoked() or current_db_status_final == 'cancelling':
                    logger.warning(f"Orchestrator {self.request.id}: Revoked/Cancelled during final progress wait for TR:{test_run_id}.")
                    raise TaskRevokedError("Revoked/Cancelled during final progress wait")
                if current_db_status_final == 'pausing' or current_db_status_final == 'paused':
                     logger.info(f"Orchestrator {self.request.id}: Pause signal during final wait for TR:{test_run_id}. Holding.")
                     time.sleep(sleep_interval)
                     timeout_seconds -= sleep_interval # Still decrement timeout during pause
                     continue

                logger.info(f"Orchestrator {self.request.id}: Still waiting for parallel progress for TR:{test_run_id}. Have {test_run.progress_current}/{test_run.progress_total}. Timeout in {timeout_seconds}s")
                time.sleep(sleep_interval)
                timeout_seconds -= sleep_interval
            
            db.session.refresh(test_run)
            if test_run.progress_current < test_run.progress_total:
                logger.warning(f"Orchestrator {self.request.id}: WARNING - TR:{test_run_id} timed out waiting for full parallel progress. Reached {test_run.progress_current}/{test_run.progress_total}.")
                # If it times out, it will likely be marked 'failed' in the final status check.

        final_db_status_end = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
        if self.is_revoked() or final_db_status_end == 'cancelling':
            if final_db_status_end != 'cancelled': # Ensure it's not already marked 'cancelled' by another process
                db.session.query(TestRun).filter_by(id=test_run_id).update({'status': 'cancelled', 'end_time': datetime.utcnow()})
                db.session.commit()
            test_run.status = 'cancelled'
            emit_run_update(test_run_id, 'run_cancelled', test_run.get_status_data())
            logger.info(f"Orchestrator {self.request.id}: TR:{test_run_id} finalized as CANCELLED.")
            return {'status': 'CANCELLED'}
        else:
            # Check if all progress made, otherwise mark as failed if incomplete but not cancelled
            if test_run.progress_current < test_run.progress_total:
                logger.error(f"Orchestrator {self.request.id}: TR:{test_run_id} did not complete all test cases ({test_run.progress_current}/{test_run.progress_total}). Marking as FAILED.")
                test_run.status = 'failed'
            else:
                logger.info(f"Orchestrator {self.request.id}: TR:{test_run_id} all cases processed. Marking COMPLETED.")
                test_run.status = 'completed'
            
            test_run.end_time = datetime.utcnow()
            # Ensure progress_current reflects actual processed or total if completed
            if test_run.status == 'completed':
                test_run.progress_current = test_run.progress_total
            
            db.session.commit()
            emit_event_name = 'run_completed' if test_run.status == 'completed' else 'run_failed'
            emit_run_update(test_run_id, emit_event_name, test_run.get_status_data())
            return {'status': test_run.status.upper()}

    except (TaskRevokedError, SoftTimeLimitExceeded) as e_revoke:
        logger.warning(f"Orchestrator {self.request.id}: Task for TR:{test_run_id} REVOKED or TIMED OUT. Type: {type(e_revoke).__name__}")
        if test_run:
            current_status = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
            if current_status not in ['failed', 'completed', 'cancelled']:
                db.session.query(TestRun).filter_by(id=test_run_id).update({'status': 'cancelled', 'end_time': datetime.utcnow()})
                db.session.commit()
                test_run.status = 'cancelled'
                emit_run_update(test_run_id, 'run_cancelled', test_run.get_status_data())
        return {'status': 'REVOKED', 'reason': str(e_revoke)}

    except ValueError as ve:
        logger.error(f"Orchestrator {self.request.id}: ValueError for TR:{test_run_id}: {ve}", exc_info=True)
        if test_run:
            final_status_on_error = 'failed'
            if "cancel" in str(ve).lower():
                final_status_on_error = 'cancelled'
            
            current_status = db.session.query(TestRun.status).filter_by(id=test_run_id).scalar()
            if current_status not in ['failed', 'completed', 'cancelled']: # Avoid overwriting a more definitive state
                db.session.query(TestRun).filter_by(id=test_run_id).update({'status': final_status_on_error, 'end_time': datetime.utcnow()})
                db.session.commit()
                test_run.status = final_status_on_error
                emit_event = 'run_cancelled' if final_status_on_error == 'cancelled' else 'run_failed'
                emit_run_update(test_run_id, emit_event, test_run.get_status_data())
        return {'status': 'FAILED', 'reason': str(ve)}
        
    except Exception as e_general:
        logger.error(f"Orchestrator {self.request.id}: UNEXPECTED ERROR for TR:{test_run_id}: {e_general}", exc_info=True)
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
# This task now needs to create TestExecution records linked to a TestRunAttempt.
# The TestRunAttempt ID should be passed to it by the orchestrator.
@shared_task(bind=True, acks_late=True, name='tasks.execute_single_case')
def execute_single_test_case_task(self, test_run_attempt_id, test_case_id, endpoint_id, prompt_text):
    logger.info(f"SingleCaseTask {self.request.id}: AttID:{test_run_attempt_id}, TCID:{test_case_id}")
    execution = None # Initialize for broader scope
    try:
        # Fetch parent attempt to ensure it exists and for context if needed
        test_run_attempt = db.session.get(TestRunAttempt, test_run_attempt_id)
        test_case = db.session.get(TestCase, test_case_id)
        endpoint = db.session.get(Endpoint, endpoint_id)

        if not test_run_attempt:
            logger.error(f"SingleCaseTask {self.request.id}: TestRunAttempt {test_run_attempt_id} not found.")
            return {'status': 'FAILED', 'reason': f"Parent TestRunAttempt {test_run_attempt_id} not found", 'test_case_id': test_case_id}
        if not test_case:
            logger.error(f"SingleCaseTask {self.request.id}: TestCase {test_case_id} not found.")
            return {'status': 'FAILED', 'reason': f"TestCase {test_case_id} not found", 'test_case_id': test_case_id}
        if not endpoint:
            logger.error(f"SingleCaseTask {self.request.id}: Endpoint {endpoint_id} not found.")
            return {'status': 'FAILED', 'reason': f"Endpoint {endpoint_id} not found", 'test_case_id': test_case_id}

        # HTTP request logic
        payload = {"prompt": prompt_text} # Prompt_text is already transformed by orchestrator
        http_method = endpoint.http_method.upper() if endpoint.http_method else 'POST'
        headers = {h.key: h.value for h in endpoint.api_headers} if endpoint.api_headers else {}
        if 'Content-Type' not in headers and http_method in ['POST', 'PUT', 'PATCH']:
             headers['Content-Type'] = 'application/json'

        response_data, status_code, error_message = replay_post_request( # Using your replay_post_request
            hostname=endpoint.hostname, # Assuming replay_post_request takes hostname and path separately
            path=endpoint.endpoint, # Assuming replay_post_request takes hostname and path separately
            payload=payload, # It should handle json.dumps if necessary
            headers_str="\n".join(f"{k}: {v}" for k, v in headers.items()) # Assuming replay_post_request takes headers_str
        )
        disposition = 'pass' if status_code and 200 <= status_code < 300 else 'fail'

        # Create TestExecution record linked to the TestRunAttempt
        execution = TestExecution(
            test_run_attempt_id=test_run_attempt_id,
            test_case_id=test_case_id,
            prompt_sent=prompt_text,
            response_received=json.dumps(response_data) if response_data is not None else None,
            status_code=status_code,
            error_message=error_message,
            status=disposition, # TestExecution's status (disposition)
            started_at=datetime.utcnow(), # This task's start time
            finished_at=datetime.utcnow() # Mark finished immediately
        )
        db.session.add(execution)
        db.session.commit()
        logger.info(f"SingleCaseTask {self.request.id}: TestExecution {execution.id} created for Attempt:{test_run_attempt_id}, TC:{test_case_id} with status {disposition}.")
        return {'status': 'SUCCESS', 'execution_id': execution.id, 'test_case_id': test_case_id, 'disposition': disposition}

    except Exception as e_single:
        logger.error(f"SingleCaseTask {self.request.id}: Error for AttID:{test_run_attempt_id}, TC:{test_case_id}: {e_single}", exc_info=True)
        if db.session.is_active: # Check before rollback
             db.session.rollback()
        # We still need to return a dict that the orchestrator/chord callback can understand as a failure
        return {'status': 'FAILED', 'reason': str(e_single), 'test_case_id': test_case_id}
    finally:
        if db.session and db.session.is_active:
            db.session.remove()


# --- Callback Task for Parallel Batches ---
@shared_task(bind=True, name='tasks.handle_batch_completion')
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