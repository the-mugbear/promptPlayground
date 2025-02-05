from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db

from models.model_Endpoints import Endpoint
from models.model_TestSuite import TestSuite
from models.model_TestRun import TestRun

test_runs_bp = Blueprint('test_runs_bp', __name__, url_prefix='/test_runs')

@test_runs_bp.route('/create', methods=['GET'])
def create_test_run_form():
    """
    GET /test_runs/create -> Show a form for selecting an endpoint & one or more test suites
    """
    # 1. Query endpoints, test suites from the DB
    endpoints = Endpoint.query.all()
    test_suites = TestSuite.query.all()

    # 2. Render a template, passing these lists
    return render_template('test_runs/create_test_run.html', endpoints=endpoints, test_suites=test_suites)

@test_runs_bp.route('/create', methods=['POST'])
def handle_create_test_run():
    """
    POST /test_runs/create -> Handle form submission to create a new Test Run
    """
    endpoint_id = request.form.get('endpoint_id')
    selected_suites = request.form.getlist('suite_ids')  # multiple suite checkboxes

    # (Optional) user might provide a name for the run:
    run_name = request.form.get('run_name') or "New Test Run"

    # 1. Create a new TestRun record
    new_run = TestRun(
        name=run_name,
        # possibly store the endpoint_id in the test run 
        # or in a separate linking table, depending on your design
    )
    db.session.add(new_run)
    db.session.commit()

    # 2. Associate the run with the selected endpoint
    # (If TestRun has a direct endpoint_id column, you'd do:
    #   new_run.endpoint_id = endpoint_id
    #   db.session.commit()
    # or if you store it in a linking table or on each TestResult, adapt accordingly.)

    # 3. For each selected suite, gather its test cases or link them to this run
    for suite_id in selected_suites:
        # You might store in a many-to-many table between TestRun and TestSuite,
        # or create TestResult entries for each test case in that suite, etc.
        # Example if you have a relationship:
        #   suite = TestSuite.query.get(suite_id)
        #   new_run.test_suites.append(suite)

        # Or if you're generating TestResult rows:
        #   suite = TestSuite.query.get(suite_id)
        #   for tc in suite.test_cases:
        #       new_result = TestResult(test_run_id=new_run.id, test_case_id=tc.id, status="pending")
        #       db.session.add(new_result)
        pass

    db.session.commit()
    flash("Test run created successfully!", "success")
    return redirect(url_for('test_runs_bp.list_test_runs'))  # or somewhere else
