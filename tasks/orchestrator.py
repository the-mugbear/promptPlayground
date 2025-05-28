# tasks/orchestrator.py
# Main orchestrator task for running test suites in parallel using a chain of chords

import time
import logging
from datetime import datetime
from typing import List, Tuple, Dict

from celery_app import celery
from celery import chain, chord, group
from sqlalchemy.orm import joinedload # Added for eager loading

from tasks.base import ContextTask, with_session
from extensions import db
from models.model_TestRun import TestRun
from models.model_TestSuite import TestSuite # Import TestSuite for subqueryload
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
    # Load run with eager loading
    run = db.session.query(TestRun).options(
        joinedload(TestRun.filters),
        joinedload(TestRun.test_suites).subqueryload(TestSuite.test_cases)
    ).get(run_id)

    if not run:
        logger.error(f"Orchestrator: TestRun {run_id} not found.")
        return {'status': 'FAILED', 'reason': 'not found'}

    # Pre-calculate and serialize data while session is active and objects loaded
    run_filters_list_of_dicts = _serialize_filters(run.filters) # Uses eagerly loaded filters
    current_progress_total = _count_cases(run) # Uses eagerly loaded test_suites.test_cases
    
    # Pre-generate case data. Note: This still might trigger _get_case_transforms later if not optimized.
    # However, the main prompt is accessed here.
    cases_list_comprehension_data: List[Tuple[int, str, int]] = [ # Added endpoint_id
        (tc.id, tc.prompt, run.endpoint_id) # Access endpoint_id while run is in session
        for suite in run.test_suites
        for tc in suite.test_cases
    ]
    
    # Assuming get_status_data() primarily uses run attributes or already loaded relations
    status_data_for_emit = run.get_status_data()


    # Initialize/Update run metadata
    run.celery_task_id = self.request.id
    run.start_time = datetime.utcnow()
    run.status = 'running'
    run.progress_current = 0
    run.progress_total = current_progress_total # Use pre-calculated total

    db.session.commit()
    db.session.expunge_all() # Expunge after commit, before detaching or emitting
    db.session.remove()     # Remove session as per original logic after initial setup

    # Emit progress update using pre-prepared data
    emit_run_update(run_id, 'progress_update', status_data_for_emit)


    # Build all single-case signatures using pre-generated data
    all_sigs = []
    for seq, (case_id, prompt, endpoint_id_val) in enumerate(cases_list_comprehension_data, start=1):
        if self.is_revoked():
            # If cancelled before scheduling, finalize immediately
            # Note: finalize_run is a Celery task, will use its own session.
            finalize_run.delay(run_id, 'cancelled')
            return {'status': 'CANCELLED'}

        # _get_case_transforms still needs a session if tc.transformations is lazy.
        # This is a known limitation unless _get_case_transforms is also refactored or transformations are eager-loaded too.
        # For now, it will create its own session via @with_session.
        case_specific_transforms = _get_case_transforms(case_id) 
        transforms = run_filters_list_of_dicts + case_specific_transforms
        
        processed = apply_transformations(prompt, transforms)
        
        # _create_attempt creates a new session via @with_session
        attempt_id = _create_attempt(run_id) 

        sig = execute_single_test_case.s(
            test_run_attempt_id=attempt_id,
            test_case_id=case_id,
            endpoint_id=endpoint_id_val, # Use pre-fetched endpoint_id
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
        finalize_run.s(run_id, 'completed') # finalize_run uses its own session via ContextTask
    )
    workflow.apply_async()

    # Rely on ContextTask for final session cleanup of the orchestrate task itself.
    # The previous db.session.expunge_all() and db.session.remove() after commit handled the setup phase.
    # No further session management needed here for the main task block.

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

    # Override final_status if the run was marked as 'cancelling'
    if run.status == 'cancelling':
        final_status = 'cancelled'
        logger.info(f"Finalize: TestRun {run_id} was 'cancelling', overriding final_status to 'cancelled'.")

    run.status = final_status
    run.end_time = datetime.utcnow()
    db.session.commit()
    db.session.expunge_all()
    db.session.remove()

    event = 'run_completed' if final_status == 'completed' else 'run_cancelled'
    emit_run_update(run_id, event, run.get_status_data())


# --- Helper functions ---

# @with_session # No longer needed if 'run' and its relationships are eagerly loaded
def _count_cases(run: TestRun) -> int:
    # Assumes run.test_suites and suite.test_cases are eagerly loaded
    return sum(len(suite.test_cases) for suite in run.test_suites if suite.test_cases)

# @with_session # No longer needed if 'run.filters' is eagerly loaded
def _serialize_filters(filters_list) -> List[Dict]: # Renamed 'filters' to 'filters_list' for clarity
    if not filters_list:
        return []
    # Assumes 'filters_list' (run.filters) is eagerly loaded
    return [
        {
            'type': pf.name,
            'config': {
                'invalid_characters': pf.invalid_characters,
                'words_to_replace': pf.words_to_replace
            }
        }
        for pf in filters_list
    ]

# _get_case_transforms still uses @with_session as TestCase objects are not part of the initial eager load of TestRun
@with_session
def _get_case_transforms(case_id: int) -> List[Dict]:
    from models.model_TestCase import TestCase
    tc = db.session.get(TestCase, case_id)
    return getattr(tc, 'transformations', []) or []

@with_session
def _create_attempt(run_id: int) -> int: # This function is called per case, needs its own session management.
    # The @with_session decorator handles session setup and teardown for this specific operation.
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
        status='running', # Consider if this status is final or should be updated by case task
        started_at=datetime.utcnow()
    )
    db.session.add(attempt)
    db.session.commit()
    # db.session.expunge_all() # Not strictly necessary here as session is scoped to this function by @with_session
    # db.session.remove() # Also handled by @with_session
    return attempt.id

# Added a note to TestRun.get_status_data in models/model_TestRun.py if it needs adjustment for eager loading.
# Assuming TestRun.get_status_data can accept pre-calculated total or is efficient.
# For this refactor, I'll assume it can take `eagerly_loaded_total` as an argument.
# If not, it would need to be:
# status_data_for_emit = run.get_status_data()
# run.progress_total = status_data_for_emit['progress_total'] # if get_status_data recalculates

