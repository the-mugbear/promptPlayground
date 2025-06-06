# app/endpoints/views_core.py
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
import json
import re

from extensions import db 
from models.model_Endpoints import Endpoint, EndpointHeader
from services.endpoints.api_templates import PAYLOAD_TEMPLATES 
from services.common.header_parser_service import parse_raw_headers, headers_from_apiheader_list 

from . import endpoints_bp

def get_endpoint_form_data(endpoint_id=None):
    """
    Extracts common endpoint data from the form.
    If endpoint_id is provided, it fetches existing data for defaults.
    """
    form_data = {}
    endpoint_obj = None

    if endpoint_id:
        endpoint_obj = Endpoint.query.options(joinedload(Endpoint.headers)).get_or_404(endpoint_id)

    form_data["name"] = request.form.get("name", endpoint_obj.name if endpoint_obj else "").strip()
    form_data["hostname"] = request.form.get("hostname", endpoint_obj.hostname if endpoint_obj else "").strip()
    form_data["endpoint_path"] = request.form.get("endpoint", endpoint_obj.endpoint if endpoint_obj else "").strip()
    
    # Default to 'POST' for new endpoints, a common choice for endpoints with payloads.
    # Use .upper() to ensure consistent casing (e.g., 'post' becomes 'POST').
    default_method = endpoint_obj.method if endpoint_obj else "POST"
    form_data["method"] = request.form.get("method", default_method).strip().upper()

    # Payload logic: prioritize form, then DB, then empty
    payload_from_form = request.form.get("http_payload", "").strip()
    if payload_from_form:
        form_data["payload"] = payload_from_form
    elif endpoint_obj and endpoint_obj.http_payload:
        form_data["payload"] = endpoint_obj.http_payload
    else:
        form_data["payload"] = ""

    # Raw headers logic: prioritize form, then DB (parsed), then empty
    raw_headers_from_form = request.form.get("raw_headers", None) 
    if raw_headers_from_form is not None: 
        form_data["raw_headers"] = raw_headers_from_form.strip()
        form_data["parsed_headers"] = parse_raw_headers(form_data["raw_headers"])
    elif endpoint_obj and endpoint_obj.headers:
        stored_headers_dict = headers_from_apiheader_list(endpoint_obj.headers)
        form_data["raw_headers"] = "\n".join(f"{k}: {v}" for k, v in stored_headers_dict.items())
        form_data["parsed_headers"] = stored_headers_dict
    else:
        form_data["raw_headers"] = ""
        form_data["parsed_headers"] = {}
        
    form_data["endpoint_obj"] = endpoint_obj
    return form_data

@endpoints_bp.route('/', methods=['GET'])
@login_required # Assuming login_required is still needed
def list_endpoints():
    endpoints = Endpoint.query.all()
    return render_template('endpoints/list_endpoints.html', endpoints=endpoints)

@endpoints_bp.route('/create', methods=['GET'])
@login_required
def create_endpoint_form():
    return render_template('endpoints/create_endpoint.html', payload_templates=PAYLOAD_TEMPLATES)

@endpoints_bp.route('/<int:endpoint_id>', methods=['GET'])
@login_required
def view_endpoint_details(endpoint_id):
    # Use the get_endpoint_form_data to pre-populate or just fetch directly
    ep = Endpoint.query.options(joinedload(Endpoint.headers)).get_or_404(endpoint_id)
    # Pass the test_result if coming from a test_endpoint redirect
    test_result = request.args.get('test_result', None)
    return render_template('endpoints/view_endpoint.html', endpoint=ep, test_result=test_result)


@endpoints_bp.route('/create', methods=['POST'])
@login_required
def handle_create_endpoint():
    try:
        form_data = get_endpoint_form_data() # Ensure this helper doesn't redirect on its own

        # Validation 1: Check for required fields
        if not form_data["name"] or not form_data["hostname"] or not form_data["endpoint_path"]:
            error_msg = "Name, hostname, and endpoint path are required."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_msg, 'field_errors': {
                    'name': 'Required' if not form_data["name"] else None,
                    'hostname': 'Required' if not form_data["hostname"] else None,
                    'endpoint_path': 'Required' if not form_data["endpoint_path"] else None
                }}), 400 # Bad Request
            flash(error_msg, "error")
            # For non-AJAX, re-render the form with errors and existing data
            return render_template("endpoints/create_endpoint.html",
                                   payload_templates=PAYLOAD_TEMPLATES,
                                   name=form_data["name"],
                                   hostname=form_data["hostname"],
                                   endpoint=form_data["endpoint_path"], # Use 'endpoint' for path form field
                                   http_payload=form_data["payload"],
                                   raw_headers=form_data["raw_headers"],
                                   flash_error=error_msg) # Custom context var for error


        # Validation 2: Check for {{INJECT_PROMPT}} in payload using a regular expression
        # This ensures either {{INJECT_PROMPT}} or {{INJECT_PROMPT | tojson}} is present.
        token_regex = re.compile(r'\{\{\s*INJECT_PROMPT\s*(?:\|\s*tojson\s*)?\}\}')
        if not token_regex.search(form_data["payload"]):
            error_msg = "HTTP Payload must contain the {{INJECT_PROMPT}} token."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_msg, 'field_errors': {'http_payload': error_msg}}), 400
            flash(error_msg, "error")
            # This part for re-rendering the template remains the same
            return render_template("endpoints/create_endpoint.html",
                                payload_templates=PAYLOAD_TEMPLATES,
                                name=form_data["name"],
                                hostname=form_data["hostname"],
                                endpoint=form_data["endpoint_path"],
                                http_payload=form_data["payload"],
                                raw_headers=form_data["raw_headers"],
                                flash_error=error_msg)

        # Validation 3: Ensure payload has a valid JSON structure, allowing for Jinja2 placeholders
        try:
            payload_str = form_data["payload"].strip()
            if payload_str.startswith('{') or payload_str.startswith('['):
                # To validate, temporarily replace all {{...}} blocks with a valid JSON string value
                # This checks the structure without being broken by template tags.
                # Using re.sub is robust for finding all placeholders.
                cleaned_for_validation = re.sub(r'{{\s*.*?\s*}}', '"dummy_value"', payload_str)
                
                # Now, try to parse the cleaned string
                json.loads(cleaned_for_validation)

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON structure in template: {str(e)}"
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_msg, 'field_errors': {'http_payload': error_msg}}), 400
            flash(error_msg, "error")
            return render_template("endpoints/create_endpoint.html",
                                flash_error=error_msg)

        # If all validations pass:
        endpoint = Endpoint(
            name=form_data["name"],
            hostname=form_data["hostname"],
            endpoint=form_data["endpoint_path"],
            method=form_data["method"],
            http_payload=form_data["payload"],
            user_id=current_user.id
        )
        db.session.add(endpoint)
        db.session.commit()

        # Process headers if provided
        if form_data["raw_headers"]:
            parsed_headers = parse_raw_headers(form_data["raw_headers"]) # Assuming get_endpoint_form_data doesn't provide parsed_headers
            for key, value in parsed_headers.items():
                header = EndpointHeader(endpoint_id=endpoint.id, key=key, value=value)
                db.session.add(header)
            db.session.commit() # Commit headers

        # Success response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'message': "Endpoint created successfully!",
                'redirect_url': url_for(".view_endpoint_details", endpoint_id=endpoint.id)
            }), 201 # HTTP 201 Created is appropriate for successful POST creating a resource

        flash("Endpoint created successfully!", "success")
        return redirect(url_for(".view_endpoint_details", endpoint_id=endpoint.id))

    except Exception as e:
        db.session.rollback()
        # Log the full exception for debugging on the server
        current_app.logger.error(f"Error creating endpoint: {str(e)}", exc_info=True)
        error_msg = f"An unexpected error occurred: {str(e)}" # Or a more generic message
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': error_msg}), 500 # Internal Server Error

        flash(error_msg, "error")
        # For non-AJAX, re-render form, trying to preserve data if possible
        # form_data might not be fully populated if exception was early
        return render_template("endpoints/create_endpoint.html",
                               payload_templates=PAYLOAD_TEMPLATES,
                               name=request.form.get('name', ''), # Get from original request
                               hostname=request.form.get('hostname', ''),
                               endpoint=request.form.get('endpoint', ''),
                               http_payload=request.form.get('http_payload', ''),
                               raw_headers=request.form.get('raw_headers', ''),
                               flash_error="An unexpected error occurred creating the endpoint.")


@endpoints_bp.route('/<int:endpoint_id>/update', methods=['POST'])
@login_required
def update_endpoint(endpoint_id):
    # Use the get_endpoint_form_data helper
    form_data = get_endpoint_form_data(endpoint_id=endpoint_id)
    endpoint_obj = form_data["endpoint_obj"] # Fetched by get_endpoint_form_data

    if not endpoint_obj: # Should be handled by get_or_404 in helper
        return redirect(url_for(".list_endpoints"))

    # Update fields
    endpoint_obj.name = form_data["name"]
    endpoint_obj.hostname = form_data["hostname"]
    endpoint_obj.endpoint = form_data["endpoint_path"]
    endpoint_obj.method = form_data["method"]
    endpoint_obj.http_payload = form_data["payload"]

    # Remove existing headers
    EndpointHeader.query.filter_by(endpoint_id=endpoint_obj.id).delete()

    # Add new headers from form_data["parsed_headers"]
    if form_data["raw_headers"]: # Check if raw_headers string is present
        for key, value in form_data["parsed_headers"].items():
            new_header = EndpointHeader(endpoint_id=endpoint_obj.id, key=key, value=value)
            db.session.add(new_header)
    try:
        db.session.commit()
        flash("Endpoint updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating endpoint: {str(e)}", "error")

    return redirect(url_for(".view_endpoint_details", endpoint_id=endpoint_id))

@endpoints_bp.route('/<int:endpoint_id>/delete', methods=['POST'])
@login_required
def delete_endpoint(endpoint_id):
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    # Consider related data like APIHeaders, ManualTestRecord if they should be cascade deleted
    # or handled here. SQLAlchemy cascade options on models are best.
    db.session.delete(endpoint_obj)
    db.session.commit()
    flash(f'Endpoint {endpoint_id} deleted successfully.', 'success')
    return redirect(url_for('.list_endpoints'))