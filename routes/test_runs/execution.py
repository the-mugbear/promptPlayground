"""
Test run execution operations for managing the execution of test runs.
This module handles the execution of test runs, including task dispatching and attempt management.
"""

from flask import redirect, url_for, flash
from flask_login import login_required
from extensions import db
from sqlalchemy.orm import selectinload
from celery import chain, group
from celery_app import celery
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestExecution import TestExecution
from models.model_Endpoints import Endpoint
from services.common.header_parser_service import headers_from_apiheader_list
from . import test_runs_bp

@test_runs_bp.route('/<int:run_id>/execute', methods=['POST'])
@login_required
def execute_test_run(run_id):
    """
    Execute or resume a test run using the latest attempt.
    
    This function:
    1. Loads all necessary data for execution
    2. Finds or creates the latest attempt
    3. Creates a new attempt if needed
    4. Prepares and dispatches execution tasks
    
    Args:
        run_id: The ID of the test run to execute
        
    Returns:
        Redirect to test run view with success/error message
    """
    # Eager load all data needed for dispatching to minimize database queries
    run = TestRun.query.options(
        selectinload(TestRun.endpoint).selectinload(Endpoint.headers),
        selectinload(TestRun.filters),
        selectinload(TestRun.attempts).selectinload(
            TestRunAttempt.executions).selectinload(TestExecution.test_case)
    ).get_or_404(run_id)

    # Find or create latest attempt
    if run.attempts:
        latest_attempt = max(run.attempts, key=lambda a: a.attempt_number)
    else:
        # Create first attempt with pending executions for all test cases
        latest_attempt = TestRunAttempt(
            test_run=run, attempt_number=1, current_sequence=0, status='pending')
        db.session.add(latest_attempt)
        sequence = 0
        for suite in run.test_suites:
            for test_case in suite.test_cases:
                execution = TestExecution(
                    test_run_attempt=latest_attempt,
                    test_case=test_case,
                    sequence=sequence,
                    status='pending'
                )
                db.session.add(execution)
                sequence += 1
        db.session.commit()

    # Get pending executions that need to be run
    pending_executions = [
        ex for ex in latest_attempt.executions if ex.status == 'pending']

    # Create new attempt if all executions in current attempt are complete
    if not pending_executions:
        new_attempt_number = latest_attempt.attempt_number + 1
        new_attempt = TestRunAttempt(
            test_run=run, attempt_number=new_attempt_number, current_sequence=0, status='pending')
        db.session.add(new_attempt)
        sequence = 0
        for suite in run.test_suites:
            for test_case in suite.test_cases:
                execution = TestExecution(
                    attempt=new_attempt,
                    test_case=test_case,
                    sequence=sequence,
                    status='pending'
                )
                db.session.add(execution)
                sequence += 1
        db.session.commit()
        latest_attempt = new_attempt
        pending_executions = latest_attempt.executions

    # Mark attempt as running
    latest_attempt.status = 'running'
    db.session.commit()

    # Prepare common data needed for all test executions
    endpoint_obj = run.endpoint
    original_payload_str = endpoint_obj.http_payload if endpoint_obj else ""
    stored_headers = headers_from_apiheader_list(
        endpoint_obj.headers) if endpoint_obj else {}
    raw_headers_str = "\n".join(
        [f"{k}: {v}" for k, v in stored_headers.items()])
    run_filter_ids_data = [f.id for f in run.filters]

    # Create task signatures for each pending execution
    task_signatures = []
    for execution in pending_executions:
        if execution.test_case and endpoint_obj:
            test_case_transformations_data = execution.test_case.transformations
            sig = celery.signature(
                'workers.execution_tasks.execute_single_test_case_task',
                args=[
                    execution.id,
                    endpoint_obj.id,
                    execution.test_case.prompt,
                    test_case_transformations_data,
                    run_filter_ids_data,
                    original_payload_str,
                    raw_headers_str
                ]
            )
            task_signatures.append(sig)
        else:
            print(f"Skipping execution {execution.id}: Missing test case or endpoint link.")
            execution.status = 'skipped'
            db.session.add(execution)

    # Dispatch tasks based on execution mode
    if not task_signatures:
        flash("No valid tasks could be prepared for execution.", "warning")
    elif run.run_serially:
        # Execute tasks in sequence
        print(f"Executing Test Run {run.id} serially (chaining {len(task_signatures)} tasks).")
        task_workflow = chain(task_signatures)
        task_workflow.apply_async()
        flash(f"Test run {run.id} queued for serial execution.", "success")
    else:
        # Execute tasks in parallel
        print(f"Executing Test Run {run.id} in parallel (grouping {len(task_signatures)} tasks).")
        task_workflow = group(task_signatures)
        task_workflow.apply_async()
        flash(f"Test run {run.id} queued for parallel execution.", "success")

    flash("Test run executed with the custom {{INJECT_PROMPT}} variable replaced in http_payload.", "success")
    return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id)) 