from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from extensions import db
from models.model_Endpoints import Endpoint, APIHeader
from services.endpoints.endpoint_services import parse_headers_from_form, parse_headers_from_list_of_dict, headers_from_apiheader_list, parse_raw_headers
from services.endpoints.api_templates import PAYLOAD_TEMPLATES
from werkzeug.exceptions import BadRequest
from sqlalchemy.orm import joinedload
import requests
import json

endpoints_bp = Blueprint('endpoints_bp', __name__, url_prefix='/endpoints')

# ********************************
# ROUTES
# ********************************
@endpoints_bp.route('/', methods=['GET'])
def list_endpoints():
    """
    GET /endpoints -> Displays a table/list of existing endpoints
    """
    endpoints = Endpoint.query.all()
    return render_template('endpoints/list_endpoints.html', endpoints=endpoints)

@endpoints_bp.route('/create', methods=['GET'])
def create_endpoint_form():
    """
    GET /endpoints/create -> Renders a form to create a new endpoint & headers
    """
    return render_template('endpoints/create_endpoint.html', payload_templates=PAYLOAD_TEMPLATES)

@endpoints_bp.route('/<int:endpoint_id>', methods=['GET'])
def view_endpoint_details(endpoint_id):
    """
    GET /endpoints/<id> -> Shows the details of a single endpoint, including headers
    """
    # Use joinedload to eagerly load the headers associated with the endpoint. 
    ep = Endpoint.query.options(joinedload(Endpoint.headers)).get_or_404(endpoint_id) 
    return render_template('endpoints/view_endpoint.html', endpoint=ep)

# ********************************
# SERVICES
# ********************************
@endpoints_bp.route('/create', methods=['POST'])
def handle_create_endpoint():
    """
    POST /endpoints/create -> Saves the new endpoint info and its headers in the DB
    
    Expected form data:
        - hostname: str
        - endpoint: str
        - http_payload: str (must contain {{INJECT_PROMPT}} if present)
        - raw_headers: str (newline-separated key:value pairs)
        
    Returns:
        Redirect to endpoints list on success
        
    Raises:
        BadRequest: If required fields are missing or if {{INJECT_PROMPT}} is not found
    """
    try:
        # Retrieve the new name field from the form
        name = request.form.get('name', '').strip()
        hostname = request.form.get('hostname', '').strip()
        endpoint_path = request.form.get('endpoint', '').strip()
        raw_payload = request.form.get('http_payload', '').strip()

        # 1) Validate minimal required fields
        if not name or not hostname or not endpoint_path:
            raise BadRequest("Missing required fields: 'name', 'hostname' or 'endpoint'.")

        # 2) If the user provided a payload, ensure it contains {{INJECT_PROMPT}}
        if raw_payload:
            if '{{INJECT_PROMPT}}' not in raw_payload:
                raise BadRequest("The HTTP payload must contain '{{INJECT_PROMPT}}'.")
            # Store exactly as user typed
            formatted_payload = raw_payload
        else:
            # If no payload, either store a minimal template or raise an error
            # Option A: create a minimal default
            formatted_payload = """{
                "messages": [
                    {"role": "user", "content": "{{INJECT_PROMPT}}"}
                ]
            }"""
                        # Option B: raise an error if you want to enforce user always provides
            # raise BadRequest("No payload provided, must contain {{INJECT_PROMPT}}.")

        # 3) Create the Endpoint
        new_endpoint = Endpoint(
            name=name,
            hostname=hostname,
            endpoint=endpoint_path,
            http_payload=formatted_payload
        )
        db.session.add(new_endpoint)
        db.session.flush()

        # 4) Parse headers from user
        raw_headers = request.form.get('raw_headers', '')
        lines = [line.strip() for line in raw_headers.split('\n') if line.strip()]
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                header = APIHeader(endpoint_id=new_endpoint.id, key=key, value=value)
                db.session.add(header)

        db.session.commit()
        flash('Endpoint created successfully!', 'success')
        # Redirect to the newly created endpoint's details page
        return redirect(url_for('endpoints_bp.view_endpoint_details', endpoint_id=new_endpoint.id))


    except BadRequest as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('endpoints_bp.create_endpoint'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating endpoint: {str(e)}', 'error')
        return redirect(url_for('endpoints_bp.create_endpoint'))

@endpoints_bp.route('/get_suggestions', methods=['GET'])
def get_endpoint_suggestions():
    """
    Return distinct hostnames, paths, and possibly payload samples
    from existing Endpoint records. The client will use these as suggestions.
    """
    # Distinct hostnames
    hostnames = (Endpoint.query
                 .with_entities(Endpoint.hostname)
                 .distinct()
                 .all())
    hostname_list = [row.hostname for row in hostnames if row.hostname]

    # Distinct endpoint paths
    paths = (Endpoint.query
             .with_entities(Endpoint.endpoint)
             .distinct()
             .all())
    path_list = [row.endpoint for row in paths if row.endpoint]

    # Optional: sample http_payload values (be mindful if they can be large)
    payloads = (Endpoint.query
                .with_entities(Endpoint.http_payload)
                .distinct()
                .all())
    payload_list = [row.http_payload for row in payloads if row.http_payload]

    return jsonify({
        "hostnames": hostname_list,
        "paths": path_list,
        "payloads": payload_list
    })

@endpoints_bp.route('/<int:endpoint_id>/delete', methods=['POST'])
def delete_endpoint(endpoint_id):
    """
    POST /endpoints/<id>/delete -> Deletes the specified endpoint
    """
    endpoint = Endpoint.query.get_or_404(endpoint_id)

    # If you have dependencies or references to test runs, consider checking them here
    # e.g. if you want to block deletion if it's used in some runs

    db.session.delete(endpoint)
    db.session.commit()
    flash(f'Endpoint {endpoint_id} deleted successfully.', 'success')

    return redirect(url_for('endpoints_bp.list_endpoints'))

# Used on the register/create endpoint page to test an endpoint before it's committed/saved
@endpoints_bp.route('/test_temporary', methods=['POST'])
def test_temporary_endpoint():
    """
    POST /endpoints/test_temporary -> Does a one-off test with the user-provided fields,
    without storing or fetching anything from DB.
    """
    hostname = request.form.get("hostname", "").strip()
    endpoint_path = request.form.get("endpoint", "").strip()
    actual_payload = request.form.get("http_payload", "").strip()

    # 2) Replace {{INJECT_PROMPT}} if present
    if "{{INJECT_PROMPT}}" in actual_payload:
        actual_payload = actual_payload.replace("{{INJECT_PROMPT}}", 'What is 4 + 3?')

    raw_headers = request.form.get("raw_headers", "").strip()

    # Construct final_headers from raw_headers
    final_headers = parse_raw_headers(raw_headers)
    # If user didn't specify 'Content-Type', let's default
    final_headers.setdefault("Content-Type", "application/json")

    test_payload = actual_payload  # We'll pass it back to the template
    response_text = ""
    try:
        import requests
        url = f"{hostname.rstrip('/')}/{endpoint_path.lstrip('/')}"

        # Try parse as JSON
        try:
            parsed_json = json.loads(actual_payload)
            resp = requests.post(url, json=parsed_json, headers=final_headers, timeout=120, verify=False)
        except json.JSONDecodeError:
            # fallback to raw text
            resp = requests.post(url, data=actual_payload, headers=final_headers, timeout=120)

        resp.raise_for_status()

        # Attempt to parse response as JSON
        try:
            parsed_resp = json.loads(resp.text)
            response_text = json.dumps(parsed_resp, indent=2)
        except json.JSONDecodeError:
            response_text = resp.text
    except requests.exceptions.RequestException as e:
        response_text = f"Error: {str(e)}"

    # Re-render the 'create_endpoint.html' template, but pass in test results
    return render_template(
        'endpoints/create_endpoint.html',
        test_payload=test_payload,
        test_response=response_text,
        test_status_code=resp.status_code,         # e.g., 200
        test_headers_sent=final_headers             # the headers dictionary used in the POST
    )


@endpoints_bp.route('/<int:endpoint_id>/update', methods=['POST'])
def update_endpoint(endpoint_id):
    # Fetch the existing endpoint record
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    
    # Get form values and trim extra whitespace
    name = request.form.get('name', '').strip()
    hostname = request.form.get('hostname', '').strip()
    endpoint_path = request.form.get('endpoint', '').strip()
    http_payload = request.form.get('http_payload', '').strip()
    raw_headers = request.form.get('raw_headers', '').strip()

    # Validate required fields
    if not hostname or not endpoint_path:
        flash("Hostname and Path are required.", "error")
        return redirect(url_for('endpoints_bp.view_endpoint_details', endpoint_id=endpoint_id))

    # Update the endpoint fields
    endpoint.name = name
    endpoint.hostname = hostname
    endpoint.endpoint = endpoint_path
    endpoint.http_payload = http_payload

    # Update headers: remove existing headers and add new ones from the raw input
    for header in endpoint.headers:
        db.session.delete(header)
    endpoint.headers = []  # Clear out the relationship list

    # Process the raw headers input (each header on a new line, "Key: Value" format)
    if raw_headers:
        lines = [line.strip() for line in raw_headers.split('\n') if line.strip()]
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                new_header = APIHeader(endpoint_id=endpoint.id, key=key.strip(), value=value.strip())
                db.session.add(new_header)
                endpoint.headers.append(new_header)

    try:
        db.session.commit()
        flash("Endpoint updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error updating endpoint: " + str(e), "error")

    # Redirect back to the view details page
    return redirect(url_for('endpoints_bp.view_endpoint_details', endpoint_id=endpoint_id))


# TODO: Remove this function as it ONLY serves as test endpoint on the details page for an endpoint. Should be one test function
@endpoints_bp.route('/<int:endpoint_id>/test', methods=['POST'])
def test_endpoint(endpoint_id):
    endpoint = Endpoint.query.get_or_404(endpoint_id)

    # 1) Payload override vs. stored payload
    override_payload = request.form.get('test_payload', '').strip()
    actual_payload = override_payload or (endpoint.http_payload or "")

    # 2) Headers from DB
    existing_headers_dict = headers_from_apiheader_list(endpoint.headers)

    # 3) Possibly parse user's raw header overrides
    raw_headers = request.form.get('raw_headers', '').strip()
    user_headers_dict = parse_raw_headers(raw_headers)

    # Merge them. If the user typed a key that already exists, they override it
    final_headers = {**existing_headers_dict, **user_headers_dict}
    response_text = ""

    try:
        # lstrip and rstrip used to remove leading chars from left and right sides respectively
        url = f"{endpoint.hostname.rstrip('/')}/{endpoint.endpoint.lstrip('/')}"
        # If actual_payload is valid JSON, we do requests.post(..., json=...)

        # We'll do a quick JSON parse attempt:
        try:
            parsed_json = json.loads(actual_payload)
            # If parse succeeded, let's ensure we have "Content-Type" set if user didn't
            final_headers.setdefault("Content-Type", "application/json")
            resp = requests.post(url, json=parsed_json, headers=final_headers, timeout=120)

        except json.JSONDecodeError:
            # fallback to raw text
            # if user didn't specify Content-Type, let's default to something
            final_headers.setdefault("Content-Type", "application/json")
            resp = requests.post(url, data=actual_payload, headers=final_headers, timeout=120)

        resp.raise_for_status()

        # Pretty print response for presentation to front
        try:
            # Attempt to parse as JSON
            parsed_resp = json.loads(resp.text)
            # Re-dump with pretty indentation
            response_text = json.dumps(parsed_resp, indent=2)

        except json.JSONDecodeError:
            # If it's not valid JSON, fallback to the raw text
            response_text = resp.text

    except requests.exceptions.RequestException as e:
        response_text = f"Error: {str(e)}"

    return render_template(
        'endpoints/view_endpoint.html',
        endpoint=endpoint,
        override_payload=override_payload,
        test_payload=actual_payload,
        test_response=response_text
    )


# AJAX call from Create Test Run page to support page functionality
@endpoints_bp.route('/<int:endpoint_id>/json', methods=['GET'])
def get_endpoint_json(endpoint_id):
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    return jsonify(endpoint.to_dict())