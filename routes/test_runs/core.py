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
from models.model_ExecutionSession import ExecutionSession, ExecutionResult
from models.model_PromptFilter import PromptFilter
from models.model_APIChain import APIChain
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
    View detailed information about a specific test run (Fresh Implementation).

    Args:
        run_id: The ID of the test run to view

    Returns:
        Rendered template with test run details using execution engine data
    """
    # Get test run with fresh model relationships
    run = (
        TestRun.query
        .options(
            selectinload(TestRun.endpoint),
            selectinload(TestRun.chain),
            selectinload(TestRun.test_suites).selectinload(TestSuite.test_cases),
            selectinload(TestRun.execution_sessions)
        )
        .get_or_404(run_id)
    )

    # Get the latest execution session
    latest_session = run.latest_execution_session
    
    # Build execution results if we have a session
    execution_results = []
    result_stats = {
        'total': 0,
        'successful': 0,
        'failed': 0,
        'success_rate': 0.0
    }
    
    if latest_session:
        # Get execution results for this session
        results = (
            ExecutionResult.query
            .filter(ExecutionResult.session_id == latest_session.id)
            .options(selectinload(ExecutionResult.test_case))
            .order_by(ExecutionResult.sequence_number)
            .all()
        )
        
        # Build execution results for display
        for result in results:
            execution_results.append({
                'id': result.id,
                'test_case': result.test_case,
                'sequence_number': result.sequence_number,
                'success': result.success,
                'status_code': result.status_code,
                'response_time_ms': result.response_time_ms,
                'error_message': result.error_message,
                'executed_at': result.executed_at,
                'started_at': result.started_at,
                'request_data': result.request_data,
                'response_data': result.response_data
            })
        
        # Calculate statistics
        result_stats = {
            'total': len(results),
            'successful': sum(1 for r in results if r.success),
            'failed': sum(1 for r in results if not r.success),
            'success_rate': (sum(1 for r in results if r.success) / len(results) * 100) if results else 0
        }

    # Load all prompt filters (for backward compatibility)
    all_filters = PromptFilter.query.order_by(PromptFilter.name).all()

    # Get execution config for display
    execution_config = run.get_execution_config()
    run_transformations = execution_config.get('transformations', [])

    # Render template with fresh execution engine data
    return render_template(
        'test_runs/view_test_run.html',
        run=run,
        latest_session=latest_session,
        execution_results=execution_results,
        result_stats=result_stats,
        current_time=datetime.now(),
        prompt_filters=all_filters,
        run_transformations=run_transformations
    )


@test_runs_bp.route('/create', methods=['GET'])
@login_required
def create_test_run_form():
    """
    Display the form for creating a new test run.

    Returns:
        Rendered template with the test run creation form
    """
    endpoints = Endpoint.query.filter_by(user_id=current_user.id).all()
    chains = APIChain.query.filter_by(user_id=current_user.id).all()
    
    # Get search parameter
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    
    # Build test suites query with search functionality
    test_suites_query = TestSuite.query.filter_by(user_id=current_user.id)
    
    if search:
        test_suites_query = test_suites_query.filter(
            TestSuite.description.contains(search)
        )
    
    # Apply pagination
    pagination = test_suites_query.order_by(TestSuite.id.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    test_suites = pagination.items
    
    filters = PromptFilter.query.order_by(PromptFilter.name).all()

    # If specific test suite is requested via URL parameter
    selected_suite_id = request.args.get('test_suite_id')
    
    return render_template(
        'test_runs/create_test_run.html',
        endpoints=endpoints,
        chains=chains,
        test_suites=test_suites,
        prompt_filters=filters,
        selected_suite_id=selected_suite_id,
        pagination=pagination,
        search=search
    )


@test_runs_bp.route('/create', methods=['POST'])
@login_required
def create_test_run():
    """
    Handle the submission of the test run creation form.

    Returns:
        Redirect to the new test run's detail page or back to the form with errors
    """
    name = request.form.get('run_name')
    description = request.form.get('run_description', '')
    target_type = request.form.get('target_type')
    endpoint_id = request.form.get('endpoint_id')
    chain_id = request.form.get('chain_id')
    test_suite_ids = request.form.getlist('suite_ids')
    
    # Execution configuration from form
    execution_config = {
        'strategy': request.form.get('strategy', 'adaptive'),
        'batch_size': int(request.form.get('batch_size', 4)),
        'concurrency': int(request.form.get('concurrency', 2)),
        'delay_between_requests': float(request.form.get('delay_between_requests', 0.5)),
        'iterations': int(request.form.get('iterations', 1)),
        'auto_adjust': request.form.get('auto_adjust') == 'true',
        'error_threshold': float(request.form.get('error_threshold', 0.1)),
        'execution_mode': request.form.get('execution_mode', 'production'),
        'max_retries': int(request.form.get('max_retries', 2)),
        'timeout': int(request.form.get('timeout', 30))
    }

    # Validation
    errors = []
    if not name:
        errors.append("Test run name is required")
    if not target_type:
        errors.append("Target type is required")
    if target_type == 'endpoint' and not endpoint_id:
        errors.append("Endpoint is required when target type is 'endpoint'")
    if target_type == 'chain' and not chain_id:
        errors.append("Chain is required when target type is 'chain'")
    if not test_suite_ids:
        errors.append("At least one test suite must be selected")

    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('test_runs_bp.create_test_run_form'))

    try:
        # Create test run
        test_run = TestRun(
            name=name,
            description=description,
            user_id=current_user.id,
            target_type=target_type,
            endpoint_id=int(endpoint_id) if endpoint_id else None,
            chain_id=int(chain_id) if chain_id else None,
            execution_config=execution_config
        )

        db.session.add(test_run)
        db.session.flush()  # Get the ID

        # Associate test suites
        for suite_id in test_suite_ids:
            suite = TestSuite.query.get(int(suite_id))
            if suite and suite.user_id == current_user.id:
                test_run.test_suites.append(suite)

        # Validate configuration
        validation_errors = test_run.validate_configuration()
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            db.session.rollback()
            return redirect(url_for('test_runs_bp.create_test_run_form'))

        db.session.commit()
        flash(f'Test run "{name}" created successfully!', 'success')
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating test run: {str(e)}', 'danger')
        return redirect(url_for('test_runs_bp.create_test_run_form'))


@test_runs_bp.route('/<int:run_id>/delete', methods=['POST'])
@login_required
def delete_test_run(run_id):
    """
    Delete a test run and all its associated data.

    Args:
        run_id: The ID of the test run to delete

    Returns:
        Redirect to the test runs list with a success or error message
    """
    test_run = TestRun.query.get_or_404(run_id)
    
    # Check permissions
    if test_run.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this test run.', 'danger')
        return redirect(url_for('test_runs_bp.list_test_runs'))

    try:
        # Delete associated execution sessions (cascade should handle this, but explicit for clarity)
        ExecutionSession.query.filter_by(test_run_id=run_id).delete()
        
        # Delete the test run itself
        db.session.delete(test_run)
        db.session.commit()
        
        flash(f'Test run "{test_run.name}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting test run: {str(e)}', 'danger')

    return redirect(url_for('test_runs_bp.list_test_runs'))


@test_runs_bp.route('/recent', methods=['GET'])
@login_required
def recent_test_runs():
    """
    Get recent test runs for the current user (API endpoint for dashboard).

    Returns:
        JSON response with recent test runs data
    """
    try:
        recent_runs = (
            TestRun.query
            .filter_by(user_id=current_user.id)
            .options(
                selectinload(TestRun.endpoint),
                selectinload(TestRun.execution_sessions)
            )
            .order_by(TestRun.created_at.desc())
            .limit(5)
            .all()
        )

        runs_data = []
        for run in recent_runs:
            latest_session = run.latest_execution_session
            runs_data.append({
                'id': run.id,
                'name': run.name,
                'target_type': run.target_type,
                'target_name': run.get_target_name(),
                'status': run.status,
                'created_at': run.created_at.isoformat(),
                'progress_percentage': run.progress_percentage,
                'session_count': len(run.execution_sessions),
                'latest_session': latest_session.to_dict() if latest_session else None
            })

        return jsonify({
            'success': True,
            'data': runs_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500