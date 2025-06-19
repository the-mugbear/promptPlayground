# routes/test_runs/execution.py
"""
Test run execution operations. This module handles the initiation of test runs
via an orchestrator Celery task, enabling real-time status, pause, and cancel.
"""
from flask import redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db
from sqlalchemy import func

# Celery task import
from tasks.orchestrator import orchestrate          # the new orchestrator task
from tasks.helpers    import emit_run_update        # the shared helper

# Model imports
from models.model_TestRun import TestRun
from models.model_ExecutionSession import ExecutionSession, ExecutionResult
from models.model_TestCase import TestCase
from models.model_TestSuite import TestSuite


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

    # Prevent starting if already actively managed (fresh model check)
    if test_run.status in ['pending', 'running', 'paused'] and test_run.is_active:
        flash(f'Test run is already {test_run.status} and actively managed. Please wait or cancel it.', 'warning')
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))

    # Reset for a new full orchestration if it's completed, failed, or cancelled
    # Also handles if it was 'not_started' to ensure a clean slate for fresh execution
    if test_run.status in ['completed', 'failed', 'cancelled', 'not_started']:
        # Clear previous execution sessions when starting a fresh full run (fresh model approach)
        ExecutionSession.query.filter_by(test_run_id=test_run_id).delete()
        
        test_run.status = 'not_started'  # Will be updated by execution engine
        test_run.started_at = None
        test_run.completed_at = None
        db.session.commit()  # Commit deletions and reset state

    # --- Calculate total test cases for the orchestrator and initial UI ---
    total_test_cases = 0
    if not test_run.test_suites:
        flash('This Test Run has no associated test suites. Cannot start.', 'danger')
        # Mark as failed as it cannot proceed
        test_run.complete_execution('failed')
        db.session.commit()
        emit_run_update(test_run_id, 'run_failed', test_run.to_dict())
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))

    # Check if any test suite has test cases using scalar queries
    has_test_cases = False
    for test_suite in test_run.test_suites:
        suite_case_count = db.session.query(func.count(TestCase.id)).filter(
            TestCase.test_suites.any(TestSuite.id == test_suite.id)
        ).scalar()
        if suite_case_count > 0:
            has_test_cases = True
            total_test_cases += suite_case_count
    
    if not has_test_cases:
        flash('Test suites contain no test cases. Cannot start.', 'danger')
        # Mark as failed as it cannot proceed
        test_run.complete_execution('failed')
        db.session.commit()
        emit_run_update(test_run_id, 'run_failed', test_run.to_dict())
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))
    
    # Multiply by iterations to get total number of executions
    execution_config = test_run.get_execution_config()
    iterations = execution_config.get('iterations', 1)
    total_test_cases *= iterations

    if total_test_cases == 0: # Should be caught above, but as a safeguard
        flash('No test cases found in the associated test suites after counting. Test run cannot start.', 'warning')
        test_run.complete_execution('failed')
        db.session.commit()
        emit_run_update(test_run_id, 'run_failed', test_run.to_dict())
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))

    # --- Prepare TestRun for Orchestration (Fresh Implementation) ---
    test_run.start_execution()  # Sets status to 'running' and started_at timestamp
    # execution_config already contains all necessary configuration for execution engine
    db.session.commit() # Commit total and pending status

    # --- Launch the single orchestrator task ---
    task_result = orchestrate.delay(test_run.id)
    
    # Flash success message for fresh execution engine
    if task_result and task_result.id:
        flash_message = f'Test run (ID: {test_run.id}) submitted for execution with {total_test_cases} test cases. Task ID: {task_result.id}'
        
        try:
            emit_run_update(test_run_id, 'progress_update', test_run.to_dict())
        except Exception:
            pass
    else:
        flash_message = f'Test run (ID: {test_run.id}) submitted, but task ID was not immediately available. Check Celery worker status.'
        print(f"WARNING: Could not get task_result.id immediately for TestRun {test_run_id}")

    flash(flash_message, 'success')
    return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))