# routes/test_runs/execution.py
"""
Test run execution operations. This module handles the initiation of test runs
via an orchestrator Celery task, enabling real-time status, pause, and cancel.
"""
from flask import redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db

# Celery task import
from tasks.orchestrator import orchestrate          # the new orchestrator task
from tasks.helpers    import emit_run_update        # the shared helper

# Model imports
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt


from . import test_runs_bp

@test_runs_bp.route('/<int:test_run_id>/start', methods=['POST'])
@login_required
def start_test_run(test_run_id):
    """
    Starts a new, full execution pass of a TestRun managed by an orchestrator task.
    This enables WebSocket-based real-time status, pause, and cancel.
    """
    test_run = db.session.get(TestRun, test_run_id)
    if not test_run:
        flash('Test Run not found.', 'danger')
        return redirect(url_for('test_runs_bp.list_test_runs')) # Adjust to your actual list route

    if test_run.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to start this test run.', 'danger')
        return redirect(url_for('test_runs_bp.list_test_runs'))

    # Prevent starting if already actively managed by an orchestrator
    if test_run.status in ['pending', 'running', 'pausing', 'cancelling'] and test_run.celery_task_id:
        flash(f'Test run is already {test_run.status} and actively managed. Please wait or cancel it.', 'warning')
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))

    # Reset for a new full orchestration if it's completed, failed, or cancelled
    # Also handles if it was 'not_started' to ensure a clean slate for progress fields
    if test_run.status in ['completed', 'failed', 'cancelled', 'not_started']:
        # Clear previous attempts when starting a fresh full run
        # TestRunAttempt.query.filter_by(test_run_id=test_run_id).delete()
        
        test_run.status = 'not_started' # Will be set to 'pending'/'running' by this function/orchestrator
        test_run.progress_current = 0
        test_run.celery_task_id = None
        test_run.start_time = None # Orchestrator will set its own start_time
        test_run.end_time = None
        # progress_total will be recalculated
        db.session.commit() # Commit deletions and reset state

    # --- Calculate total test cases for the orchestrator and initial UI ---
    total_test_cases = 0
    if not test_run.test_suites or not any(list(ts.test_cases) for ts in test_run.test_suites):
        flash('This Test Run has no associated test suites or no test cases in them. Cannot start.', 'danger')
        # Mark as failed as it cannot proceed
        test_run.status = 'failed'
        test_run.progress_total = 0
        test_run.progress_current = 0
        test_run.end_time = datetime.utcnow()
        db.session.commit()
        emit_run_update(test_run_id, 'run_failed', test_run.get_status_data())
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))

    for test_suite in test_run.test_suites: # Assuming test_run.test_suites is eager/properly loaded
        total_test_cases += len(list(test_suite.test_cases)) # Ensure test_cases are loaded

    if total_test_cases == 0: # Should be caught above, but as a safeguard
        flash('No test cases found in the associated test suites after counting. Test run cannot start.', 'warning')
        test_run.status = 'failed' # No cases means it effectively failed to run anything meaningful
        test_run.progress_total = 0
        test_run.progress_current = 0
        test_run.end_time = datetime.utcnow()
        db.session.commit()
        emit_run_update(test_run_id, 'run_failed', test_run.get_status_data())
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))

    # --- Prepare TestRun for Orchestration ---
    test_run.progress_total = total_test_cases
    test_run.progress_current = 0
    test_run.status = 'pending' # The orchestrator task will quickly change this to 'running'
    test_run.start_time = datetime.utcnow() # Set start time here, orchestrator can also update if precise timing needed
    test_run.end_time = None
    # celery_task_id will be set by the orchestrator, or optimistically below
    db.session.commit() # Commit total and pending status

    # --- Launch the single orchestrator task ---
    task_result = orchestrate.delay(test_run.id)
    
    # Optimistically update the celery_task_id on the TestRun object in the database.
    # The orchestrator task will also do this as its first step, ensuring consistency.
    if task_result and task_result.id:
        test_run.celery_task_id = task_result.id
        db.session.commit()
        flash_message = f'Test run (ID: {test_run.id}) submitted for execution with {total_test_cases} test cases. Orchestrator Task ID: {task_result.id}'
        
        try:
            emit_run_update(test_run_id, 'progress_update', test_run.get_status_data())
        except Exception:
            pass
    else:
        flash_message = f'Test run (ID: {test_run.id}) submitted, but task ID was not immediately available. Check Celery worker status.'
        print(f"WARNING: Could not get task_result.id immediately for TestRun {test_run_id}")

    flash(flash_message, 'success')
    return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))
