# tasks/orchestrator.py
# Main orchestrator task for running test suites in parallel using a chain of chords

import time
import logging
from datetime import datetime
from typing import List, Tuple, Dict

from celery_app import celery
from celery import chain, chord, group

from tasks.base import ContextTask, with_session
from extensions import db
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt
from tasks.helpers import emit_run_update, apply_transformations
from tasks.case import execute_single_test_case
from tasks.batch import handle_batch_completion

logger = logging.getLogger(__name__)

PARALLEL_BATCH_SIZE = 8

@celery.task(
    bind=True,
    acks_late=True,
    base=ContextTask,
    name='tasks.orchestrate_test_run'
)
def orchestrate(self, run_id: int) -> Dict[str, str]:
    """
    Orchestrates a full test run by chaining batch chords sequentially,
    and finalizing the run in a single callback with the appropriate status.
    """
    # Load run
    run = db.session.get(TestRun, run_id)
    if not run:
        logger.error(f"Orchestrator: TestRun {run_id} not found.")
        return {'status': 'FAILED', 'reason': 'not found'}

    # Initialize run metadata
    run.celery_task_id = self.request.id
    run.start_time = datetime.utcnow()
    run.status = 'running'
    run.progress_current = 0
    run.progress_total = _count_cases(run)
    db.session.commit()
    db.session.expunge_all()
    db.session.remove()

    emit_run_update(run_id, 'progress_update', run.get_status_data())

    # Prepare transformations and case list
    run_filters = _serialize_filters(run.filters)
    cases: List[Tuple[int, str]] = [
        (tc.id, tc.prompt)
        for suite in run.test_suites
        for tc in suite.test_cases
    ]

    # Build all single-case signatures
    all_sigs = []
    for seq, (case_id, prompt) in enumerate(cases, start=1):
        if self.is_revoked():
            # If cancelled before scheduling, finalize immediately
            finalize_run.delay(run_id, 'cancelled')
            return {'status': 'CANCELLED'}

        transforms = run_filters + _get_case_transforms(case_id)
        processed = apply_transformations(prompt, transforms)
        attempt_id = _create_attempt(run_id)

        sig = execute_single_test_case.s(
            test_run_attempt_id=attempt_id,
            test_case_id=case_id,
            endpoint_id=run.endpoint_id,
            prompt_text=processed,
            sequence_num=seq
        )
        all_sigs.append(sig)

    # Chunk into batches
    batches = [all_sigs[i:i + PARALLEL_BATCH_SIZE]
               for i in range(0, len(all_sigs), PARALLEL_BATCH_SIZE)]

    # Convert to chord signatures
    batch_chords = [
        chord(
            group(batch),
            handle_batch_completion.s(test_run_id=run_id, num_cases_in_batch=len(batch))
        ) for batch in batches
    ]

    # Chain chords and finalize with a single callback
    workflow = chain(
        *batch_chords,
        finalize_run.s(run_id, 'completed')
    )
    workflow.apply_async()

    # 🔥 ensure the orchestrator itself returns its DB connection
    db.session.expunge_all()
    db.session.remove()

    return {'status': 'PENDING'}


# Single finalize callback for both completed and cancelled
@celery.task(
    bind=True,
    base=ContextTask,
    name='tasks.finalize_run'
)
def finalize_run(self, run_id: int, final_status: str):
    """
    Finalize the TestRun with the given status ('completed' or 'cancelled').
    Emits the corresponding SocketIO event.
    """
    run = db.session.get(TestRun, run_id)
    if not run:
        logger.error(f"Finalize: TestRun {run_id} not found.")
        return

    run.status = final_status
    run.end_time = datetime.utcnow()
    db.session.commit()
    db.session.expunge_all()
    db.session.remove()

    event = 'run_completed' if final_status == 'completed' else 'run_cancelled'
    emit_run_update(run_id, event, run.get_status_data())


# --- Helper functions ---

@with_session
def _count_cases(run: TestRun) -> int:
    return sum(len(suite.test_cases) for suite in run.test_suites)

@with_session
def _serialize_filters(filters) -> List[Dict]:
    if not filters:
        return []
    return [
        {
            'type': pf.name,
            'config': {
                'invalid_characters': pf.invalid_characters,
                'words_to_replace': pf.words_to_replace
            }
        }
        for pf in filters
    ]

@with_session
def _get_case_transforms(case_id: int) -> List[Dict]:
    from models.model_TestCase import TestCase
    tc = db.session.get(TestCase, case_id)
    return getattr(tc, 'transformations', []) or []

@with_session
def _create_attempt(run_id: int) -> int:
    latest = (
        db.session.query(TestRunAttempt.attempt_number)
        .filter_by(test_run_id=run_id)
        .order_by(TestRunAttempt.attempt_number.desc())
        .first()
    )
    next_num = (latest[0] if latest else 0) + 1
    attempt = TestRunAttempt(
        test_run_id=run_id,
        attempt_number=next_num,
        status='running',
        started_at=datetime.utcnow()
    )
    db.session.add(attempt)
    db.session.commit()
    db.session.expunge_all()
    db.session.remove()
    return attempt.id

