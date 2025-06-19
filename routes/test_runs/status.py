"""
Status update operations for execution results.
This module handles updating execution session status and viewing execution results.
"""

from flask import redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models.model_TestRun import TestRun
from models.model_ExecutionSession import ExecutionSession, ExecutionResult
from . import test_runs_bp

@test_runs_bp.route('/execution_result/<int:result_id>/view', methods=['GET'])
@login_required
def view_execution_result(result_id):
    """
    View detailed information about a specific execution result.
    
    Args:
        result_id: The ID of the execution result to view
        
    Returns:
        JSON response with execution result details
    """
    result = ExecutionResult.query.get_or_404(result_id)
    
    # Check permissions via the test run
    session = result.session
    test_run = session.test_run
    
    if test_run.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        result_data = result.to_dict(include_detailed_data=True)
        result_data['session'] = session.to_dict()
        result_data['test_run'] = test_run.to_dict()
        
        return jsonify({
            'success': True,
            'data': result_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@test_runs_bp.route('/execution_session/<int:session_id>/status', methods=['GET'])
@login_required
def execution_session_status(session_id):
    """
    Get real-time status of an execution session.
    
    Args:
        session_id: The ID of the execution session
        
    Returns:
        JSON response with session status and real-time metrics
    """
    session = ExecutionSession.query.get_or_404(session_id)
    
    # Check permissions via the test run  
    if session.test_run.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        # Get real-time statistics
        stats = session.get_real_time_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@test_runs_bp.route('/execution_session/<int:session_id>/control', methods=['POST'])
@login_required
def control_execution_session(session_id):
    """
    Control an execution session (pause, resume, cancel).
    
    Args:
        session_id: The ID of the execution session
        
    Returns:
        JSON response with success/error message
    """
    from flask import current_app
    current_app.logger.info(f"=== CONTROL REQUEST RECEIVED ===")
    current_app.logger.info(f"Control request for session {session_id}")
    current_app.logger.info(f"Request method: {request.method}")
    current_app.logger.info(f"Request form data: {dict(request.form)}")
    current_app.logger.info(f"Request headers: {dict(request.headers)}")
    
    session = ExecutionSession.query.get_or_404(session_id)
    action = request.form.get('action')
    
    current_app.logger.info(f"Session {session_id} current state: {session.state}, action: {action}")
    
    # Check permissions via the test run
    if session.test_run.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Permission denied'}), 403
    
    if not action:
        return jsonify({'error': 'Missing action parameter'}), 400
    
    try:
        if action == 'pause':
            if session.state in ['running', 'pending']:  # Allow pausing pending sessions too
                session.state = 'paused'
                session.test_run.pause_execution()
                db.session.commit()
                message = 'Execution paused successfully'
            else:
                return jsonify({'error': f'Can only pause running or pending executions. Current state: {session.state}'}), 400
                
        elif action == 'resume':
            if session.state == 'paused':
                session.state = 'running'
                session.test_run.resume_execution()
                db.session.commit()
                message = 'Execution resumed successfully'
            else:
                return jsonify({'error': 'Can only resume paused executions'}), 400
                
        elif action == 'cancel':
            if session.state in ['pending', 'running', 'paused']:
                session.complete_execution('cancelled')
                session.test_run.complete_execution('cancelled')
                db.session.commit()
                message = 'Execution cancelled successfully'
            else:
                return jsonify({'error': 'Cannot cancel completed executions'}), 400
                
        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400
        
        return jsonify({
            'success': True,
            'message': message,
            'new_state': session.state
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Deprecated endpoint for backward compatibility
@test_runs_bp.route('/execution/<int:execution_id>/update_status', methods=['POST'])
@login_required
def update_execution_status(execution_id):
    """
    DEPRECATED: Legacy endpoint for updating execution status.
    
    This endpoint is maintained for backward compatibility but redirects
    to the execution result view since execution results are immutable
    in the fresh model.
    
    Args:
        execution_id: The ID of the legacy execution (treated as result_id)
        
    Returns:
        Redirect to test run view with info message
    """
    # Try to find an execution result with this ID
    result = ExecutionResult.query.get(execution_id)
    
    if result:
        test_run_id = result.session.test_run_id
        flash('Execution results are immutable in the new execution engine. Use session controls instead.', 'info')
        return redirect(url_for('test_runs_bp.view_test_run', run_id=test_run_id))
    else:
        flash('Execution result not found.', 'error')
        return redirect(url_for('test_runs_bp.list_test_runs'))