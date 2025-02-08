from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db

from models.model_Endpoints import Endpoint
from models.model_TestSuite import TestSuite
from models.model_TestRun import TestRun

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
    including associated suites, test cases, and statuses.
    """
    run = TestRun.query.get_or_404(run_id)

    # Build a dict so we can quickly find the TestResult for each test_case_id
    # E.g. { test_case_id: TestResult object }
    result_map = {}
    if run.results:
        for r in run.results:
            result_map[r.test_case_id] = r
    
    return render_template('test_runs/view_test_run.html', run=run, result_map=result_map)

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
    # get form data
    run_name = request.form.get('run_name')
    endpoint_id = request.form.get('endpoint_id')
    # user might submit suite_ids as multiple values e.g. suite_ids=10, suite_ids=12, ...
    selected_suite_ids = request.form.getlist('suite_ids')

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
    for suite_id in selected_suite_ids:
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
