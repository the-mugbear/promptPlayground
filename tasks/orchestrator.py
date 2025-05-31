# tasks/orchestrator.py
# Main orchestrator task for running test suites in parallel using a chain of chords

import time
import logging
from datetime import datetime
from typing import List, Tuple, Dict

from celery_app import celery
from celery import chain, chord, group

from extensions import db
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestSuite import TestSuite
from tasks.base import ContextTask
from tasks.helpers import with_session, emit_run_update
from tasks.case import execute_single_test_case
from tasks.batch import handle_batch_completion
from services.transformers.registry import apply_transformation
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)
logger.debug("Orchestrator: entering orchestrate()")

PARALLEL_BATCH_SIZE = 8

@celery.task(
    bind=True,
    acks_late=True,
    base=ContextTask,
    name='tasks.orchestrate_test_run'
)
@with_session
def orchestrate(self, run_id: int) -> Dict[str, str]:
    """
    Orchestrates a full test run: 1) load run with relationships,
    2) update status → commit, 3) spawn subtasks, 4) return.
    The decorator handles commit/remove automatically.
    """
    # 1) Load run eagerly so we can access filters / test_suites without detached errors
    run: TestRun = (
        db.session.query(TestRun)
        .options(
            selectinload(TestRun.filters),
            selectinload(TestRun.test_suites).selectinload(TestSuite.test_cases)
        )
        .get(run_id)
    )
    if not run:
        logger.error(f"Orchestrator: TestRun {run_id} not found.")
        return {'status': 'FAILED', 'reason': 'not found'}

    # 2) Initialize/Update run metadata in the same session
    run.celery_task_id = self.request.id
    run.start_time = datetime.utcnow()
    run.status = 'running'             # or use your enum: TestRunStatus.RUNNING
    run.progress_current = 0
    run.progress_total = _count_cases(run)

    # 3) Gather relationships into local lists now (while session is open)
    filter_list = list(run.filters)    # already loaded thanks to selectinload
    suite_list  = list(run.test_suites)

    # 4) Emit initial progress update
    emit_run_update(run_id, 'progress_update', run.get_status_data())

    # 5) Prepare run-level transformations
    run_level_tfm_configs = run.run_transformations or []
    if run_level_tfm_configs:
        logger.debug(f"Orchestrator: Run-level transforms: {run_level_tfm_configs}")

    # 6) Build prompt-filter configs
    prompt_filter_tfm_configs = []
    for filt_data in _serialize_filters(filter_list):
        prompt_filter_tfm_configs.append({
            "name": filt_data.get("type"),
            "params": filt_data.get("config", {})
        })
    if prompt_filter_tfm_configs:
        logger.debug(f"Orchestrator: Prompt-filter transformations: {prompt_filter_tfm_configs}")


    # 7) Build (case_id, prompt) list from suite_list
    cases: List[Tuple[int, str]] = [
        (tc.id, tc.prompt)
        for suite in suite_list
        for tc in suite.test_cases
    ]
    logger.info(f"Orchestrator: Found {len(cases)} test cases to execute for run {run_id}.")


    # 8) Create exactly one TestRunAttempt for this entire run execution
    attempt_id = _create_attempt(run_id)
    logger.debug(f"Orchestrator: Created TestRunAttempt ID={attempt_id} for run {run_id}.")

    # 9) Build all single-case signatures
    all_sigs = []
    for seq, (case_id, original_prompt) in enumerate(cases, start=1):
        if self.is_revoked():
            # If revoked, enqueue finalize_run with “cancelled” status and return
            finalize_run.delay(run_id, 'cancelled')
            return {'status': 'CANCELLED'}

        # Consolidate prompt through transformations
        current_prompt = original_prompt
        all_tfm_steps = []

        # Stage 1: run-level
        if run_level_tfm_configs:
            all_tfm_steps.extend(run_level_tfm_configs)

        # Stage 2: prompt filters
        if prompt_filter_tfm_configs:
            all_tfm_steps.extend(prompt_filter_tfm_configs)

        # Stage 3: case-specific
        case_specific_tfm_data = _get_case_transforms(case_id)
        if isinstance(case_specific_tfm_data, list):
            logger.debug(f"Orchestrator: Case {case_id} has {len(case_specific_tfm_data)} specific transforms")
            for case_tfm in case_specific_tfm_data:
                if isinstance(case_tfm, dict) and "name" in case_tfm:
                    all_tfm_steps.append({
                        "name": case_tfm["name"],
                        "params": case_tfm.get("params", {})
                    })
                elif isinstance(case_tfm, str):
                    all_tfm_steps.append({"name": case_tfm, "params": {}})

        # If no transforms at all, we’ll still push current_prompt = original_prompt
        if all_tfm_steps:
            logger.debug(f"Orchestrator: Case {case_id}, initial prompt: {original_prompt}")
        else:
            logger.debug(f"Orchestrator: Case {case_id} has no transformations; using original prompt.")

        # Apply transformations sequentially
        for tfm_config in all_tfm_steps:
            tfm_name = tfm_config.get("name")
            instance_params = tfm_config.get("params", {})
            logger.debug(
                f"Orchestrator: Applying transform '{tfm_name}' "
                f"with params {instance_params} on prompt '{current_prompt}'"
            )
            current_prompt = apply_transformation(
                t_id=tfm_name,
                prompt=current_prompt,
                params=instance_params
            )
            logger.debug(f"Orchestrator: New prompt after '{tfm_name}': '{current_prompt}'")

        logger.debug(
            f"Orchestrator: about to schedule execute_single_test_case with "
            f"(attempt_id={attempt_id}, case_id={case_id}, endpoint_id={run.endpoint_id}, "
            f"prompt_text='{current_prompt}', sequence_num={seq})"
        )

        # Build the signature for execute_single_test_case
        sig = execute_single_test_case.s(
            attempt_id,             # → test_run_attempt_id
            case_id,                # → test_case_id
            run.endpoint_id,        # → endpoint_id
            current_prompt,         # → prompt_text
            seq                     # → sequence_num
        )
        all_sigs.append(sig)

    # 10) Chunk into batches and build chords
    batches = [
        all_sigs[i:i + PARALLEL_BATCH_SIZE]
        for i in range(0, len(all_sigs), PARALLEL_BATCH_SIZE)
    ]
    batch_chords = [
        chord(
            group(batch),
            handle_batch_completion.s(
                test_run_id=run_id,
                num_cases_in_batch=len(batch)
            )
        ).set(immutable=True)
        for batch in batches
    ]

    # 11) Chain the batch chords and finalize at the end (immutable signature for finalize)
    workflow = chain(
        *batch_chords,
        finalize_run.si(run_id, 'completed')
    )
    workflow.apply_async()

    # 12) Return. @with_session will commit everything and remove the session here.
    return {'status': 'PENDING'}

# Single finalize callback for both completed and cancelled
@celery.task(
    bind=True,
    base=ContextTask,
    name='tasks.finalize_run'
)
@with_session
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
    emit_run_update(run_id,
                    'run_completed' if final_status == 'completed' else 'run_cancelled',
                    run.get_status_data())


# --- Helper functions ---
def _count_cases(run: TestRun) -> int:
    return sum(len(suite.test_cases) for suite in run.test_suites)

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

def _get_case_transforms(case_id: int) -> List[Dict]:
    from models.model_TestCase import TestCase
    tc = db.session.get(TestCase, case_id)
    return getattr(tc, 'transformations', []) or []

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
    db.session.flush()
    return attempt.id

