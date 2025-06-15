import json
from flask import Blueprint, stream_with_context, Response, request, jsonify, flash, redirect, url_for, render_template
from models.model_Endpoints import Endpoint
from services.common.http_request_service import execute_api_request
from services.common.header_parser_service import parse_raw_headers
from services.jailbreaks.jailbreak_service import evil_agent_jailbreak_generator

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
    adversarial_id = request.args.get('adversarial_endpoint')
    recipient_id = request.args.get('recipient_endpoint')
    initial_prompt = request.args.get('initial_prompt')
    
    if not adversarial_id or not recipient_id or not initial_prompt:
        return jsonify({"error": "All fields are required."}), 400
    
    adversarial_endpoint = Endpoint.query.get_or_404(adversarial_id)
    recipient_endpoint = Endpoint.query.get_or_404(recipient_id)
    
    def generate():
        for attempt_data in evil_agent_jailbreak_generator(adversarial_endpoint, recipient_endpoint, initial_prompt):
            yield f"data: {json.dumps(attempt_data)}\n\n"
    
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

