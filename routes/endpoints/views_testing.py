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
from services.common.templating_service import render_template_string

from . import endpoints_bp

@endpoints_bp.route('/get_suggestions', methods=['GET'])
@login_required
def get_endpoint_suggestions():
    """
    Provides suggestions for hostnames, paths, and payloads
    based on existing distinct values in the database.
    Used for autocompletion or suggestions in forms.
    """
    hostnames = [row.hostname for row in Endpoint.query.with_entities(
        Endpoint.hostname).distinct().all() if row.hostname]
    paths = [row.endpoint for row in Endpoint.query.with_entities(
        Endpoint.endpoint).distinct().all() if row.endpoint]
    payloads = [row.http_payload for row in Endpoint.query.with_entities(
        Endpoint.http_payload).distinct().all() if row.http_payload]

    return jsonify({
        "hostnames": hostnames,
        "paths": paths,
        "payloads": payloads
    })


# Route for testing a new, unsaved endpoint configuration
@endpoints_bp.route('/test', methods=['POST'])
# Route for testing an existing endpoint (e.g., from view_endpoint.html)
@endpoints_bp.route('/<int:endpoint_id>/test', methods=['POST'])
@login_required
def test_endpoint(endpoint_id=None):
    """
    Tests an endpoint configuration, handling both AJAX and standard form submissions
    from both the create and view/edit pages.
    """
    endpoint = db.session.get(Endpoint, endpoint_id)
    if not endpoint:
        flash("Endpoint not found.", "danger")
        return redirect(url_for('endpoints_bp.list_endpoints'))

    # Gather effective data from form, with fallback to DB object if it exists
    form_data = {
        'hostname': request.form.get('hostname', endpoint.hostname if endpoint else ''),
        'endpoint': request.form.get('endpoint', endpoint.endpoint if endpoint else ''),
        'http_payload': request.form.get('http_payload', endpoint.http_payload if endpoint else ''),
        'method': request.form.get('method', endpoint.method if endpoint else 'POST'),
        'raw_headers': request.form.get('raw_headers')
    }

    raw_headers = form_data['raw_headers']
    if raw_headers is not None:
        effective_headers_dict = parse_raw_headers(raw_headers)
    elif endpoint and endpoint.headers:
        effective_headers_dict = headers_from_apiheader_list(
            endpoint.headers)
    else:
        effective_headers_dict = {}

    is_ajax_request = request.headers.get(
        'X-Requested-With') == 'XMLHttpRequest'

    # --- Validation ---
    # Helper function to avoid repetition when handling validation errors
    def handle_validation_error(error_msg):
        if is_ajax_request:
            return jsonify(error=error_msg), 400
        else:
            flash(error_msg, 'error')
            # Re-render the form the user was on, preserving their input
            template = 'endpoints/view_endpoint.html' if endpoint_id else 'endpoints/create_endpoint.html'
            return render_template(template, endpoint=endpoint, **form_data)

    if not all([form_data['hostname'], form_data['endpoint'], form_data['http_payload']]):
        return handle_validation_error("Hostname, Endpoint Path, and Payload are required for testing.")

    # --- Payload Rendering ---
    try:
        render_context = {
            "INJECT_PROMPT": "This is a test prompt to validate the template.",
            "model": "test-model"  # Provide a dummy model for templates that need it
        }
        # Use the new function name
        actual_payload_sent = render_template_string(
            form_data['http_payload'], render_context)
        
        # Validate that the rendered payload is valid JSON
        json.loads(actual_payload_sent)

    # Catch specific JSON error or a generic one for other template issues
    except json.JSONDecodeError as e:
        return handle_validation_error(f"Rendered payload is not valid JSON: {e}")
    except Exception as e:
        return handle_validation_error(f"Error in payload template: {e}")

    # --- Execute the Test HTTP Request ---
    result = execute_api_request(
        method=form_data['method'].upper(),
        hostname_url=form_data['hostname'],
        endpoint_path=form_data['endpoint'],
        raw_headers_or_dict=effective_headers_dict,
        http_payload_as_string=actual_payload_sent
    )

    # --- Prepare Final Result Data ---
    test_result_data = {
        'status_code': result.get("status_code", "N/A"),
        'response_data': result.get("response_body"),
        'request_headers_sent': result.get("request_headers_sent", {}),
        'error_message': result.get("error_message")
    }
    try:
        test_result_data['payload_sent'] = json.loads(actual_payload_sent)
    except json.JSONDecodeError:
        test_result_data['payload_sent'] = actual_payload_sent

    # --- Return Response (AJAX or Rendered Template) ---
    if is_ajax_request:
        return jsonify(test_result_data)
    else:
        # For a standard form post, re-render the page with the results displayed
        flash("Endpoint test completed!", "info")
        template = 'endpoints/view_endpoint.html' if endpoint_id else 'endpoints/create_endpoint.html'
        return render_template(template, endpoint=endpoint, test_result=test_result_data, **form_data)
