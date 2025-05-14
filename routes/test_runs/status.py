"""
Status update operations for test executions.
This module handles updating the status of test executions and their associated attempts.
"""

from flask import redirect, url_for, flash, jsonify, request
from flask_login import login_required
from extensions import db
from models.model_TestRun import TestRun
from models.model_TestExecution import TestExecution
from . import test_runs_bp

@test_runs_bp.route('/execution/<int:execution_id>/update_status', methods=['POST'])
@login_required
def update_execution_status(execution_id):
    """
    Update the status of a test execution.
    
    This endpoint can be called via AJAX or regular form submission.
    It updates the status of a test execution and handles any associated
    attempt status updates.
    
    Args:
        execution_id: The ID of the test execution to update
        
    Returns:
        For AJAX requests:
            JSON response with success/error message
        For regular requests:
            Redirect to test run view with success/error message
    """
    execution = TestExecution.query.get_or_404(execution_id)
    new_status = request.form.get('new_status')
    
    if not new_status:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Missing new_status parameter'}), 400
        flash('Missing new_status parameter', 'error')
        return redirect(url_for('test_runs_bp.view_test_run', run_id=execution.test_run_attempt.test_run_id))
    
    try:
        execution.status = new_status
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'message': 'Status updated successfully'})
        flash('Status updated successfully', 'success')
        return redirect(url_for('test_runs_bp.view_test_run', run_id=execution.test_run_attempt.test_run_id))
        
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': str(e)}), 500
        flash(f'Error updating status: {str(e)}', 'error')
        return redirect(url_for('test_runs_bp.view_test_run', run_id=execution.test_run_attempt.test_run_id)) 