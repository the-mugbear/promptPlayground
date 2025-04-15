from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from datetime import datetime
from models.model_Endpoints import Endpoint
from models.model_TestSuite import TestSuite
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestExecution import TestExecution
from services.transformers.registry import apply_transformation, TRANSFORM_PARAM_CONFIG
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import headers_from_apiheader_list

import json, requests

test_runs_bp = Blueprint('test_runs_bp', __name__, url_prefix='/test_runs')

# ********************************
# ROUTES
# ********************************
@test_runs_bp.route('/', methods=['GET'])
def list_test_runs():
    """
    GET /test_runs -> Displays a table or list of existing test runs
    """
    # Optional: handle pagination
    page = request.args.get('page', 1, type=int)
    pagination = TestRun.query.order_by(TestRun.id.desc()).paginate(page=page, per_page=10, error_out=False)
    runs = pagination.items

    return render_template('test_runs/list_test_runs.html', test_runs=runs, pagination=pagination)

@test_runs_bp.route('/<int:run_id>', methods=['GET'])
def view_test_run(run_id):

    run = (TestRun.query
        .options(
            selectinload(TestRun.endpoint),
            selectinload(TestRun.test_suites).selectinload(TestSuite.test_cases),
            selectinload(TestRun.attempts).selectinload(TestRunAttempt.executions).selectinload(TestExecution.test_case)
        )
        .get_or_404(run_id))

    # Build a dictionary keyed by test_case.id with responses from each attempt.
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
                'execution_id': execution.id,  # for form reference
                'attempt_number': attempt.attempt_number,
                'status': execution.status,
                'response': execution.response_data,
                'started_at': execution.started_at,
                'finished_at': execution.finished_at
            })

    # Sort responses by attempt number for each test case.
    for item in test_case_map.values():
        item['attempts'].sort(key=lambda x: x['attempt_number'])

    # Aggregate overall counts for the run.
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

    # Convert the result to a dictionary.
    overall_counts_dict = {status: count for status, count in overall_counts}
    passed_count = overall_counts_dict.get('passed', 0)
    failed_count = overall_counts_dict.get('failed', 0)
    skipped_count = overall_counts_dict.get('skipped', 0)
    pending_review_count = overall_counts_dict.get('pending_review', 0)

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

    # Then, you can build your attempt_counts dictionary:
    attempt_counts = {}
    for attempt_number, status, count in per_attempt_counts:
        if attempt_number not in attempt_counts:
            attempt_counts[attempt_number] = {"passed": 0, "failed": 0, "skipped": 0, "pending_review": 0}
        attempt_counts[attempt_number][status] = count

    return render_template(
        'test_runs/view_test_run.html',
        run=run,
        test_case_map=test_case_map,
        current_time=datetime.now(),
        passed_count=passed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        pending_review_count=pending_review_count,
        attempt_counts=attempt_counts
    )


@test_runs_bp.route('/create', methods=['GET'])
def create_test_run_form():
    # 1. Get page & search from query params
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    
    # 2. Base query for test suites
    suites_query = TestSuite.query
    
    # 3. If there's a search term, filter by description
    if search:
        # e.g. case-insensitive match
        suites_query = suites_query.filter(TestSuite.description.ilike(f'%{search}%'))
    
    # 4. Paginate, 10 per page
    pagination = suites_query.paginate(page=page, per_page=10, error_out=False)
    test_suites = pagination.items  # the current page’s suite objects
    
    # 5. We'll also fetch endpoints for the dropdown
    endpoints = Endpoint.query.all()
    
    return render_template(
        'test_runs/create_test_run.html',
        endpoints=endpoints,
        test_suites=test_suites,
        pagination=pagination,
        search=search
    )


# ********************************
# SERVICES
# ********************************
@test_runs_bp.route('/create', methods=['POST'])
def handle_create_test_run():
    try:
        run_name = request.form.get('run_name')
        endpoint_id = request.form.get('endpoint_id')
        selected_suite_ids = request.form.getlist('suite_ids')

        if not run_name or not endpoint_id or not selected_suite_ids:
            flash("Missing required fields: run_name, endpoint_id, or suite_ids", 'error')
            return redirect(url_for('test_runs_bp.create_test_run_form'))

        # Create the TestRun record
        new_run = TestRun(
            name=run_name,
            endpoint_id=endpoint_id,
            status='pending'
        )
        db.session.add(new_run)
        
        # Associate selected test suites
        for suite_id in selected_suite_ids:
            suite = TestSuite.query.get(suite_id)
            if not suite:
                flash(f"Test suite with ID {suite_id} not found", "error")
                return redirect(url_for('test_runs_bp.create_test_run_form'))
            new_run.test_suites.append(suite)

        # Create an initial TestRunAttempt (attempt_number 1)
        new_attempt = TestRunAttempt(
            test_run=new_run,
            attempt_number=1,
            current_sequence=0,
            status='pending'
        )
        db.session.add(new_attempt)
        db.session.flush()  # Ensure new_attempt.id is generated
        
        # Build a list of TestExecution objects with explicit foreign keys.
        execution_records = []
        sequence = 0
        for suite in new_run.test_suites:
            for test_case in suite.test_cases:
                execution_records.append(
                    TestExecution(
                        test_run_attempt_id=new_attempt.id,  # Explicitly set the FK
                        test_case_id=test_case.id,             # Explicitly set the test case FK
                        sequence=sequence,
                        status='pending'
                    )
                )
                sequence += 1

        # Instead of bulk_save_objects, use add_all.
        db.session.add_all(execution_records)
        db.session.commit()
        flash("Test run created successfully!", "success")
        return redirect(url_for('test_runs_bp.view_test_run', run_id=new_run.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Failed to create test run: {str(e)}", 'error')
        return redirect(url_for('test_runs_bp.create_test_run_form'))

@test_runs_bp.route('/<int:run_id>/execute', methods=['POST'])
def execute_test_run(run_id):
    """
    Execute or resume a test run using the latest attempt.
    """
    run = TestRun.query.get_or_404(run_id)

    # Determine the latest attempt; if none exists, create one.
    if run.attempts:
        latest_attempt = max(run.attempts, key=lambda a: a.attempt_number)
    else:
        latest_attempt = TestRunAttempt(test_run=run, attempt_number=1, current_sequence=0, status='pending')
        db.session.add(latest_attempt)
        # Create TestExecution records for each test case in associated suites
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

    # Use the latest attempt’s executions
    pending_executions = [ex for ex in latest_attempt.executions if ex.status == 'pending']
    
    # If no pending executions remain, create a new attempt.
    if not pending_executions:
        new_attempt_number = latest_attempt.attempt_number + 1
        new_attempt = TestRunAttempt(test_run=run, attempt_number=new_attempt_number, current_sequence=0, status='pending')
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

    # Mark the current attempt as running.
    latest_attempt.status = 'running'
    db.session.commit()

    endpoint_obj = run.endpoint
    original_payload_str = endpoint_obj.http_payload or ""

    # Build raw headers string from the stored headers, if any
    stored_headers = headers_from_apiheader_list(endpoint_obj.headers)  # returns a dict
    # Create a raw header string: "Key1: Value1; Key2: Value2"
    # test_temporary endpoint expects (and the headers.js parser assumes) that each header is on its own line
    raw_headers = "\n".join([f"{k}: {v}" for k, v in stored_headers.items()])

    # Process each pending execution in the current attempt.
    for execution in pending_executions:
        # Apply transformations to the test case prompt.
        prompt = execution.test_case.prompt
        for tinfo in (execution.test_case.transformations or []):
            t_type = tinfo.get("type")
            params = {}
            if "value" in tinfo:
                params["value"] = tinfo["value"]
            prompt = apply_transformation(t_type, prompt, params)

        # Remove any invalid characters specified in the endpoint's configuration.
        if endpoint_obj.invalid_characters:
            for char in endpoint_obj.invalid_characters:
                prompt = prompt.replace(char, '')

        # Replace the placeholder in the payload with the transformed prompt.
        replaced_payload_str = original_payload_str.replace("{{INJECT_PROMPT}}", prompt)
        execution.started_at = execution.started_at or datetime.now()

        # Use the shared service to replay the POST request
        result = replay_post_request(endpoint_obj.hostname, endpoint_obj.endpoint, replaced_payload_str, raw_headers)
        execution.finished_at = datetime.now()

        if result.get("status_code") is not None:
            execution.status = 'pending_review'
            execution.response_data = result.get("response_text")
        else:
            execution.status = 'error'
            execution.response_data = result.get("response_text")
        
        db.session.commit()

    # If all executions are finished, mark the attempt as completed.
    # TODO: Remove other states, all cases should be 'pending review' after execution
    if all(ex.status in ['pending review', 'failed', 'skipped'] for ex in latest_attempt.executions):
        latest_attempt.status = 'completed'
        latest_attempt.finished_at = datetime.now()
        run.status = 'completed' # sets the test run record as complete if all test cases were completed
        db.session.commit()

    flash("Test run executed with the custom {{INJECT_PROMPT}} variable replaced in http_payload.", "success")
    return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id))


@test_runs_bp.route('/<int:run_id>/update_execution_status', methods=['POST'])
def update_execution_status(run_id):
    # Retrieve form data
    execution_id = request.form.get('execution_id')
    new_status = request.form.get('status')
    
    if not execution_id or not new_status:
        flash("Missing execution ID or status.", "error")
        # For AJAX requests, return JSON error
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Missing execution ID or status."}), 400
        return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id))
    
    try:
        execution = TestExecution.query.get_or_404(execution_id)
        execution.status = new_status
        db.session.commit()
        flash("Test execution status updated successfully.", "success")
        
        # Return a JSON response for AJAX calls
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "success", "message": "Test execution status updated successfully."})
        else:
            return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id))
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating status: {str(e)}", "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": str(e)}), 400
        return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id))

# TestRun has a 1-to-many relationship with TestRunAttempt
# These in turn cascade to TestExecution records
# TestRun has a 1-to-many relationship with TestSuite through the association table
@test_runs_bp.route('/<int:run_id>/delete', methods=['POST'])
def delete_test_run(run_id):
    # Retrieve the test run or return a 404 if not found
    test_run = TestRun.query.get_or_404(run_id)
    
    # Clear the many-to-many association with test suites to avoid orphaned rows
    test_run.test_suites.clear()
    
    # Delete the test run; its attempts (and their executions) will be removed via cascade
    db.session.delete(test_run)
    db.session.commit()
    
    flash("Test run deleted successfully", "success")
    return redirect(url_for('test_runs_bp.list_test_runs'))