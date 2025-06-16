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
            selectinload(TestRun.endpoint) # Eagerly load endpoint if not already
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
    
    # 3) Gather cases and multiply by iterations
    suite_list = list(run.test_suites)
    base_cases = [
        (tc.id, tc.prompt) 
        for suite in suite_list
        for tc in suite.test_cases
    ]
    
    # Multiply cases by iterations to create multiple executions per case
    cases_to_process: List[Tuple[int, str, int]] = [  # (case_id, original_prompt, iteration_number)
        (case_id, prompt, iteration)
        for case_id, prompt in base_cases
        for iteration in range(1, run.iterations + 1)
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

    for seq, (case_id, _, iteration) in enumerate(cases_to_process, start=1): # original_prompt from cases_to_process is ignored with _
        if self.is_revoked():
            logger.warning(f"Orchestrator TR_ID:{run_id}: Task revoked.")
            finalize_run.delay(run_id, 'cancelled') # As in your orchestrator.py
            return {'status': 'CANCELLED'}

        logger.debug(
            f"Orchestrator TR_ID:{run_id}: Creating signature for TC_ID:{case_id}, Seq:{seq}, "
            f"Iteration:{iteration} with AttemptID:{attempt_id}."
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
            sequence_num=seq,
            iteration_num=iteration
        )
        all_sigs.append(sig)
    
    logger.info(f"Orchestrator TR_ID:{run_id}: Finished building {len(all_sigs)} lightweight signatures in {time.time() - loop_start_time:.4f}s.")

    if not all_sigs:
        logger.error(f"Orchestrator TR_ID:{run_id}: No signatures generated. Aborting.")
        # Finalize run status appropriately
        return {'status': 'ERROR', 'message': 'No signatures generated.'}
    
    # In orchestrate(), after all_sigs is populated:
    if all_sigs:
        # Create a group of all the individual test case execution signatures
        test_case_group = group(all_sigs)
        
        # Create a signature for the finalize_run task that will run after the group completes.
        # .s() creates a signature. Using .si() for immutable signature is also an option
        # if finalize_run doesn't need results from the group.
        # finalize_run(self, run_id: int, final_status: str)
        finalization_sig = finalize_run.s(run_id=run_id, final_status='completed')

        # Create a workflow: first the group of test cases, then the finalization task.
        # The pipe operator `|` chains them, so finalization_sig runs after test_case_group.
        diagnostic_workflow_with_callback = (test_case_group | finalization_sig)
        
        logger.info(f"DIAGNOSTIC: Attempting to submit simple group of {len(all_sigs)} tasks with a finalization callback...")
        try:
            # Apply the workflow asynchronously
            task_chain_result = diagnostic_workflow_with_callback.apply_async()
            
            logger.info(f"DIAGNOSTIC: Simple group with callback submitted. Workflow (Group) ID: {task_chain_result.id}")
            # The task_chain_result.id here will be the ID of the group.
            # The orchestrate task returns. The actual run finalization happens when the callback runs.
            return {'status': 'PENDING_DIAGNOSTIC_GROUP_WITH_CALLBACK', 'workflow_id': task_chain_result.id}
            
        except Exception as e_submit:
            logger.error(f"DIAGNOSTIC: Failed to submit simple group with callback: {e_submit}", exc_info=True)
            # If submission fails, you might want to update the TestRun status to 'error' or 'failed_to_submit' here.
            # _finalize_run_status(run_id, 'failed_to_submit', db.session, f"Diagnostic group submission error: {e_submit}")
            return {'status': 'ERROR', 'message': f'Failed diagnostic group submission with callback: {e_submit}'}
    else:
        logger.error(f"Orchestrator TR_ID:{run_id}: No signatures generated. Aborting.")
        _finalize_run_status(run_id, 'completed_with_no_cases', db.session, "No signatures generated.") # Example using your helper
        return {'status': 'ERROR', 'message': 'No signatures generated.'}

# Make sure finalize_run task is correctly defined in this file, as you have it:
@celery.task(
    bind=True,
    base=ContextTask,
    name='tasks.finalize_run'
)
@with_session
def finalize_run(self, results_from_group, run_id: int, final_status: str): # Added results_from_group
    """
    Finalize the TestRun with the given status ('completed' or 'failed').
    This runs after all tasks in the preceding group have finished.
    'results_from_group' will contain the return values of all tasks in the group.
    """
    logger.info(f"FinalizeRunTask TR_ID:{run_id}, TaskID:{self.request.id}: Group completed. Marking run as '{final_status}'.")
    logger.debug(f"FinalizeRunTask TR_ID:{run_id}: Received {len(results_from_group) if results_from_group else 0} results from the preceding group.")

    run = db.session.get(TestRun, run_id)
    if not run:
        logger.error(f"FinalizeRunTask TR_ID:{run_id}: TestRun not found.")
        return {'status': 'FAILED', 'reason': 'Run not found'}

    run.status = final_status
    run.completed_at = datetime.utcnow() # Use completed_at as per your model
    
    # Ensure progress_current is capped at progress_total, especially if some tasks failed
    # but the group is considered "complete" for the callback to run.
    # If individual tasks update progress, this might just be a final check.
    if final_status == 'completed' and run.progress_total > 0:
        # You could query the actual number of successful TestExecution records
        # to set progress_current accurately, or assume all were attempted.
        # For now, setting to total if 'completed'.
        run.progress_current = run.progress_total
        logger.info(f"FinalizeRunTask TR_ID:{run_id}: Progress set to {run.progress_current}/{run.progress_total}.")


    # @with_session handles commit
    emit_run_update(run_id, 
                    'run_completed' if final_status == 'completed' else 'run_failed', # Or a more specific event
                    run.get_status_data())
    logger.info(f"FinalizeRunTask TR_ID:{run_id}: Run finalized and update emitted.")
    return {'status': 'SUCCESS', 'run_id': run_id, 'final_status': final_status}



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


