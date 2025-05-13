"""
Core operations for managing test runs including listing, viewing, creating, and deleting test runs.
This module handles the basic CRUD operations for test runs and their associated data.
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from sqlalchemy.orm import selectinload
from sqlalchemy import func, or_
from datetime import datetime
from models.model_Endpoints import Endpoint
from models.model_TestSuite import TestSuite
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestExecution import TestExecution
from models.model_PromptFilter import PromptFilter
from . import test_runs_bp

@test_runs_bp.route('/', methods=['GET'])
@login_required 
def list_test_runs():
    """
    Display a paginated list of all test runs.
    
    Returns:
        Rendered template with paginated test runs list
    """
    page = request.args.get('page', 1, type=int)
    pagination = (TestRun.query
                 .options(selectinload(TestRun.user))
                 .order_by(TestRun.id.desc())
                 .paginate(page=page, per_page=10, error_out=False))
    runs = pagination.items
    return render_template('test_runs/list_test_runs.html', test_runs=runs, pagination=pagination)

@test_runs_bp.route('/<int:run_id>', methods=['GET'])
@login_required 
def view_test_run(run_id):
    """
    View detailed information about a specific test run.
    
    Args:
        run_id: The ID of the test run to view
        
    Returns:
        Rendered template with test run details including:
        - Test case responses and status
        - Overall execution statistics
        - Per-attempt execution counts
        - Associated prompt filters
    """
    # Eager load all related data to minimize database queries
    run = (TestRun.query
           .options(
               selectinload(TestRun.endpoint),
               selectinload(TestRun.test_suites).selectinload(TestSuite.test_cases),
               selectinload(TestRun.attempts).selectinload(TestRunAttempt.executions).selectinload(TestExecution.test_case)
           )
           .get_or_404(run_id))

    # Build a map of test cases to their execution history
    test_case_map = {}
    for attempt in run.attempts:
        for execution in attempt.executions:
            if not execution.test_case:
                continue
            tc_id = execution.test_case.id
            if tc_id not in test_case_map:
                test_case_map[tc_id] = {
                    'test_case': execution.test_case,
                    'attempts': []
                }
            test_case_map[tc_id]['attempts'].append({
                'execution_id': execution.id,
                'attempt_number': attempt.attempt_number,
                'status': execution.status,
                'response': execution.response_data,
                'started_at': execution.started_at,
                'finished_at': execution.finished_at
            })

    # Sort execution history by attempt number for chronological display
    for item in test_case_map.values():
        item['attempts'].sort(key=lambda x: x['attempt_number'])

    # Calculate overall execution statistics
    overall_counts = (
        db.session.query(
            func.lower(TestExecution.status),
            func.count(TestExecution.id)
        )
        .join(TestRunAttempt)
        .filter(TestRunAttempt.test_run_id == run_id)
        .group_by(TestExecution.status)
        .all()
    )

    overall_counts_dict = {status: count for status, count in overall_counts}
    passed_count = overall_counts_dict.get('passed', 0)
    failed_count = overall_counts_dict.get('failed', 0)
    skipped_count = overall_counts_dict.get('skipped', 0)
    pending_review_count = overall_counts_dict.get('pending_review', 0)

    # Calculate per-attempt execution statistics
    per_attempt_counts = (
        db.session.query(
            TestRunAttempt.attempt_number,
            TestExecution.status,
            func.count(TestExecution.id)
        )
        .join(TestRunAttempt.executions)
        .filter(TestRunAttempt.test_run_id == run_id)
        .group_by(TestRunAttempt.attempt_number, TestExecution.status)
        .all()
    )

    attempt_counts = {}
    for attempt_number, status, count in per_attempt_counts:
        if attempt_number not in attempt_counts:
            attempt_counts[attempt_number] = {
                "passed": 0, "failed": 0, "skipped": 0, "pending_review": 0}
        attempt_counts[attempt_number][status] = count

    # Load all available prompt filters for potential association
    all_filters = PromptFilter.query.order_by(PromptFilter.name).all()

    return render_template(
        'test_runs/view_test_run.html',
        run=run,
        test_case_map=test_case_map,
        current_time=datetime.now(),
        passed_count=passed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        pending_review_count=pending_review_count,
        attempt_counts=attempt_counts,
        prompt_filters=all_filters
    )

@test_runs_bp.route('/create', methods=['GET'])
@login_required
def create_test_run_form():
    """
    Display the form for creating a new test run.
    
    Returns:
        Rendered template with:
        - Paginated list of available test suites
        - List of available endpoints
        - List of available prompt filters
    """
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)

    # Filter test suites by search term if provided
    suites_query = TestSuite.query
    if search:
        suites_query = suites_query.filter(TestSuite.description.ilike(f'%{search}%'))

    pagination = suites_query.paginate(page=page, per_page=10, error_out=False)
    test_suites = pagination.items
    endpoints = Endpoint.query.all()
    prompt_filters = PromptFilter.query.order_by(PromptFilter.name).all()

    return render_template(
        'test_runs/create_test_run.html',
        endpoints=endpoints,
        test_suites=test_suites,
        pagination=pagination,
        search=search,
        prompt_filters=prompt_filters
    )

@test_runs_bp.route('/create', methods=['POST'])
@login_required
def handle_create_test_run():
    """
    Handle the submission of the test run creation form.
    
    Creates a new test run with:
    - Associated endpoint
    - Selected test suites
    - Selected prompt filters
    - Initial test run attempt
    - Pending test executions for each test case
    
    Returns:
        Redirect to the new test run's view page on success,
        or back to the creation form with error message on failure
    """
    run_name = request.form.get('run_name')
    endpoint_id = request.form.get('endpoint_id')
    selected_suite_ids = request.form.getlist('suite_ids')
    selected_filter_ids = request.form.getlist('filter_ids')
    payload_override = request.form.get('endpointPayload')

    # Generate default name if none provided
    if not run_name:
        run_name = f"Run for Endpoint {endpoint_id} at {datetime.now()}"
    if not endpoint_id or not selected_suite_ids:
        flash("Missing required fields: endpoint_id, or suite_ids", 'error')
        return redirect(url_for('test_runs_bp.create_test_run_form'))

    try:
        # Validate and update endpoint if payload override provided
        endpoint_to_update = Endpoint.query.get(endpoint_id)
        if not endpoint_to_update:
            flash(f"Selected endpoint with ID {endpoint_id} not found.", 'error')
            return redirect(url_for('test_runs_bp.create_test_run_form'))

        if payload_override and payload_override.strip():
            if "{{INJECT_PROMPT}}" not in payload_override:
                flash("Error: The overridden payload must still contain '{{INJECT_PROMPT}}'. Endpoint not updated.", 'error')
            else:
                endpoint_to_update.http_payload = payload_override

        # Create new test run
        new_run = TestRun(
            name=run_name,
            endpoint_id=endpoint_id,
            status='not_started',
            user_id=current_user.id
        )
        db.session.add(new_run)

        # Associate selected test suites
        for suite_id in selected_suite_ids:
            suite = TestSuite.query.get(suite_id)
            if not suite:
                flash(f"Test suite with ID {suite_id} not found", "error")
                return redirect(url_for('test_runs_bp.create_test_run_form'))
            new_run.test_suites.append(suite)

        # Associate selected prompt filters
        for pf_id in selected_filter_ids:
            pf = PromptFilter.query.get(pf_id)
            if pf:
                new_run.filters.append(pf)

        # Create initial test run attempt
        new_attempt = TestRunAttempt(
            test_run=new_run,
            attempt_number=1,
            current_sequence=0,
            status='pending'
        )
        db.session.add(new_attempt)
        db.session.flush()

        # Create pending test executions for each test case
        execution_records = []
        seq = 0
        for suite in new_run.test_suites:
            for tc in suite.test_cases:
                execution_records.append(TestExecution(
                    test_run_attempt_id=new_attempt.id,
                    test_case_id=tc.id,
                    sequence=seq,
                    status='pending'
                ))
                seq += 1
        db.session.add_all(execution_records)

        db.session.commit()
        flash("Test run created successfully!", "success")
        return redirect(url_for('test_runs_bp.view_test_run', run_id=new_run.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Failed to create test run: {e}", 'error')
        return redirect(url_for('test_runs_bp.create_test_run_form'))

@test_runs_bp.route('/<int:run_id>/delete', methods=['POST'])
@login_required
def delete_test_run(run_id):
    """
    Delete a test run and all its associated data.
    
    This includes:
    - All test executions
    - All test run attempts
    - Associations with test suites and filters
    - The test run itself
    
    Args:
        run_id: The ID of the test run to delete
        
    Returns:
        Redirect to test runs list with success/error message
    """
    run = TestRun.query.get_or_404(run_id)
    
    # Delete all attempts and their executions
    for attempt in run.attempts:
        for execution in attempt.executions:
            db.session.delete(execution)
        db.session.delete(attempt)
    
    # Remove associations with test suites and filters
    run.test_suites = []
    run.filters = []
    
    # Delete the test run
    db.session.delete(run)
    
    try:
        db.session.commit()
        flash('Test run deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting test run: {str(e)}', 'error')
    
    return redirect(url_for('test_runs_bp.list_test_runs')) 