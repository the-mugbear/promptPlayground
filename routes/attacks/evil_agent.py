import json
import logging
from flask import Blueprint, stream_with_context, Response, request, jsonify, flash, redirect, url_for, render_template
from models.model_Endpoints import Endpoint
from services.common.http_request_service import execute_api_request
from services.common.header_parser_service import parse_raw_headers
from services.jailbreaks.jailbreak_service import evil_agent_jailbreak_generator
from services.jailbreaks.advanced_evil_agent import EvilAgentConfig, AttackStrategy

logger = logging.getLogger(__name__)

evil_agent_bp = Blueprint('evil_agent_bp', __name__, url_prefix='/evil_agent')

@evil_agent_bp.route('/')
def evil_agent_index():
    endpoints = Endpoint.query.all()
    return render_template('attacks/evil_agent/index.html', endpoints=endpoints)

@evil_agent_bp.route('/endpoint_details/<int:endpoint_id>', methods=['GET'])
def endpoint_details(endpoint_id):
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    headers_list = [{"key": h.key, "value": h.value} for h in endpoint.headers]
    return jsonify({
        "id": endpoint.id,
        "name": endpoint.name,
        "base_url": endpoint.base_url,
        "path": endpoint.path,
        "payload_template": endpoint.payload_template.template if endpoint.payload_template else None,
        "headers": headers_list
    })

@evil_agent_bp.route('/run', methods=['GET'])
def run_evil_agent():
    # Get basic parameters
    adversarial_id = request.args.get('adversarial_endpoint')
    recipient_id = request.args.get('recipient_endpoint')
    initial_prompt = request.args.get('initial_prompt')
    
    if not adversarial_id or not recipient_id or not initial_prompt:
        return jsonify({"error": "All fields are required."}), 400
    
    # Get configuration parameters
    use_advanced = request.args.get('use_advanced', 'true').lower() == 'true'
    max_rounds = int(request.args.get('max_rounds', 10))
    success_threshold = float(request.args.get('success_threshold', 0.7))
    learning_enabled = request.args.get('learning_enabled') == 'on'
    use_adversarial_feedback = request.args.get('use_adversarial_feedback') == 'on'
    
    # Get selected strategies
    selected_strategies = request.args.getlist('strategies')
    enabled_strategies = []
    
    strategy_mapping = {
        'role_playing': AttackStrategy.ROLE_PLAYING,
        'social_engineering': AttackStrategy.SOCIAL_ENGINEERING,
        'context_injection': AttackStrategy.CONTEXT_INJECTION,
        'prompt_injection': AttackStrategy.PROMPT_INJECTION,
        'authority_appeal': AttackStrategy.AUTHORITY_APPEAL,
        'urgency_pressure': AttackStrategy.URGENCY_PRESSURE,
        'leetspeak': AttackStrategy.LEETSPEAK,
        'unicode_obfuscation': AttackStrategy.UNICODE_OBFUSCATION,
        'character_substitution': AttackStrategy.CHARACTER_SUBSTITUTION,
        'base64_encode': AttackStrategy.BASE64_ENCODE,
        'rot13': AttackStrategy.ROT13,
        'multi_turn_buildup': AttackStrategy.MULTI_TURN_BUILDUP,
    }
    
    for strategy_name in selected_strategies:
        if strategy_name in strategy_mapping:
            enabled_strategies.append(strategy_mapping[strategy_name])
    
    # Default to basic strategies if none selected
    if not enabled_strategies:
        enabled_strategies = [AttackStrategy.ROLE_PLAYING, AttackStrategy.SOCIAL_ENGINEERING]
    
    logger.info(f"Evil Agent Attack Configuration:")
    logger.info(f"  - Algorithm: {'Advanced' if use_advanced else 'Legacy'}")
    logger.info(f"  - Max Rounds: {max_rounds}")
    logger.info(f"  - Success Threshold: {success_threshold}")
    logger.info(f"  - Strategies: {[s.value for s in enabled_strategies]}")
    logger.info(f"  - Learning: {learning_enabled}")
    logger.info(f"  - Adversarial Feedback: {use_adversarial_feedback}")
    
    adversarial_endpoint = Endpoint.query.get_or_404(adversarial_id)
    recipient_endpoint = Endpoint.query.get_or_404(recipient_id)
    
    def generate():
        try:
            # Pass configuration to the jailbreak generator
            for attempt_data in evil_agent_jailbreak_generator(
                adversarial_endpoint=adversarial_endpoint,
                recipient_endpoint=recipient_endpoint, 
                base_prompt=initial_prompt,
                max_samples=max_rounds,
                use_advanced=use_advanced,
                enabled_strategies=enabled_strategies,
                success_threshold=success_threshold,
                learning_enabled=learning_enabled,
                use_adversarial_feedback=use_adversarial_feedback
            ):
                yield f"data: {json.dumps(attempt_data)}\n\n"
        except Exception as e:
            logger.error(f"Error in evil agent generation: {e}")
            error_data = {
                'final': True,
                'error': str(e),
                'success': False
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

