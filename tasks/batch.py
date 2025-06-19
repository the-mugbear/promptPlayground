# tasks/batch.py
# Callback task for parallel batch completion

import logging
from celery_app import celery
from tasks.base import ContextTask
from extensions import db
from models.model_TestRun import TestRun
from models.model_ExecutionSession import ExecutionSession
from .helpers import emit_run_update, with_session

logger = logging.getLogger(__name__)

@celery.task(
    bind=True,
    acks_late=True,
    base=ContextTask,
    name='tasks.handle_batch_completion'
)
@with_session
def handle_batch_completion(self, results, test_run_id, num_cases_in_batch):
    """
    Celery callback that runs after each parallel batch completes,
    updates the execution session progress,
    and emits a progress_update event.
    """
    logger.info(f"BatchCallback {self.request.id}: TR:{test_run_id}. "
                f"BatchSize:{num_cases_in_batch}. ResultsRcvd:{len(results)}")

    # Load the TestRun in its own session context
    test_run = db.session.get(TestRun, test_run_id)
    if not test_run:
        logger.error(f"BatchCallback {self.request.id}: TR:{test_run_id} NOT FOUND.")
        return {'status': 'FAILED', 'reason': 'TestRun not found'}

    try:
        # Get the latest execution session for this test run
        latest_session = test_run.latest_execution_session
        if not latest_session:
            logger.warning(f"BatchCallback {self.request.id}: No execution session found for TR:{test_run_id}.")
            return {'status': 'FAILED', 'reason': 'No execution session found'}

        # Atomically increment progress_current in the execution session
        updated_count = (
            db.session
            .query(ExecutionSession)
            .filter_by(id=latest_session.id)
            .update(
                {ExecutionSession.progress_current: ExecutionSession.progress_current + num_cases_in_batch},
                synchronize_session=False
            )
        )
        if updated_count == 0:
            logger.warning(
                f"BatchCallback {self.request.id}: No rows updated for session {latest_session.id}."
            )

        # Refresh to get the latest values
        db.session.refresh(latest_session)

        # Cap at total if we overshot
        if latest_session.progress_current > latest_session.progress_total:
            logger.warning(
                f"BatchCallback {self.request.id}: Capping over-increment for session {latest_session.id}. "
                f"From {latest_session.progress_current} to {latest_session.progress_total}"
            )
            (
                db.session
                .query(ExecutionSession)
                .filter_by(id=latest_session.id)
                .update(
                    {ExecutionSession.progress_current: latest_session.progress_total},
                    synchronize_session=False
                )
            )
            # Refresh again
            db.session.refresh(latest_session)

        logger.info(
            f"BatchCallback {self.request.id}: Updated session {latest_session.id} to "
            f"{latest_session.progress_current}/{latest_session.progress_total}."
        )

        # Emit a WebSocket update now that test_run is session‐bound
        emit_run_update(
            test_run_id,
            'progress_update',
            test_run.get_status_data()
        )

        # Return success
        return {
            'status': 'SUCCESS',
            'updated_progress': latest_session.progress_current,
            'session_id': latest_session.id
        }

    except Exception as e:
        logger.error(
            f"BatchCallback {self.request.id}: Error for TR:{test_run_id}: {e}",
            exc_info=True
        )
        # Even on error, emit last known state. test_run is still session‐bound here.
        emit_run_update(
            test_run_id,
            'progress_update',
            test_run.get_status_data()
        )
        # Returning or re‐raising will cause @with_session to roll back and then remove()
        return {'status': 'FAILED', 'reason': str(e)}