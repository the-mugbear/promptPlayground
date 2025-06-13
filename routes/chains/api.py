# routes/chains/api.py
import logging
from flask import jsonify
from flask_login import login_required, current_user
from . import chains_bp
from services.chain_execution_service import APIChainExecutor, ChainExecutionError
from tasks.chain_tasks import execute_full_chain_run
from models.model_APIChain import APIChain


logger = logging.getLogger(__name__)

@chains_bp.route('/<int:chain_id>/steps/<int:step_id>/execute_upto', methods=['POST'])
@login_required
def execute_upto_step(chain_id, step_id):
    """
    API endpoint to execute a chain up to a specific step and return the results.
    """
    executor = APIChainExecutor()
    try:
        results = executor.execute_chain(chain_id, execute_until_step_id=step_id)
        return jsonify(results), 200
    except ChainExecutionError as e:
        return jsonify({'error': str(e), 'step': e.step_order}), 400
    except Exception as e:
        logger.error(f"Unexpected error during partial chain execution: {e}", exc_info=True)
        return jsonify({'error': 'An unexpected server error occurred.'}), 500
    
@chains_bp.route('/<int:chain_id>/execute', methods=['POST'])
@login_required
def execute_full_chain(chain_id):
    """
    API endpoint to trigger a full, asynchronous execution of a chain.
    """
    chain = APIChain.query.filter_by(id=chain_id, user_id=current_user.id).first_or_404()
    
    # Start the background task
    task = execute_full_chain_run.delay(chain_id=chain.id)
    
    # Return immediately with the task ID
    return jsonify({
        'message': 'Chain execution started.',
        'task_id': task.id
    }), 202 # 202 Accepted is a good status code for starting an async task