from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from sqlalchemy.orm import joinedload
from datetime import datetime
from models.model_Endpoints import Endpoint
from models.model_TestSuite import TestSuite
from models.model_TestRun import TestRun
from models.model_TestExecution import TestExecution

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
        # Get form data
        run_name = request.form.get('run_name')
        endpoint_id = request.form.get('endpoint_id')
        selected_suite_ids = request.form.getlist('suite_ids')

        if not run_name or not endpoint_id or not selected_suite_ids:
            return jsonify({
                'error': 'Missing required fields: run_name, endpoint_id, and suite_ids'
            }), 400

        # Create a new TestRun record
        new_run = TestRun(
            name=run_name,
            endpoint_id=endpoint_id,
            status='pending'
        )
        db.session.add(new_run)
        
        # Associate test suites with the run
        sequence = 0  # Initialize sequence counter
        for suite_id in selected_suite_ids:
            suite = TestSuite.query.get(suite_id)
            if not suite:
                return jsonify({
                    'error': f'Test suite with ID {suite_id} not found'
                }), 404
                
            # Add suite to test run
            new_run.test_suites.append(suite)
            
            # Create TestExecution entries for each test case in the suite
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
        return redirect(url_for('test_runs_bp.list_test_runs'))  # or somewhere else

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Failed to create test run: {str(e)}'
        }), 500

    # db.session.commit()
    # flash("Test run created successfully!", "success")
    # return redirect(url_for('test_runs_bp.list_test_runs'))  # or somewhere else
