# app/endpoints/views_testing.py
from flask import request, jsonify, flash, redirect, url_for, render_template
from flask_login import login_required
import json

from extensions import db
from models.model_Endpoints import Endpoint
from services.common.http_request_service import replay_post_request # Adjust path
from services.common.header_parser_service import parse_raw_headers, headers_from_apiheader_list # Adjust path
from services.endpoints.api_templates import PAYLOAD_TEMPLATES # Assuming this is still the source

from . import endpoints_bp
from .views_core import get_endpoint_form_data # If test can be initiated from create form

@endpoints_bp.route('/get_suggestions', methods=['GET'])
@login_required
def get_endpoint_suggestions():
    hostnames = [row.hostname for row in Endpoint.query.with_entities(Endpoint.hostname).distinct().all() if row.hostname]
    paths = [row.endpoint for row in Endpoint.query.with_entities(Endpoint.endpoint).distinct().all() if row.endpoint]
    payloads = [row.http_payload for row in Endpoint.query.with_entities(Endpoint.http_payload).distinct().all() if row.http_payload]

    return jsonify({
        "hostnames": hostnames,
        "paths": paths,
        "payloads": payloads
    })

@endpoints_bp.route('/test', methods=['POST']) # For testing a new, unsaved configuration
@endpoints_bp.route('/<int:endpoint_id>/test', methods=['POST']) # For testing an existing endpoint
@login_required
def test_endpoint(endpoint_id=None):
    endpoint = None
    form_data = {} # To store data from form or DB

    if endpoint_id:
        endpoint = Endpoint.query.options(joinedload(Endpoint.headers)).get_or_404(endpoint_id)
        hostname = endpoint.hostname
        endpoint_path = endpoint.endpoint
        payload_template = endpoint.http_payload # This is the template with {{INJECT_PROMPT}}
        headers_dict = headers_from_apiheader_list(endpoint.headers)
    else: # Testing a new configuration from form
        # Use a simplified version of get_endpoint_form_data or extract directly
        # For simplicity, direct extraction here. Consider refining.
        hostname = request.form.get('hostname', '').strip()
        endpoint_path = request.form.get('endpoint', '').strip() # 'endpoint' is field name for path
        payload_template = request.form.get('http_payload', '').strip()
        raw_headers = request.form.get('raw_headers', '').strip()
        headers_dict = parse_raw_headers(raw_headers) if raw_headers else {}

    # Ensure required fields for testing are present
    if not hostname or not endpoint_path or not payload_template:
        flash("Hostname, Endpoint Path, and Payload are required for testing.", "error")
        if endpoint_id:
            return redirect(url_for(".view_endpoint_details", endpoint_id=endpoint_id))
        else:
            # Need to pass back form data to re-populate create form
            return render_template('create_endpoint.html', 
                                   payload_templates=PAYLOAD_TEMPLATES, 
                                   # Pass back other form values: name, hostname, etc.
                                   name=request.form.get('name'),
                                   hostname=hostname,
                                   endpoint=endpoint_path, # Field name
                                   http_payload=payload_template,
                                   raw_headers=request.form.get('raw_headers'))


    if "{{INJECT_PROMPT}}" not in payload_template:
        flash("Error: The HTTP payload must contain '{{INJECT_PROMPT}}' token.", 'error')
        # Redirect logic... (similar to original)
        if endpoint_id:
            return redirect(url_for('.view_endpoint_details', endpoint_id=endpoint_id))
        else:
            return redirect(url_for('.create_endpoint_form')) # Or render_template with error

    headers_str = "\n".join(f"{k}: {v}" for k, v in headers_dict.items())
    test_prompt_value = "What is 4 + 3?" # Or get from form if you want dynamic test prompt
    actual_payload_sent = payload_template.replace("{{INJECT_PROMPT}}", test_prompt_value)

    try:
        json.loads(actual_payload_sent)
    except json.JSONDecodeError as e:
        flash(f"Error: Invalid JSON in payload: {str(e)}", 'error')
        # Redirect logic...
        if endpoint_id:
            return redirect(url_for('.view_endpoint_details', endpoint_id=endpoint_id))
        else:
            return redirect(url_for('.create_endpoint_form'))


    # Hostname processing (protocol, container internal)
    processed_hostname = hostname
    if not processed_hostname.startswith(('http://', 'https://')):
        processed_hostname = 'http://' + processed_hostname
    if processed_hostname.startswith('http://127.0.0.1') or processed_hostname.startswith('http://localhost'):
        processed_hostname = processed_hostname.replace('127.0.0.1', 'host.containers.internal').replace('localhost', 'host.containers.internal')

    result = replay_post_request(processed_hostname, endpoint_path, actual_payload_sent, headers_str)
    
    test_result_data = {
        'payload_sent': actual_payload_sent,
        'response_data': result.get("response_text"),
        'status_code': result.get("status_code", "N/A"),
        'headers_sent': result.get("headers_sent", {}) # Headers actually sent by replay_post_request
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest': # If test was AJAX
        return jsonify(test_result_data)

    if endpoint_id:
        # Pass data back to the view_endpoint template
        return render_template('view_endpoint.html', endpoint=endpoint, test_result=test_result_data)
    else:
        # Pass data back to the create_endpoint template
        return render_template('create_endpoint.html',
                               payload_templates=PAYLOAD_TEMPLATES,
                               # Re-populate form with original values
                               name=request.form.get('name'),
                               hostname=hostname,
                               endpoint=endpoint_path,
                               http_payload=payload_template, # Original template
                               raw_headers=request.form.get('raw_headers'),
                               # Test results
                               test_result=test_result_data
                               )