# routes/test_runs/api.py

import logging
import random
from flask import jsonify, request
from flask_login import login_required, current_user

from extensions import db
from models.model_TestRun import TestRun
from models.model_TestSuite import TestSuite
from models.model_TestCase import TestCase
from models.model_ExecutionSession import ExecutionSession
from services.transformers.registry import apply_multiple_transformations, TRANSFORM_PARAM_CONFIG
from . import test_runs_bp

logger = logging.getLogger(__name__)

@test_runs_bp.route('/api/random_test_case', methods=['POST'])
@login_required
def get_random_test_case():
    """Get a random test case from selected test suites"""
    data = request.get_json()
    suite_ids = data.get('suite_ids', [])
    
    if not suite_ids:
        return jsonify({'error': 'No test suites provided'}), 400
    
    # Convert to integers
    try:
        suite_ids = [int(sid) for sid in suite_ids]
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid suite IDs provided'}), 400
    
    try:
        logger.debug(f"Getting test cases for suite_ids: {suite_ids}, user_id: {current_user.id}")
        
        # Get all test cases from the selected suites
        test_cases = TestCase.query.join(TestCase.test_suites).filter(
            TestSuite.id.in_(suite_ids),
            TestSuite.user_id == current_user.id  # Ensure user owns the suites
        ).all()
        
        logger.debug(f"Found {len(test_cases)} test cases")
        
        if not test_cases:
            # Let's also check if the suites exist and belong to the user
            user_suites = TestSuite.query.filter(
                TestSuite.id.in_(suite_ids),
                TestSuite.user_id == current_user.id
            ).all()
            logger.debug(f"User owns {len(user_suites)} of the requested suites")
            
            # Check total test cases in those suites
            if user_suites:
                total_cases = TestCase.query.join(TestCase.test_suites).filter(
                    TestSuite.id.in_([s.id for s in user_suites])
                ).count()
                logger.debug(f"Total test cases in user's suites: {total_cases}")
            
            return jsonify({'error': 'No test cases found in selected suites'}), 404
        
        # Pick a random test case
        random_case = random.choice(test_cases)
        
        return jsonify({
            'id': random_case.id,
            'prompt': random_case.prompt,
            'source': random_case.source,
            'attack_type': random_case.attack_type,
            'data_type': random_case.data_type,
            'nist_risk': random_case.nist_risk,
            'suite_name': random_case.test_suites[0].description if random_case.test_suites else 'Unknown'
        })
        
    except Exception as e:
        logger.error(f"Error getting random test case: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get random test case'}), 500

@test_runs_bp.route('/api/apply_transformations', methods=['POST'])
@login_required
def apply_transformations():
    """Apply transformations to a test prompt for preview using the existing transformers service"""
    data = request.get_json()
    original_prompt = data.get('prompt', '')
    transformation_ids = data.get('transformation_ids', [])
    all_params = data.get('params', {})
    
    if not original_prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    try:
        logger.debug(f"Applying {len(transformation_ids)} transformations: {transformation_ids}")
        logger.debug(f"With parameters: {all_params}")
        
        # Use the existing transformers service to apply transformations in order
        transformed_prompt = apply_multiple_transformations(transformation_ids, original_prompt, all_params)
        
        logger.debug(f"Original: {original_prompt[:50]}...")
        logger.debug(f"Transformed: {transformed_prompt[:50]}...")
        
        return jsonify({
            'original': original_prompt,
            'transformed': transformed_prompt
        })
        
    except Exception as e:
        logger.error(f"Error applying transformations: {e}", exc_info=True)
        return jsonify({'error': 'Failed to apply transformations'}), 500

@test_runs_bp.route('/api/<int:run_id>/start', methods=['POST'])
@login_required
def start_test_run_api(run_id):
    """API endpoint to start a test run"""
    test_run = TestRun.query.filter_by(id=run_id, user_id=current_user.id).first()
    if not test_run:
        return jsonify({'error': 'Test run not found or unauthorized'}), 404
    
    if test_run.status not in ['not_started', 'pending']:
        return jsonify({'error': f'Cannot start test run in {test_run.status} status'}), 400
    
    try:
        # Update status to pending (actual execution would be handled by Celery)
        test_run.status = 'pending'
        db.session.commit()
        
        # TODO: Trigger actual test execution here
        # task = execute_test_run.delay(run_id)
        # test_run.celery_task_id = task.id
        # db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Test run started',
            'status': test_run.status
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error starting test run {run_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to start test run'}), 500

@test_runs_bp.route('/api/<int:run_id>/pause', methods=['POST'])
@login_required
def pause_test_run_api(run_id):
    """API endpoint to pause a test run"""
    test_run = TestRun.query.filter_by(id=run_id, user_id=current_user.id).first()
    if not test_run:
        return jsonify({'error': 'Test run not found or unauthorized'}), 404
    
    if test_run.status != 'running':
        return jsonify({'error': f'Cannot pause test run in {test_run.status} status'}), 400
    
    try:
        test_run.status = 'paused'
        db.session.commit()
        
        # TODO: Signal Celery task to pause
        
        return jsonify({
            'success': True,
            'message': 'Test run paused',
            'status': test_run.status
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error pausing test run {run_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to pause test run'}), 500

@test_runs_bp.route('/api/<int:run_id>/resume', methods=['POST'])
@login_required
def resume_test_run_api(run_id):
    """API endpoint to resume a test run"""
    test_run = TestRun.query.filter_by(id=run_id, user_id=current_user.id).first()
    if not test_run:
        return jsonify({'error': 'Test run not found or unauthorized'}), 404
    
    if test_run.status != 'paused':
        return jsonify({'error': f'Cannot resume test run in {test_run.status} status'}), 400
    
    try:
        test_run.status = 'running'
        db.session.commit()
        
        # TODO: Signal Celery task to resume
        
        return jsonify({
            'success': True,
            'message': 'Test run resumed',
            'status': test_run.status
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resuming test run {run_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to resume test run'}), 500

@test_runs_bp.route('/api/<int:run_id>/cancel', methods=['POST'])
@login_required
def cancel_test_run_api(run_id):
    """API endpoint to cancel a test run"""
    test_run = TestRun.query.filter_by(id=run_id, user_id=current_user.id).first()
    if not test_run:
        return jsonify({'error': 'Test run not found or unauthorized'}), 404
    
    if test_run.status not in ['running', 'paused', 'pending']:
        return jsonify({'error': f'Cannot cancel test run in {test_run.status} status'}), 400
    
    try:
        test_run.status = 'cancelled'
        db.session.commit()
        
        # TODO: Signal Celery task to cancel
        
        return jsonify({
            'success': True,
            'message': 'Test run cancelled',
            'status': test_run.status
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cancelling test run {run_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to cancel test run'}), 500

@test_runs_bp.route('/api/<int:run_id>', methods=['DELETE'])
@login_required
def delete_test_run_api(run_id):
    """API endpoint to delete a test run"""
    test_run = TestRun.query.filter_by(id=run_id, user_id=current_user.id).first()
    if not test_run:
        return jsonify({'error': 'Test run not found or unauthorized'}), 404
    
    if test_run.status == 'running':
        return jsonify({'error': 'Cannot delete a running test run. Cancel it first.'}), 400
    
    try:
        db.session.delete(test_run)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Test run deleted'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting test run {run_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete test run'}), 500


@test_runs_bp.route('/api/test-runs/<int:run_id>/status', methods=['GET'])
@login_required
def get_test_run_status_api(run_id):
    """API endpoint to get test run status and current execution session"""
    test_run = TestRun.query.filter_by(id=run_id, user_id=current_user.id).first()
    if not test_run:
        return jsonify({'error': 'Test run not found or unauthorized'}), 404
    
    try:
        # Get current execution session
        current_session = test_run.current_execution_session
        
        response_data = {
            'run_id': test_run.id,
            'status': test_run.status,
            'current_session': None
        }
        
        if current_session:
            response_data['current_session'] = {
                'id': current_session.id,
                'state': current_session.state,
                'strategy_name': current_session.strategy_name,
                'progress_percentage': current_session.progress_percentage,
                'total_test_cases': current_session.total_test_cases,
                'completed_test_cases': current_session.completed_test_cases,
                'health_status': current_session.health_status
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error getting test run status {run_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get test run status'}), 500