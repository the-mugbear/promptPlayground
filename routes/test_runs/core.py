"""
Core operations for managing test runs including listing, viewing, creating, and deleting test runs.
This module handles the basic CRUD operations for test runs and their associated data.
"""
import json
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
                  .options(
                      selectinload(TestRun.user),
                      selectinload(TestRun.endpoint)
                  )
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
        - Per‐attempt execution counts
        - Associated prompt filters
        - Run‐level transformations
    """
    # 1) Eager load the run, its endpoint, test suites → test cases,
    #    and all attempts → executions → test_case
    run = (
        TestRun.query
        .options(
            selectinload(TestRun.endpoint),
            selectinload(TestRun.test_suites).selectinload(
                TestSuite.test_cases),
            selectinload(TestRun.attempts)
            .selectinload(TestRunAttempt.executions)
            .selectinload(TestExecution.test_case)
        )
        .get_or_404(run_id)
    )

    # 2) Deserialize run‐level transformations JSON into a Python list
    run_transformations = run.run_transformations if run.run_transformations is not None else []

    # 3) Build a map of test_case_id → { test_case, attempts: [ … ] }
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
                'finished_at': execution.finished_at,
                'processed_prompt': execution.processed_prompt,
                # Enhanced debugging information
                'request_method': execution.request_method,
                'request_url': execution.request_url,
                'request_headers': execution.request_headers,
                'request_payload': execution.request_payload,
                'request_duration_ms': execution.request_duration_ms,
                'response_headers': execution.response_headers,
                'status_code': execution.status_code,
                'error_message': execution.error_message,
                'error_details': execution.error_details
            })

    # 4) Sort each test case’s executions by attempt_number
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

    # 5) Calculate overall execution statistics (passed, failed, etc.)
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

    # 6) Calculate per‐attempt execution counts
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

    # 7) Load all prompt filters (for the “Add Filter” form)
    all_filters = PromptFilter.query.order_by(PromptFilter.name).all()

    # 8) Render template, passing in run_transformations as a Python list
    return render_template(
        'test_runs/view_test_run.html',
        run=run,
        run_transformations=run_transformations,
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
        suites_query = suites_query.filter(
            TestSuite.description.ilike(f'%{search}%'))

    pagination = suites_query.paginate(page=page, per_page=10, error_out=False)
    test_suites = pagination.items
    endpoints = Endpoint.query.filter_by(user_id=current_user.id).all()
    prompt_filters = PromptFilter.query.order_by(PromptFilter.name).all()
    
    # Add chains for the current user
    from models.model_APIChain import APIChain
    chains = APIChain.query.filter_by(user_id=current_user.id).order_by(APIChain.name).all()

    return render_template(
        'test_runs/create_test_run.html',
        endpoints=endpoints,
        test_suites=test_suites,
        chains=chains,
        pagination=pagination,
        search=search,
        prompt_filters=prompt_filters
    )


@test_runs_bp.route('/create', methods=['POST'])
@login_required
def create_test_run():
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
    target_type = request.form.get('target_type', 'endpoint')
    endpoint_id = request.form.get('endpoint_id')
    chain_id = request.form.get('chain_id')
    selected_suite_ids = request.form.getlist('suite_ids')
    selected_filter_ids = request.form.getlist('filter_ids')
    payload_override = request.form.get('endpointPayload')
    iterations = request.form.get('iterations', 1, type=int)
    delay_between_requests = request.form.get('delay_between_requests', 0, type=float)
    run_serially = request.form.get('run_serially') is not None
    
    # Parse header overrides
    override_keys = request.form.getlist('override_key')
    override_values = request.form.getlist('override_value')
    header_overrides = {}
    
    print(f"DEBUG: Raw override keys from form: {override_keys}")
    print(f"DEBUG: Raw override values from form: {override_values}")
    
    for key, value in zip(override_keys, override_values):
        if key.strip() and value.strip():  # Only include non-empty key-value pairs
            header_overrides[key.strip()] = value.strip()
    
    print(f"DEBUG: Processed header overrides: {header_overrides}")

    # 2) Parse the ordered list of transformation names from our hidden field
    ordered_json = request.form.get('ordered_transformations', '[]')
    try:
        ordered_names = json.loads(ordered_json)
    except ValueError:
        ordered_names = []
        flash("Invalid transformation order data.", 'danger')

    # 3) Build a list of {name, params} in exactly that order
    transform_configs = []
    for transform_name in ordered_names:
        if transform_name == 'prepend_text':
            # read the associated text field
            text = request.form.get('text_to_prepend', '').strip()
            if not text:
                flash("Selected “Prepend Text” but left the text blank.", 'warning')
                # You could choose to skip or return here. Let’s skip if blank:
                continue
            transform_configs.append({
                'name': 'prepend_text',
                'params': {'text_to_prepend': text}
            })

        elif transform_name == 'postpend_text':
            text = request.form.get('text_to_postpend', '').strip()
            if not text:
                flash("Selected “Postpend Text” but left the text blank.", 'warning')
                continue
            transform_configs.append({
                'name': 'postpend_text',
                'params': {'text_to_postpend': text}
            })

        else:
            # All other transforms have no extra parameters
            transform_configs.append({'name': transform_name, 'params': {}})

    # run_transformations_json = json.dumps(transform_configs)

    # Generate default name if none provided
    if not run_name:
        if target_type == 'chain' and chain_id:
            run_name = f"Chain Run {chain_id} at {datetime.now()}"
        elif endpoint_id:
            run_name = f"Endpoint Run {endpoint_id} at {datetime.now()}"
        else:
            run_name = f"Test Run at {datetime.now()}"
    
    # Validate required fields based on target type
    if target_type == 'endpoint':
        if not endpoint_id or not selected_suite_ids:
            flash("Missing required fields: endpoint must be selected for endpoint runs, and at least one test suite", 'error')
            return redirect(url_for('test_runs_bp.create_test_run_form'))
    elif target_type == 'chain':
        if not chain_id or not selected_suite_ids:
            flash("Missing required fields: chain must be selected for chain runs, and at least one test suite", 'error')
            return redirect(url_for('test_runs_bp.create_test_run_form'))
    else:
        flash("Invalid target type", 'error')
        return redirect(url_for('test_runs_bp.create_test_run_form'))

    try:
        # Handle validation based on target type
        if target_type == 'endpoint':
            # Validate and update endpoint if payload override provided
            endpoint_to_update = Endpoint.query.get(endpoint_id)
            if not endpoint_to_update:
                flash(
                    f"Selected endpoint with ID {endpoint_id} not found.", 'error')
                return redirect(url_for('test_runs_bp.create_test_run_form'))

            # Check if endpoint has required {{INJECT_PROMPT}} token for test runs
            current_payload = payload_override.strip() if payload_override and payload_override.strip() else None
            
            # Get the payload to check - either override or from endpoint's template
            payload_to_check = current_payload
            if not payload_to_check and endpoint_to_update.payload_template:
                payload_to_check = endpoint_to_update.payload_template.template
            
            # Validate that payload contains {{INJECT_PROMPT}} token
            if not payload_to_check or "{{INJECT_PROMPT}}" not in payload_to_check:
                # Create a helpful error message with a suggested payload
                suggested_payload = '{\n  "messages": [\n    {\n      "role": "user",\n      "content": "{{INJECT_PROMPT}}"\n    }\n  ]\n}'
                
                flash(
                    f"Error: This endpoint cannot be used for test runs because its payload doesn't contain the required '{{{{INJECT_PROMPT}}}}' token. "
                    f"Test cases need this token to substitute their prompts. You can either: "
                    f"1) Edit the endpoint to add a payload template with the token, or "
                    f"2) Use the 'Payload Override' field below with a payload like: {suggested_payload}", 
                    'error')
                return redirect(url_for('test_runs_bp.create_test_run_form'))

            # Update endpoint payload if override provided
            if current_payload:
                endpoint_to_update.http_payload = current_payload
                
        elif target_type == 'chain':
            # Validate chain exists and belongs to user
            from models.model_APIChain import APIChain
            chain_to_use = APIChain.query.filter_by(id=chain_id, user_id=current_user.id).first()
            if not chain_to_use:
                flash(
                    f"Selected chain with ID {chain_id} not found or doesn't belong to you.", 'error')
                return redirect(url_for('test_runs_bp.create_test_run_form'))
            
            # For chain runs, we don't need to validate {{INJECT_PROMPT}} tokens
            # as chains handle data flow differently
            endpoint_to_update = None  # Not applicable for chain runs

        # Create new test run
        new_run = TestRun(
            name=run_name,
            target_type=target_type,
            endpoint_id=endpoint_id if target_type == 'endpoint' else None,
            chain_id=chain_id if target_type == 'chain' else None,
            status='Not Started',
            user_id=current_user.id,
            run_transformations=transform_configs,
            header_overrides=header_overrides if header_overrides else None,
            iterations=iterations,
            delay_between_requests=delay_between_requests,
            run_serially=run_serially
        )
        
        print(f"DEBUG: Created test run with header_overrides: {new_run.header_overrides}")
        
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
