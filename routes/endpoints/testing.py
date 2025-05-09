"""
Endpoint testing operations.
This module handles testing of endpoints and retrieving test suggestions.
"""

from flask import request, jsonify, flash, redirect, url_for, render_template
from flask_login import login_required
import json
from models.model_Endpoints import Endpoint
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import parse_raw_headers, headers_from_apiheader_list
from . import endpoints_bp

@endpoints_bp.route('/get_suggestions', methods=['GET'])
@login_required
def get_endpoint_suggestions():
    """
    Get suggestions for endpoint configurations based on existing endpoints.
    
    Returns:
        JSON response containing lists of:
        - Distinct hostnames
        - Distinct paths
        - Distinct payloads
    """
    hostnames = [row.hostname for row in Endpoint.query.with_entities(Endpoint.hostname).distinct().all() if row.hostname]
    paths = [row.endpoint for row in Endpoint.query.with_entities(Endpoint.endpoint).distinct().all() if row.endpoint]
    payloads = [row.http_payload for row in Endpoint.query.with_entities(Endpoint.http_payload).distinct().all() if row.http_payload]

    return jsonify({
        "hostnames": hostnames,
        "paths": paths,
        "payloads": payloads
    })

@endpoints_bp.route('/test', methods=['POST'])
@endpoints_bp.route('/<int:endpoint_id>/test', methods=['POST'])
@login_required
def test_endpoint(endpoint_id=None):
    """
    Test an endpoint with its current configuration.
    Can be used to test either an existing endpoint (with ID) or a new endpoint configuration.
    """
    if endpoint_id:
        # Test an existing endpoint
        endpoint = Endpoint.query.get_or_404(endpoint_id)
        payload = endpoint.http_payload
        headers_dict = headers_from_apiheader_list(endpoint.headers)
        hostname = endpoint.hostname
        endpoint_path = endpoint.endpoint
    else:
        # Test a new endpoint configuration from the form
        payload = request.form.get('http_payload', '').strip()
        raw_headers = request.form.get('raw_headers', '').strip()
        headers_dict = parse_raw_headers(raw_headers) if raw_headers else {}
        hostname = request.form.get('hostname', '').strip()
        endpoint_path = request.form.get('endpoint', '').strip()
    
    # Validate that the payload contains the INJECT_PROMPT token
    if "{{INJECT_PROMPT}}" not in payload:
        flash("Error: The HTTP payload must contain '{{INJECT_PROMPT}}' token.", 'error')
        if endpoint_id:
            return redirect(url_for('endpoints_bp.view_endpoint_details', endpoint_id=endpoint_id))
        else:
            return redirect(url_for('endpoints_bp.create_endpoint_form'))
    
    # Convert headers dictionary to string format
    headers_str = "\n".join(f"{k}: {v}" for k, v in headers_dict.items())
    
    # Replace the injection prompt with a test value
    test_prompt = "What is 4 + 3?"
    payload = payload.replace("{{INJECT_PROMPT}}", test_prompt)
    
    # Validate JSON format
    try:
        json.loads(payload)
    except json.JSONDecodeError as e:
        flash(f"Error: Invalid JSON in payload: {str(e)}", 'error')
        if endpoint_id:
            return redirect(url_for('endpoints_bp.view_endpoint_details', endpoint_id=endpoint_id))
        else:
            return redirect(url_for('endpoints_bp.create_endpoint_form'))
    
    # Ensure the hostname has the correct protocol and handle container networking
    if not hostname.startswith(('http://', 'https://')):
        hostname = 'http://' + hostname
    
    # Replace localhost/127.0.0.1 with host.containers.internal for container networking
    if hostname.startswith('http://127.0.0.1') or hostname.startswith('http://localhost'):
        hostname = hostname.replace('127.0.0.1', 'host.containers.internal').replace('localhost', 'host.containers.internal')
    
    # Make the request
    result = replay_post_request(hostname, endpoint_path, payload, headers_str)
    
    if endpoint_id:
        # Return the results in the view_endpoint template
        return render_template(
            'endpoints/view_endpoint.html',
            endpoint=endpoint,
            test_result={
                'payload_sent': payload,
                'response_data': result.get("response_text"),
                'status_code': result.get("status_code", "N/A"),
                'headers_sent': result.get("headers_sent", {})
            }
        )
    else:
        # Return the results in the create_endpoint template
        return render_template(
            'endpoints/create_endpoint.html',
            payload_templates=PAYLOAD_TEMPLATES,
            test_payload=payload,
            test_response=result.get("response_text"),
            test_status_code=result.get("status_code", "N/A"),
            test_headers_sent=result.get("headers_sent", {})
        )