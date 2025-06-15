# routes/chains/api.py

import logging
import json

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

# Correctly import the functions and classes we will use
from services.chain_execution_service import APIChainExecutor, ChainExecutionError
from services.common.templating_service import render_template_string
from services.common.http_request_service import execute_api_request
from services.common.data_extraction_service import extract_data_from_response, DataExtractionError
from tasks.chain_tasks import execute_full_chain_run
from models import db, APIChain, APIChainStep, Endpoint

from . import chains_api_bp

logger = logging.getLogger(__name__)


@chains_api_bp.route('/test_step_in_isolation', methods=['POST'])
@login_required
def test_step_in_isolation():
    """
    Executes a single chain step in isolation with a mock context.
    This is used for testing a step during the authoring process.
    """
    data = request.get_json()
    endpoint_id = data.get('endpoint_id')
    payload_template = data.get('payload', '{}')
    headers_template = data.get('headers', '{}')
    extraction_rules = data.get('data_extraction_rules', [])
    mock_context = data.get('mock_context', {})

    if not endpoint_id:
        return jsonify({'error': 'Endpoint ID is required'}), 400

    endpoint = Endpoint.query.get(endpoint_id)
    if not endpoint:
        return jsonify({'error': 'Endpoint not found'}), 404

    try:
        # 1. Render templates
        rendered_payload = render_template_string(payload_template, mock_context)
        rendered_headers_str = render_template_string(headers_template, mock_context)
        
        rendered_headers_dict = {}
        # Only try to parse if the string is not empty or just whitespace
        if rendered_headers_str and rendered_headers_str.strip():
            try:
                rendered_headers_dict = json.loads(rendered_headers_str)
            except json.JSONDecodeError as e:
                # This is the error you were seeing.
                return jsonify({'error': f'Invalid JSON in rendered Headers: {e}'}), 400

        # 2. Make the HTTP request using the service function
        response_data = execute_api_request(
            method=endpoint.method,
            hostname_url=endpoint.hostname,
            endpoint_path=endpoint.endpoint,
            raw_headers_or_dict=rendered_headers_dict,
            http_payload_as_string=rendered_payload
        )

        # 3. Extract data from the response using the service function
        extracted_data = {}
        for rule in extraction_rules:
            variable_name = rule.get("variable_name")
            if not variable_name:
                continue
            try:
                extracted_data[variable_name] = extract_data_from_response(response_data, rule)
            except DataExtractionError as e:
                # Still include the variable name in the result, but with the error message
                extracted_data[variable_name] = f"Extraction Error: {e}"
        
        # This response is tailored for the single-step test UI
        return jsonify({
            'rendered_payload': rendered_payload,
            'rendered_headers': rendered_headers_dict,
            'response': {
                'status_code': response_data.get('status_code'),
                'headers': response_data.get('response_headers'),
                'body': response_data.get('response_body'),
            },
            'extracted_data': extracted_data
        }), 200

    except Exception as e:
        logger.error(f"Error in test_step_in_isolation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# --- NEW ENDPOINT FOR THE DEBUGGER ---
@chains_api_bp.route('/execute_step', methods=['POST'])
@login_required
def execute_step():
    """
    Executes a single step of a saved chain, given the current context.
    This is the engine for the interactive chain debugger.
    """
    data = request.get_json()
    step_id = data.get('step_id')
    context = data.get('context', {})

    step = db.session.get(APIChainStep, step_id)
    if not step:
        return jsonify({'error': 'Step not found'}), 404
    
    # Optional: Check if the chain belongs to the user
    if step.chain.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Use the executor service we defined earlier
    executor = APIChainExecutor()
    try:
        result = executor.execute_single_step(step, context)
        return jsonify(result), 200
    except ChainExecutionError as e:
        logger.error(f"Chain execution error on step {step_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@chains_api_bp.route('/<int:chain_id>/execute', methods=['POST'])
@login_required
def execute_full_chain(chain_id):
    """
    API endpoint to trigger a full, asynchronous execution of a chain.
    """
    chain = APIChain.query.filter_by(id=chain_id, user_id=current_user.id).first_or_404()
    
    task = execute_full_chain_run.delay(chain_id=chain.id)
    
    return jsonify({
        'message': 'Chain execution started.',
        'task_id': task.id
    }), 202

@chains_api_bp.route('/<int:chain_id>/reorder_steps', methods=['POST'])
@login_required
def reorder_steps(chain_id):
    """
    Receives a new order of step IDs and updates the database safely.
    """
    chain = db.session.get(APIChain, chain_id)
    if not chain or chain.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized or chain not found'}), 404

    ordered_ids = request.json.get('ordered_ids')
    if not isinstance(ordered_ids, list):
        return jsonify({'error': 'ordered_ids must be a list'}), 400

    try:
        # Create a map of ID to step object for the steps in this chain
        steps_map = {step.id: step for step in chain.steps}
        
        # --- PHASE 1: Move steps to temporary, non-conflicting orders ---
        # We use negative numbers to avoid clashes with existing positive orders.
        for i, step_id_str in enumerate(ordered_ids):
            step_id = int(step_id_str)
            if step_id in steps_map:
                steps_map[step_id].step_order = -(i + 1)
        
        # Flush these temporary changes to the database session.
        # This doesn't permanently save them yet but updates the current transaction state.
        db.session.flush()

        # --- PHASE 2: Set the final, correct order ---
        for i, step_id_str in enumerate(ordered_ids):
            step_id = int(step_id_str)
            if step_id in steps_map:
                steps_map[step_id].step_order = i + 1

        db.session.commit()
        return jsonify({'success': True, 'message': 'Steps reordered successfully.'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error reordering steps for chain {chain_id}: {e}", exc_info=True)
        return jsonify({'error': 'A server error occurred while reordering.'}), 500