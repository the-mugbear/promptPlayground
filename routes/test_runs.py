from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from sqlalchemy.orm import joinedload
from datetime import datetime
from models.model_Endpoints import Endpoint
from models.model_TestSuite import TestSuite
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestExecution import TestExecution
from services.transformers.registry import apply_transformation, TRANSFORM_PARAM_CONFIG

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
    """
    Show details for a single test run with its attempts.
    """
    run = (TestRun.query
           .options(
               joinedload(TestRun.endpoint),
               joinedload(TestRun.test_suites).joinedload(TestSuite.test_cases),
               joinedload(TestRun.attempts).joinedload(TestRunAttempt.executions).joinedload(TestExecution.test_case)
           )
           .get_or_404(run_id))

    # Use the latest attempt for statistics; if none exists, fallback to an empty list.
    latest_attempt = max(run.attempts, key=lambda a: a.attempt_number) if run.attempts else None
    executions = latest_attempt.executions if latest_attempt else []

    # Calculate summary statistics on the latest attempt
    execution_stats = {
        'total': len(executions),
        'pending': sum(1 for e in executions if e.status == 'pending'),
        'passed': sum(1 for e in executions if e.status == 'passed'),
        'failed': sum(1 for e in executions if e.status == 'failed'),
        'skipped': sum(1 for e in executions if e.status == 'skipped')
    }
    
    # Calculate progress percentage
    if execution_stats['total'] > 0:
        execution_stats['progress'] = round(
            ((execution_stats['passed'] + execution_stats['failed'] + execution_stats['skipped']) /
             execution_stats['total']) * 100
        )
    else:
        execution_stats['progress'] = 0

    # Calculate duration based on the attempt's timestamps (not the run's, which we removed)
    if latest_attempt and latest_attempt.finished_at and latest_attempt.started_at:
        duration = latest_attempt.finished_at - latest_attempt.started_at
        duration_str = str(duration).split('.')[0]
    else:
        duration_str = None

    # Build a lookup for quick access by test case ID (from the latest attempt)
    execution_map = {
        execution.test_case_id: execution 
        for execution in executions if execution.test_case_id
    }

    # Patch to be lazy and not update frontend
    run.execution_groups = run.attempts

    return render_template(
        'test_runs/view_test_run.html',
        run=run,
        stats=execution_stats,
        duration=duration_str,
        execution_map=execution_map,
        current_time=datetime.now()  # for elapsed time calculations in the template
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
        
        # Create TestExecution records within the new attempt.
        sequence = 0
        for suite in new_run.test_suites:
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
        flash("Test run created successfully!", "success")
        return redirect(url_for('test_runs_bp.list_test_runs'))

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
    url = f"{endpoint_obj.hostname.rstrip('/')}/{endpoint_obj.endpoint.lstrip('/')}"
    original_payload_str = endpoint_obj.http_payload or ""

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

        # Replace the placeholder in the payload.
        replaced_str = original_payload_str.replace("{{INJECT_PROMPT}}", prompt)

        # Attempt to parse the payload as JSON.
        try:
            test_payload = json.loads(replaced_str)
        except json.JSONDecodeError as e:
            execution.status = 'failed'
            execution.response_data = f"Invalid JSON after substitution: {e}"
            execution.started_at = execution.started_at or datetime.now()
            execution.finished_at = datetime.now()
            db.session.commit()
            continue

        try:
            execution.started_at = execution.started_at or datetime.now()
            resp = requests.post(url, json=test_payload, timeout=120, verify=False)
            resp.raise_for_status()
            execution.status = 'passed'
            execution.response_data = resp.text
            execution.finished_at = datetime.now()
        except Exception as e:
            execution.status = 'failed'
            execution.response_data = str(e)
            execution.finished_at = datetime.now()

        db.session.commit()

    # If all executions in the current attempt are finished, mark it completed.
    if all(ex.status in ['passed', 'failed', 'skipped'] for ex in latest_attempt.executions):
        latest_attempt.status = 'completed'
        latest_attempt.finished_at = datetime.now()
        db.session.commit()

    flash("Test run executed with the custom {{INJECT_PROMPT}} variable replaced in http_payload.", "success")
    return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id))