# tasks/batch.py
# Callback task for parallel batch completion

import logging
from celery_app import celery
from tasks.base import ContextTask
from extensions import db
from models.model_TestRun import TestRun
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
    increments the TestRun.progress_current by the batch size,
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
        # Atomically increment progress_current
        updated_count = (
            db.session
            .query(TestRun)
            .filter_by(id=test_run_id)
            .update(
                {TestRun.progress_current: TestRun.progress_current + num_cases_in_batch},
                synchronize_session=False
            )
        )
        if updated_count == 0:
            logger.warning(
                f"BatchCallback {self.request.id}: No rows updated for TR:{test_run_id}."
            )

        # Refresh to get the latest values into session‐bound test_run
        db.session.refresh(test_run)

        # Cap at total if we overshot
        if test_run.progress_current > test_run.progress_total:
            logger.warning(
                f"BatchCallback {self.request.id}: Capping over-increment for TR:{test_run_id}. "
                f"From {test_run.progress_current} to {test_run.progress_total}"
            )
            (
                db.session
                .query(TestRun)
                .filter_by(id=test_run_id)
                .update(
                    {TestRun.progress_current: test_run.progress_total},
                    synchronize_session=False
                )
            )
            # Refresh again into session
            db.session.refresh(test_run)

        logger.info(
            f"BatchCallback {self.request.id}: Updated TR:{test_run_id} to "
            f"{test_run.progress_current}/{test_run.progress_total}."
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
            'updated_progress': test_run.progress_current
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