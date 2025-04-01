import json
import time
from flask import Blueprint, stream_with_context, Response, request, jsonify, flash, redirect, url_for, render_template
from models.model_Endpoints import Endpoint
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import parse_raw_headers
from services.jailbreaks.jailbreak_service import best_of_n_jailbreak_generator

bon_bp = Blueprint('bon_bp', __name__, url_prefix='/bon')

@bon_bp.route('/')
def bon_index():
    endpoints = Endpoint.query.all()
    return render_template('bon/index.html', endpoints=endpoints)

@bon_bp.route('/endpoint_details/<int:endpoint_id>', methods=['GET'])
def endpoint_details(endpoint_id):
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    headers_list = [{"key": h.key, "value": h.value} for h in endpoint.headers]
    return jsonify({
        "id": endpoint.id,
        "name": endpoint.name,
        "hostname": endpoint.hostname,
        "endpoint": endpoint.endpoint,
        "http_payload": endpoint.http_payload,
        "headers": headers_list
    })

@bon_bp.route('/run', methods=['POST'])
def run_jailbreak():
    adversarial_id = request.form.get('adversarial_endpoint')
    recipient_id = request.form.get('recipient_endpoint')
    initial_prompt = request.form.get('initial_prompt')
    
    if not adversarial_id or not recipient_id or not initial_prompt:
        return jsonify({"error": "All fields are required."}), 400
    
    adversarial_endpoint = Endpoint.query.get_or_404(adversarial_id)
    recipient_endpoint = Endpoint.query.get_or_404(recipient_id)
    
    def generate():
        # best_of_n_jailbreak_generator yields a dict for each attempt.
        for attempt_data in best_of_n_jailbreak_generator(adversarial_endpoint, recipient_endpoint, initial_prompt):
            yield f"data: {json.dumps(attempt_data)}\n\n"
    
    return Response(stream_with_context(generate()), mimetype="text/event-stream")
