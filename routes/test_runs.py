from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from sqlalchemy.orm import joinedload
from datetime import datetime
from models.model_Endpoints import Endpoint
from models.model_TestSuite import TestSuite
from models.model_TestRun import TestRun
from models.model_TestExecution import TestExecution
from services.transformers.registry import apply_transformation, TRANSFORM_PARAM_CONFIG

import json, requests

test_runs_bp = Blueprint('test_runs_bp', __name__, url_prefix='/test_runs')

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
    GET /test_runs/<run_id> -> Show details for a single test run,
    including associated suites, test cases, and execution statuses.
    
    Args:
        run_id (int): The ID of the test run to view
        
    Returns:
        rendered template with test run details
        
    Raises:
        404: If test run is not found
    """
    # Fetch test run with all related data in one query to avoid N+1 problems
    run = (TestRun.query
           .options(
               joinedload(TestRun.endpoint),
               joinedload(TestRun.test_suites).joinedload(TestSuite.test_cases),
               joinedload(TestRun.executions).joinedload(TestExecution.test_case)
           )
           .get_or_404(run_id))

    # Calculate some summary statistics
    execution_stats = {
        'total': len(run.executions),
        'pending': sum(1 for e in run.executions if e.status == 'pending'),
        'passed': sum(1 for e in run.executions if e.status == 'passed'),
        'failed': sum(1 for e in run.executions if e.status == 'failed'),
        'skipped': sum(1 for e in run.executions if e.status == 'skipped')
    }
    
    # Calculate progress percentage
    if execution_stats['total'] > 0:
        execution_stats['progress'] = round(
            ((execution_stats['passed'] + execution_stats['failed'] + execution_stats['skipped']) /
             execution_stats['total']) * 100
        )
    else:
        execution_stats['progress'] = 0

    # Calculate duration if the run is finished
    if run.finished_at and run.created_at:
        duration = run.finished_at - run.created_at
        duration_str = str(duration).split('.')[0]  # Remove microseconds
    else:
        duration_str = None

    # Create a lookup of executions by test case ID for faster access in template
    execution_map = {
        execution.test_case_id: execution 
        for execution in run.executions if execution.test_case_id
    }

    return render_template(
        'test_runs/view_test_run.html',
        run=run,
        stats=execution_stats,
        duration=duration_str,
        execution_map=execution_map,
        current_time=datetime.now()  # For calculating elapsed time in template
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


@test_runs_bp.route('/create', methods=['POST'])
def handle_create_test_run():
    try:
        # 1) Basic form data
        run_name = request.form.get('run_name')
        endpoint_id = request.form.get('endpoint_id')
        selected_suite_ids = request.form.getlist('suite_ids')
        selected_transform_ids = request.form.getlist('transformations')  # e.g. ["base64_encode", "prepend_text"]

        # 2) Validate required fields
        if not run_name or not endpoint_id or not selected_suite_ids:
            flash("Missing required fields: run_name, endpoint_id, or suite_ids", 'error')
            return redirect(url_for('test_runs_bp.create_test_run_form'))

        # 3) Build transformations_data from the registry
        transformations_data = []
        for t_id in selected_transform_ids:
            cfg = TRANSFORM_PARAM_CONFIG.get(t_id)
            # If user picked a transformation that doesn't exist, skip or raise error
            if not cfg:
                flash(f"Unknown transformation '{t_id}'", 'warning')
                continue

            # Build final_params
            final_params = {}
            for form_key, param_key in cfg["param_map"].items():
                user_val = request.form.get(form_key, "")
                final_params[param_key] = user_val

            transformations_data.append({
                "id": t_id,
                "params": final_params
            })

        # 4) Create the TestRun
        new_run = TestRun(
            name=run_name,
            endpoint_id=endpoint_id,
            status='pending',
            transformations=transformations_data
        )
        db.session.add(new_run)
        
        # 5) Create TestExecutions
        sequence = 0
        for suite_id in selected_suite_ids:
            suite = TestSuite.query.get(suite_id)
            if not suite:
                flash(f"Test suite with ID {suite_id} not found", "error")
                return redirect(url_for('test_runs_bp.create_test_run_form'))

            new_run.test_suites.append(suite)
            
            for test_case in suite.test_cases:
                execution = TestExecution(
                    test_run=new_run,
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
    POST /test_runs/<run_id>/execute -> Start or resume executing the test run.
    Replaces the {{INJECT_PROMPT}} variable in the endpoint's http_payload
    with each test case's prompt, then posts to the endpoint.
    """
    run = TestRun.query.get_or_404(run_id)

    # Check if we can run
    if run.status not in ['pending', 'paused', 'failed']:
        flash(f"Cannot execute run in status '{run.status}'.", "warning")
        return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id))

    # Mark as running
    run.status = 'running'
    db.session.commit()

    # We'll read the run.endpoint.http_payload, which might look like:
    # {
    #   "model": "deepseek-chat",
    #   "messages": [
    #       {"role": "system", "content": "You are a helpful assistant."},
    #       {"role": "user", "content": "PLACEHOLDER"}
    #   ],
    #   "stream": false
    # }
     # We won't parse the JSON up front. We'll parse for each test case after substituting.
    endpoint_obj = run.endpoint
    url = f"{endpoint_obj.hostname.rstrip('/')}/{endpoint_obj.endpoint.lstrip('/')}"

    original_payload_str = run.endpoint.http_payload or ""

    for execution in run.executions:
        if execution.status != 'pending':
            continue

        # 1) Start with the original test case prompt:
        prompt = execution.test_case.prompt

        # 2) For each transformation in run.transformations, apply it:
        for tinfo in (run.transformations or []):
            t_id = tinfo["id"]
            params = tinfo.get("params", {})

            # e.g. use a dictionary or function approach:
            prompt = apply_transformation(t_id, prompt, params)

        # 3) Now we do the string replacement in the http_payload template
        replaced_str = original_payload_str.replace("{{INJECT_PROMPT}}", prompt)

        # 4) Try json.loads(...) and POST as you do now
        try:
            test_payload = json.loads(replaced_str)
        except json.JSONDecodeError as e:
            execution.status = 'failed'
            execution.response_data = f"Invalid JSON after substitution: {e}"
            execution.started_at = execution.started_at or datetime.now()
            execution.finished_at = datetime.now()
            db.session.commit()
            continue  # move on to next test case

        # 3) Send the POST request
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

    # After all test cases:
    if all(ex.status in ['passed', 'failed', 'skipped'] for ex in run.executions):
        run.status = 'completed'
        run.finished_at = datetime.now()
        db.session.commit()

    flash("Test run executed with the custom {{INJECT_PROMPT}} variable replaced in http_payload.", "success")
    return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id))

@test_runs_bp.route('/<int:run_id>/reset', methods=['POST'])
def reset_test_run(run_id):
    """
    POST /test_runs/<run_id>/reset -> Resets the run status to 'pending' and
    all test executions to 'pending' with cleared start/end times.
    """
    run = TestRun.query.get_or_404(run_id)

    # Reset the run's status and timestamps
    run.status = 'pending'
    run.finished_at = None
    run.current_sequence = 0  # if you use this for tracking progress

    # Reset each test execution
    for execution in run.executions:
        execution.status = 'pending'
        execution.started_at = None
        execution.finished_at = None
        execution.response_data = None  # optional if you want to clear the old response

    db.session.commit()

    flash(f"Test run #{run.id} has been reset to 'pending'.", "success")
    return redirect(url_for('test_runs_bp.view_test_run', run_id=run.id))

