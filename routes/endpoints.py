from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from extensions import db
from models.model_Endpoints import Endpoint, APIHeader
from services.endpoints.api_templates import PAYLOAD_TEMPLATES
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import parse_raw_headers
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
        # Retrieve form fields
        name = request.form.get('name', '').strip()
        hostname = request.form.get('hostname', '').strip()
        endpoint_path = request.form.get('endpoint', '').strip()
        raw_payload = request.form.get('http_payload', '').strip()

        # 1) Validate minimal required fields
        if not name or not hostname or not endpoint_path:
            raise BadRequest("Missing required fields: 'name', 'hostname' or 'endpoint'.")

        # 2) Validate payload contains the injection prompt if provided
        if raw_payload:
            if '{{INJECT_PROMPT}}' not in raw_payload:
                raise BadRequest("The HTTP payload must contain '{{INJECT_PROMPT}}'.")
            formatted_payload = raw_payload
        else:
            # Minimal default payload
            formatted_payload = '''{
                "messages": [
                    {"role": "user", "content": "{{INJECT_PROMPT}}"}
                ]
            }'''

        # 3) Create new Endpoint record
        new_endpoint = Endpoint(
            name=name,
            hostname=hostname,
            endpoint=endpoint_path,
            http_payload=formatted_payload
        )
        db.session.add(new_endpoint)
        db.session.flush()  # Ensure new_endpoint.id is assigned

        # 4) Process headers using the centralized header parser
        raw_headers = request.form.get('raw_headers', '')
        parsed_headers = parse_raw_headers(raw_headers)
        for key, value in parsed_headers.items():
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

@endpoints_bp.route('/test_temporary', methods=['POST'])
def test_temporary_endpoint():
    """
    POST /endpoints/test_temporary -> Executes a one-off test of an endpoint using provided form data.
    """
    hostname = request.form.get("hostname", "").strip()
    endpoint_path = request.form.get("endpoint", "").strip()
    actual_payload = request.form.get("http_payload", "").strip()

    if "{{INJECT_PROMPT}}" in actual_payload:
        actual_payload = actual_payload.replace("{{INJECT_PROMPT}}", "What is 4 + 3?")

    raw_headers = request.form.get("raw_headers", "").strip()
    result = replay_post_request(hostname, endpoint_path, actual_payload, raw_headers)

    return render_template(
        'endpoints/create_endpoint.html',
        test_payload=actual_payload,
        test_response=result.get("response_text"),
        test_status_code=result.get("status_code"),
        test_headers_sent=result.get("headers_sent")
    )

@endpoints_bp.route('/<int:endpoint_id>/update', methods=['POST'])
def update_endpoint(endpoint_id):
    """
    POST /endpoints/<id>/update -> Updates the specified endpoint using form data.
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    name = request.form.get('name', '').strip()
    hostname = request.form.get('hostname', '').strip()
    endpoint_path = request.form.get('endpoint', '').strip()
    http_payload = request.form.get('http_payload', '').strip()
    raw_headers = request.form.get('raw_headers', '').strip()

    if not hostname or not endpoint_path:
        flash("Hostname and Path are required.", "error")
        return redirect(url_for('endpoints_bp.view_endpoint_details', endpoint_id=endpoint_id))

    endpoint_obj.name = name
    endpoint_obj.hostname = hostname
    endpoint_obj.endpoint = endpoint_path
    endpoint_obj.http_payload = http_payload

    # Remove existing headers
    for header in endpoint_obj.headers:
        db.session.delete(header)
    endpoint_obj.headers = []

    # Process new headers using centralized header parser
    if raw_headers:
        parsed_headers = parse_raw_headers(raw_headers)
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

@endpoints_bp.route('/<int:endpoint_id>/test', methods=['POST'])
def test_endpoint(endpoint_id):
    """
    POST /endpoints/<id>/test -> Tests the specified endpoint with provided or stored data.
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    hostname = request.form.get("hostname", "").strip() or endpoint_obj.hostname
    endpoint_path = request.form.get("endpoint", "").strip() or endpoint_obj.endpoint
    http_payload = request.form.get("test_payload", "").strip() or endpoint_obj.http_payload or ""

    if "{{INJECT_PROMPT}}" in http_payload:
        http_payload = http_payload.replace("{{INJECT_PROMPT}}", "What is 4 + 3?")

    raw_headers = request.form.get("raw_headers", "").strip()
    result = replay_post_request(hostname, endpoint_path, http_payload, raw_headers)

    return render_template(
        'endpoints/view_endpoint.html',
        endpoint=endpoint_obj,
        test_payload=http_payload,
        test_response=result.get("response_text")
    )

@endpoints_bp.route('/<int:endpoint_id>/json', methods=['GET'])
def get_endpoint_json(endpoint_id):
    """
    GET /endpoints/<id>/json -> Returns the JSON representation of the endpoint.
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    return jsonify(endpoint_obj.to_dict())
