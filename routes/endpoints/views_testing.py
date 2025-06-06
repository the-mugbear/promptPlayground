# app/endpoints/views_testing.py
from flask import request, jsonify, flash, redirect, url_for, render_template
from flask_login import login_required
from sqlalchemy.orm import joinedload
import json

from extensions import db
from models.model_Endpoints import Endpoint
from services.common.http_request_service import execute_api_request
from services.common.header_parser_service import parse_raw_headers, headers_from_apiheader_list
from services.endpoints.api_templates import PAYLOAD_TEMPLATES

from . import endpoints_bp

@endpoints_bp.route('/get_suggestions', methods=['GET'])
@login_required
def get_endpoint_suggestions():
    """
    Provides suggestions for hostnames, paths, and payloads
    based on existing distinct values in the database.
    Used for autocompletion or suggestions in forms.
    """
    hostnames = [row.hostname for row in Endpoint.query.with_entities(Endpoint.hostname).distinct().all() if row.hostname]
    paths = [row.endpoint for row in Endpoint.query.with_entities(Endpoint.endpoint).distinct().all() if row.endpoint]
    payloads = [row.http_payload for row in Endpoint.query.with_entities(Endpoint.http_payload).distinct().all() if row.http_payload]

    return jsonify({
        "hostnames": hostnames,
        "paths": paths,
        "payloads": payloads
    })

@endpoints_bp.route('/test', methods=['POST']) # Route for testing a new, unsaved endpoint configuration (e.g., from create_endpoint.html)
@endpoints_bp.route('/<int:endpoint_id>/test', methods=['POST']) # Route for testing an existing endpoint (e.g., from view_endpoint.html)
@login_required
def test_endpoint(endpoint_id=None):
    """
    Tests an endpoint configuration.
    This function serves two main scenarios:
    1. If `endpoint_id` is None (POST to /test):
       It tests a new configuration, typically submitted from the 'create_endpoint' page.
       It expects all necessary data (hostname, path, payload, headers) from `request.form`.
    2. If `endpoint_id` is provided (POST to /<endpoint_id>/test):
       It tests an existing endpoint. It fetches the endpoint's details from the database.
       It allows overriding these database values with data from `request.form` if provided
       (e.g., live edits from 'view_endpoint.html' sent via AJAX FormData).

    Handles both AJAX (returns JSON) and traditional form submissions (returns rendered template with results).
    """
    db_endpoint_obj = None  # To store the endpoint object if fetched from DB

    # Variables to hold the actual values that will be used for the test
    effective_hostname = None
    effective_endpoint_path = None
    effective_payload_template = None
    effective_headers_dict = {} # Parsed headers (key: value)

    # Determine if the current request is AJAX
    is_ajax_request = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if endpoint_id:
        # Scenario 2: Testing an existing endpoint (potentially with live edits)
        db_endpoint_obj = Endpoint.query.options(joinedload(Endpoint.headers)).get_or_404(endpoint_id)
        
        form_hostname = request.form.get('hostname')
        form_endpoint_path = request.form.get('endpoint') 
        form_http_payload = request.form.get('http_payload')
        form_raw_headers = request.form.get('raw_headers')

        effective_hostname = form_hostname if form_hostname is not None else db_endpoint_obj.hostname
        effective_endpoint_path = form_endpoint_path if form_endpoint_path is not None else db_endpoint_obj.endpoint
        effective_payload_template = form_http_payload if form_http_payload is not None else db_endpoint_obj.http_payload

        if form_raw_headers is not None:
            effective_headers_dict = parse_raw_headers(form_raw_headers)
        elif db_endpoint_obj.headers: 
            effective_headers_dict = headers_from_apiheader_list(db_endpoint_obj.headers)
            
    else:
        # Scenario 1: Testing a new, unsaved configuration
        effective_hostname = request.form.get('hostname', '').strip()
        effective_endpoint_path = request.form.get('endpoint', '').strip()
        effective_payload_template = request.form.get('http_payload', '').strip()
        raw_headers_from_form = request.form.get('raw_headers', '').strip()
        effective_headers_dict = parse_raw_headers(raw_headers_from_form) if raw_headers_from_form else {}

    # --- Validation and AJAX-Friendly Error Handling ---
    if not effective_hostname or not effective_endpoint_path or not effective_payload_template:
        error_msg = "Hostname, Endpoint Path, and Payload are required for testing."
        if is_ajax_request: # MODIFIED HERE
            return jsonify(error=error_msg, status_code=400, response_data=None, headers_sent={}), 400
        flash(error_msg, "error")
        return redirect(url_for(".view_endpoint_details", endpoint_id=endpoint_id) if endpoint_id else url_for(".create_endpoint_form"))

    if "{{INJECT_PROMPT}}" not in effective_payload_template:
        error_msg = "Error: The HTTP payload must contain '{{INJECT_PROMPT}}' token."
        if is_ajax_request: # MODIFIED HERE
            return jsonify(error=error_msg, status_code=400, response_data=None, headers_sent={}), 400
        flash(error_msg, 'error')
        return redirect(url_for(".view_endpoint_details", endpoint_id=endpoint_id) if endpoint_id else url_for(".create_endpoint_form"))

    test_prompt_value = "What is 4 + 3?" 
    actual_payload_sent = effective_payload_template.replace("{{INJECT_PROMPT}}", test_prompt_value)

    try:
        json.loads(actual_payload_sent)
    except json.JSONDecodeError as e:
        error_msg = f"Error: Invalid JSON in final payload after injection: {str(e)}"
        if is_ajax_request: # MODIFIED HERE
            return jsonify(error=error_msg, status_code=400, response_data=None, headers_sent={}), 400
        flash(error_msg, 'error')
        if endpoint_id:
            return redirect(url_for('.view_endpoint_details', endpoint_id=endpoint_id))
        else:
            return redirect(url_for('.create_endpoint_form'))

    # --- Prepare and Execute the Test HTTP Request ---
    processed_hostname = effective_hostname 
    if not processed_hostname.startswith(('http://', 'https://')):
        processed_hostname = 'http://' + processed_hostname
    if processed_hostname.startswith('http://127.0.0.1') or processed_hostname.startswith('http://localhost'):
        processed_hostname = processed_hostname.replace('127.0.0.1', 'host.containers.internal').replace('localhost', 'host.containers.internal')
        
    headers_str = "\n".join(f"{k}: {v}" for k, v in effective_headers_dict.items())
    
    result = execute_api_request(processed_hostname, effective_endpoint_path, actual_payload_sent, headers_str)
    
    test_result_data = {
        'payload_sent': actual_payload_sent,
        'response_data': result.get("response_text") if result else "Error during replay or no response", # Graceful handling if result is None
        'status_code': result.get("status_code", "N/A") if result else "N/A",
        'headers_sent': result.get("headers_sent", {}) if result else {}
    }
    
    # --- Return Response (AJAX or Rendered Template) ---
    if is_ajax_request: # MODIFIED HERE
        return jsonify(test_result_data)
    else:
        if endpoint_id:
            return render_template('view_endpoint.html', endpoint=db_endpoint_obj, test_result=test_result_data)
        else:
            return render_template('create_endpoint.html',
                                   payload_templates=PAYLOAD_TEMPLATES,
                                   name=request.form.get('name'), 
                                   hostname=effective_hostname,
                                   endpoint=effective_endpoint_path, 
                                   http_payload=effective_payload_template, 
                                   raw_headers=request.form.get('raw_headers', ''), 
                                   test_result=test_result_data
                                  )