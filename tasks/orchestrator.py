# tasks/orchestrator.py
# Main orchestrator task for running test suites in parallel

import time
import logging
from datetime import datetime
from typing import List, Tuple, Dict

from celery_app import celery
from celery import group, chord, chain

from extensions import db
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestSuite import TestSuite
from tasks.base import ContextTask
from tasks.helpers import with_session, emit_run_update
from tasks.case import execute_single_test_case
from services.transformers.registry import apply_transformation
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import func

from tasks.batch import handle_batch_completion

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
    # 1) Load run eagerly (as in your existing orchestrator.py)
    run: TestRun = (
        db.session.query(TestRun)
        .options(
            selectinload(TestRun.filters), # For the new helper function access later
            selectinload(TestRun.test_suites).selectinload(TestSuite.test_cases),
            joinedload(TestRun.endpoint) # Eagerly load endpoint if not already
        )
        .get(run_id)
    )
    if not run:
        logger.error(f"Orchestrator TR_ID:{run_id}: TestRun not found.")
        return {'status': 'FAILED', 'reason': 'not found'}

    # Ensure endpoint is loaded, critical for later use in execute_single_test_case
    if not run.endpoint:
         logger.error(f"Orchestrator TR_ID:{run_id}: TestRun has no associated endpoint. Aborting.")
         # You might want a specific _finalize_run_status call here
         return {'status': 'ERROR', 'message': 'TestRun has no endpoint.'}

    # 2) Initialize/Update run metadata (as in your existing orchestrator.py)
    run.celery_task_id = self.request.id
    run.start_time = datetime.utcnow()
    run.status = 'running'
    run.progress_current = 0
    
    # 3) Gather cases (as in your existing orchestrator.py)
    suite_list  = list(run.test_suites)
    cases_to_process: List[Tuple[int, str]] = [ # We get (case_id, original_prompt)
        (tc.id, tc.prompt) 
        for suite in suite_list
        for tc in suite.test_cases
    ]
    run.progress_total = len(cases_to_process)
    
    if run.progress_total == 0:
        logger.warning(f"Orchestrator TR_ID:{run_id}: No test cases found.")
        # Finalize appropriately
        return {'status': 'SUCCESS', 'message': 'No test cases to execute.'}

    # 4) Emit initial progress update (as in your existing orchestrator.py)
    emit_run_update(run_id, 'progress_update', run.get_status_data())

    # 5) Create TestRunAttempt (as in your existing orchestrator.py)
    attempt_id = _create_attempt(run_id, db.session) 
    logger.info(f"Orchestrator TR_ID:{run_id}: Created TestRunAttempt ID={attempt_id}.")

    # --- Build lightweight signatures ---
    all_sigs = []
    logger.info(f"Orchestrator TR_ID:{run_id}: Starting to build {len(cases_to_process)} lightweight signatures...")
    loop_start_time = time.time()

    for seq, (case_id, _) in enumerate(cases_to_process, start=1): # original_prompt from cases_to_process is ignored with _
        if self.is_revoked():
            logger.warning(f"Orchestrator TR_ID:{run_id}: Task revoked.")
            finalize_run.delay(run_id, 'cancelled') # As in your orchestrator.py
            return {'status': 'CANCELLED'}

        logger.debug(
            f"Orchestrator TR_ID:{run_id}: Creating signature for TC_ID:{case_id}, Seq:{seq} "
            f"with AttemptID:{attempt_id}."
        )

        # fetch the endpoint_id from run.endpoint.id (or however you store it)
        endpoint_obj = run.endpoint
        if not endpoint_obj:
            logger.error(f"Orchestrator TR_ID:{run_id}: Missing endpoint, cannot build child sig.")
            return {'status': 'ERROR', 'message': 'No endpoint'}

        sig = execute_single_test_case.s(
            test_run_attempt_id=attempt_id,
            test_case_id=case_id,
            endpoint_id=endpoint_obj.id,   
            test_run_id=run_id,            
            sequence_num=seq
        )
        all_sigs.append(sig)
    
    logger.info(f"Orchestrator TR_ID:{run_id}: Finished building {len(all_sigs)} lightweight signatures in {time.time() - loop_start_time:.4f}s.")

    if not all_sigs:
        logger.error(f"Orchestrator TR_ID:{run_id}: No signatures generated. Aborting.")
        # Finalize run status appropriately
        return {'status': 'ERROR', 'message': 'No signatures generated.'}
    
    # In orchestrate(), after all_sigs is populated:
    if all_sigs:
        diagnostic_workflow = group(all_sigs)
        logger.info(f"DIAGNOSTIC: Attempting to submit simple group of {len(all_sigs)} tasks...")
        try:
            task_chain_result = diagnostic_workflow.apply_async()
            logger.info(f"DIAGNOSTIC: Simple group submitted. Workflow ID: {task_chain_result.id}")
            return {'status': 'PENDING_DIAGNOSTIC_GROUP', 'workflow_id': task_chain_result.id}
        except Exception as e_submit:
            logger.error(f"DIAGNOSTIC: Failed to submit simple group: {e_submit}", exc_info=True)
            return {'status': 'ERROR', 'message': 'Failed diagnostic group submission'}
    # (Comment out the original batch_chords/workflow/apply_async logic for this test)

    # # 10) Chunk into batches and build chords (as in your existing orchestrator.py)
    # batches = [
    #     all_sigs[i:i + PARALLEL_BATCH_SIZE]
    #     for i in range(0, len(all_sigs), PARALLEL_BATCH_SIZE)
    # ]
    # if not batches: # Should be caught by 'if not all_sigs' but defensive
    #     logger.error(f"Orchestrator TR_ID:{run_id}: No batches created despite having signatures. Aborting.")
    #     return {'status': 'ERROR', 'message': 'Batch creation failed.'}

    # batch_chords = [
    #     chord(
    #         group(batch_task_list), # Renamed 'batch' to 'batch_task_list' for clarity
    #         handle_batch_completion.s(
    #             test_run_id=run_id, # Keep this for the callback
    #             num_cases_in_batch=len(batch_task_list)
    #         )
    #     ).set(immutable=True) # As in your orchestrator.py
    #     for batch_task_list in batches
    # ]

    # # 11) Chain the batch chords and finalize (as in your existing orchestrator.py)
    # workflow = chain(
    #     *batch_chords,
    #     finalize_run.si(run_id, 'completed') # Immutable signature for finalize_run
    # )
    
    # logger.info(f"Orchestrator TR_ID:{run_id}: Attempting to submit lightweight task chain...")
    # apply_async_start_time = time.time()
    # try:
    #     task_chain_result = workflow.apply_async()
    #     logger.info(f"Orchestrator TR_ID:{run_id}: Lightweight task chain submitted in {time.time() - apply_async_start_time:.4f}s. Workflow ID: {task_chain_result.id}")
    #     # Optionally, store task_chain_result.id on the run model if you want to track the workflow ID
    #     # run.celery_workflow_id = task_chain_result.id 
    # except Exception as e_submit:
    #     logger.error(f"Orchestrator TR_ID:{run_id}: Failed to submit lightweight task chain: {e_submit}", exc_info=True)
    #     # Finalize run status to 'failed_to_submit' or 'error'
    #     return {'status': 'ERROR', 'message': f'Failed to submit task chain: {e_submit}'}

    # 12) Return (as in your existing orchestrator.py)
    return {'status': 'PENDING', 'workflow_id': task_chain_result.id} # Workflow ID is good to return

# Keep your finalize_run, _count_cases, _serialize_filters, _get_case_transforms (if still used elsewhere, though likely not for this flow), _create_attempt helpers
# Note: _get_case_transforms was confirmed for a removed feature.
# _serialize_filters might still be used for logging in your orchestrator.py if you had it separate from prompt processing.

# Single finalize callback for both completed and cancelled
@celery.task(
    bind=True,
    base=ContextTask,
    name='tasks.finalize_run'
)
@with_session
def finalize_run(self, run_id: int, final_status: str):
    """
    After all batch groups have finished, mark the run as completed (or failed),
    cap progress_current, and emit a final 'run_completed' event.
    """
    logger.info(f"FinalizeRunTask TR_ID:{run_id}, TaskID:{self.request.id}: Marking run as '{final_status}'.")
    run = db.session.get(TestRun, run_id)
    if not run:
        logger.error(f"FinalizeRunTask TR_ID:{run_id}: TestRun not found.")
        return {'status': 'FAILED', 'reason': 'Run not found'}

    run.status = final_status
    run.completed_at = datetime.utcnow()
    # If we somehow under‐ or overshot, cap progress_current at progress_total
    if final_status == 'completed' and run.progress_total:
        run.progress_current = run.progress_total

    db.session.flush()
    emit_run_update(run_id, 'run_completed', run.get_status_data())
    logger.info(f"FinalizeRunTask TR_ID:{run_id}: Emit final run_completed event.")
    return {'status': 'SUCCESS', 'run_id': run_id}


# --- Helper functions ---
def _count_cases(run: TestRun) -> int:
    # Recalculate based on eager-loaded data
    count = 0
    if run.test_suites:
        for suite in run.test_suites:
            if suite.test_cases:
                count += len(suite.test_cases)
    return count

def _serialize_filters(filters_list: List) -> List[Dict]: # Type hint for clarity
    # 'filters_list' now directly contains PromptFilter ORM objects
    if not filters_list:
        return []
    return [
        {
            'type': pf.name, # Assuming PromptFilter model has a 'name'
            'config': { # Assuming config structure matches your needs
                'invalid_characters': pf.invalid_characters,
                'words_to_replace': pf.words_to_replace # This should be a dict if JSONB
            }
        }
        for pf in filters_list 
    ]

def _create_attempt(run_id: int, session) -> int: 
    # Find the maximum existing attempt_number for this run_id
    latest_attempt_num_tuple = (
        session.query(func.max(TestRunAttempt.attempt_number))
        .filter_by(test_run_id=run_id)
        .one_or_none() # Returns (max_val,) or (None,)
    )
    
    next_attempt_num = 1
    if latest_attempt_num_tuple and latest_attempt_num_tuple[0] is not None:
        next_attempt_num = latest_attempt_num_tuple[0] + 1
    
    new_attempt = TestRunAttempt(
        test_run_id=run_id,
        attempt_number=next_attempt_num,
        status='running', # Initial status for the attempt
        started_at=datetime.utcnow()
    )
    session.add(new_attempt)
    session.flush() # Flush to get the ID for the new_attempt if needed before commit
    # Commit is handled by @with_session for the orchestrate task
    return new_attempt.id 

def _finalize_run_status(run_id: int, final_status: str, session, message: str = None):
    # This is a simplified version if finalize_run task handles the main logic.
    # This can be used by the orchestrator for early exits (e.g. no cases, errors before chain submission)
    logger.info(f"Orchestrator TR_ID:{run_id}: Finalizing run early with status '{final_status}'. Message: {message}")
    run = session.get(TestRun, run_id)
    if not run:
        logger.error(f"Orchestrator TR_ID:{run_id}: Cannot finalize. TestRun {run_id} not found.")
        return

    run.status = final_status
    run.end_time = datetime.utcnow()
    if message:
        run.notes = f"{(run.notes + '; ' if run.notes else '')}Orchestrator: {message}"

    if final_status == 'completed_with_no_cases':
        run.progress_current = 0
        run.progress_total = 0
        emit_event_name = 'run_completed' # Or a specific 'run_empty' event
    elif final_status == 'failed_to_submit' or final_status == 'error':
        emit_event_name = 'run_failed'
    else: # e.g. 'cancelled'
        emit_event_name = 'run_cancelled'
    
    # The @with_session decorator on 'orchestrate' will commit this.
    emit_run_update(run_id, emit_event_name, run.get_status_data())
    logger.info(f"Orchestrator TR_ID:{run_id}: Run status set to '{final_status}' and update emitted.")


