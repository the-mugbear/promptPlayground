from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from extensions import db
from models.model_Endpoints import Endpoint, APIHeader
from services.endpoints.api_templates import PAYLOAD_TEMPLATES
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import parse_raw_headers, headers_from_apiheader_list
from werkzeug.exceptions import BadRequest
from sqlalchemy.orm import joinedload

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
    ep = Endpoint.query.options(joinedload(Endpoint.headers)).get_or_404(endpoint_id)
    return render_template('endpoints/view_endpoint.html', endpoint=ep)

# ********************************
# SERVICES
# ********************************
@endpoints_bp.route('/create', methods=['POST'])
def handle_create_endpoint():
    try:
        data = get_endpoint_form_data(default_payload=(
            '''{
                "messages": [
                    {"role": "user", "content": "{{INJECT_PROMPT}}"}
                ]
            }'''
        ))
        # Validate required fields for creation
        if not data["name"] or not data["hostname"] or not data["endpoint_path"]:
            raise BadRequest("Missing required fields: 'name', 'hostname' or 'endpoint'.")
        # For creation, ensure the payload contains the injection prompt.
        if data["payload"] and "{{INJECT_PROMPT}}" not in data["payload"]:
            raise BadRequest("The HTTP payload must contain '{{INJECT_PROMPT}}'.")
    
        new_endpoint = Endpoint(
            name=data["name"],
            hostname=data["hostname"],
            endpoint=data["endpoint_path"],
            http_payload=data["payload"]
        )
        db.session.add(new_endpoint)
        db.session.flush()  # Ensure new_endpoint.id is assigned

        # Use the already parsed headers (which includes the cookie header handled appropriately).
        for key, value in data["parsed_headers"].items():
            header = APIHeader(endpoint_id=new_endpoint.id, key=key, value=value)
            db.session.add(header)

        db.session.commit()
        flash('Endpoint created successfully!', 'success')
        return redirect(url_for('endpoints_bp.view_endpoint_details', endpoint_id=new_endpoint.id))

    except BadRequest as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('endpoints_bp.create_endpoint_form'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating endpoint: {str(e)}', 'error')
        return redirect(url_for('endpoints_bp.create_endpoint_form'))


@endpoints_bp.route('/get_suggestions', methods=['GET'])
def get_endpoint_suggestions():
    """
    Return distinct hostnames, paths, and payloads from existing Endpoint records.
    """
    hostnames = [row.hostname for row in Endpoint.query.with_entities(Endpoint.hostname).distinct().all() if row.hostname]
    paths = [row.endpoint for row in Endpoint.query.with_entities(Endpoint.endpoint).distinct().all() if row.endpoint]
    payloads = [row.http_payload for row in Endpoint.query.with_entities(Endpoint.http_payload).distinct().all() if row.http_payload]

    return jsonify({
        "hostnames": hostnames,
        "paths": paths,
        "payloads": payloads
    })

@endpoints_bp.route('/<int:endpoint_id>/delete', methods=['POST'])
def delete_endpoint(endpoint_id):
    """
    POST /endpoints/<id>/delete -> Deletes the specified endpoint
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    db.session.delete(endpoint_obj)
    db.session.commit()
    flash(f'Endpoint {endpoint_id} deleted successfully.', 'success')
    return redirect(url_for('endpoints_bp.list_endpoints'))

@endpoints_bp.route('/<int:endpoint_id>/update', methods=['POST'])
def update_endpoint(endpoint_id):
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    data = get_endpoint_form_data()
    # Update fields with data from the form (or DB defaults)
    endpoint_obj.name = data["name"]
    endpoint_obj.hostname = data["hostname"]
    endpoint_obj.endpoint = data["endpoint_path"]
    endpoint_obj.http_payload = data["payload"]

    # Remove existing headers
    for header in endpoint_obj.headers:
        db.session.delete(header)
    endpoint_obj.headers = []

    if data["raw_headers"]:
        parsed_headers = parse_raw_headers(data["raw_headers"])
        for key, value in parsed_headers.items():
            new_header = APIHeader(endpoint_id=endpoint_obj.id, key=key, value=value)
            db.session.add(new_header)
            endpoint_obj.headers.append(new_header)

    try:
        db.session.commit()
        flash("Endpoint updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error updating endpoint: " + str(e), "error")

    return redirect(url_for('endpoints_bp.view_endpoint_details', endpoint_id=endpoint_id))


@endpoints_bp.route('/<int:endpoint_id>/json', methods=['GET'])
def get_endpoint_json(endpoint_id):
    """
    GET /endpoints/<id>/json -> Returns the JSON representation of the endpoint.
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    return jsonify(endpoint_obj.to_dict())

@endpoints_bp.route('/test', methods=['POST'])
def test_endpoint():
    """
    Unified endpoint that tests an API.
    If 'endpoint_id' is provided, fetch stored values; otherwise, use form values.
    """
    data = get_endpoint_form_data()
    if "{{INJECT_PROMPT}}" in data["payload"]:
        data["payload"] = data["payload"].replace("{{INJECT_PROMPT}}", "What is 4 + 3?")
    result = replay_post_request(data["hostname"], data["endpoint_path"], data["payload"], data["raw_headers"])
    return render_template(
        data["template"],
        test_payload=data["payload"],
        test_response=result.get("response_text"),
        test_status_code=result.get("status_code", "N/A"),
        test_headers_sent=result.get("headers_sent", {}),
        endpoint=data["endpoint_obj"]
    )

# Helper to consolidate form data extraction across endpoints
def get_endpoint_form_data(default_payload=None):
    """
    Extracts common endpoint data from the form.
    Returns a dictionary with the following keys:
      - endpoint_id: string or None
      - name: endpoint name
      - hostname: API hostname
      - endpoint_path: API path (from the 'endpoint' field)
      - payload: For testing, prioritizes 'test_payload' over 'http_payload'
      - raw_headers: raw header string
      - endpoint_obj: the stored Endpoint (if endpoint_id is provided) or None
      - template: template to use when rendering results
    If no endpoint_id is provided (i.e. creation), then if payload is empty, it is set to default_payload.
    """
    data = {}
    data["endpoint_id"] = request.form.get("endpoint_id", "").strip() or None
    data["name"] = request.form.get("name", "").strip()
    data["hostname"] = request.form.get("hostname", "").strip()
    data["endpoint_path"] = request.form.get("endpoint", "").strip()
    
    test_payload = request.form.get("test_payload", "").strip()
    http_payload = request.form.get("http_payload", "").strip()
    data["payload"] = test_payload if test_payload else http_payload

    # Process raw headers from the form.
    let_raw = request.form.get("raw_headers", "").strip()
    if let_raw:
        parsed = parse_raw_headers(let_raw)
        # Save the reassembled raw_headers string (for display)…
        data["raw_headers"] = "\n".join(f"{k}: {v}" for k, v in parsed.items())
        # …and also save the parsed dictionary.
        data["parsed_headers"] = parsed
    else:
        data["raw_headers"] = ""
        data["parsed_headers"] = {}
    
    if data["endpoint_id"]:
        # For update/test scenarios, fetch stored values for missing fields.
        endpoint_obj = Endpoint.query.get_or_404(data["endpoint_id"])
        data["endpoint_obj"] = endpoint_obj
        if not data["hostname"]:
            data["hostname"] = endpoint_obj.hostname
        if not data["endpoint_path"]:
            data["endpoint_path"] = endpoint_obj.endpoint
        if not data["payload"]:
            data["payload"] = endpoint_obj.http_payload or ""
        if not data["raw_headers"]:
            stored_headers = headers_from_apiheader_list(endpoint_obj.headers)
            data["raw_headers"] = "\n".join(f"{k}: {v}" for k, v in stored_headers.items())
        data["template"] = "endpoints/view_endpoint.html"
    else:
        # Use the form values as a fallback endpoint object
        data["endpoint_obj"] = {
            "name": data["name"],
            "hostname": data["hostname"],
            "endpoint": data["endpoint_path"],
            "http_payload": data["payload"]
        }
        # Also set a default template for creation.
        data["template"] = "endpoints/create_endpoint.html"
    
    # If an endpoint_id is provided, you may use a different template:
    if data["endpoint_id"]:
        data["template"] = request.form.get("template", "endpoints/view_endpoint.html").strip()

    return data
