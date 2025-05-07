from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.model_Endpoints import Endpoint, APIHeader
from models.model_ManualTestRecord import ManualTestRecord
from services.endpoints.api_templates import PAYLOAD_TEMPLATES
from services.transformers.registry import apply_transformations_to_lines, TRANSFORM_PARAM_CONFIG, apply_transformation
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import parse_raw_headers, headers_from_apiheader_list
from werkzeug.exceptions import BadRequest
from sqlalchemy.orm import joinedload
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
@login_required
def create_endpoint_form():
    """
    GET /endpoints/create -> Renders a form to create a new endpoint & headers
    """
    return render_template('endpoints/create_endpoint.html', payload_templates=PAYLOAD_TEMPLATES)

@endpoints_bp.route('/<int:endpoint_id>', methods=['GET'])
@login_required
def view_endpoint_details(endpoint_id):
    """
    GET /endpoints/<id> -> Shows the details of a single endpoint, including headers
    """
    ep = Endpoint.query.options(joinedload(Endpoint.headers)).get_or_404(endpoint_id)
    return render_template('endpoints/view_endpoint.html', endpoint=ep)

@endpoints_bp.route('/manual_test', methods=['GET', 'POST'])
def manual_test():
    # 1) On GET, show the form + load history:
    if request.method == 'GET':
        history = ManualTestRecord.query.order_by(ManualTestRecord.created_at.desc()).all()
        return render_template('endpoints/manual_test.html',
                               payload_templates=PAYLOAD_TEMPLATES,
                               transform_params=TRANSFORM_PARAM_CONFIG,
                               history=history)

    # 2) On POST, extract form data:
    host     = request.form['hostname'].strip()
    path     = request.form['endpoint_path'].strip()
    raw_hdrs = request.form.get('raw_headers', '').strip()
    tpl      = request.form['http_payload'].strip()
    # the user‑entered replacement value:
    repl     = request.form['replacement_value'].strip()

    # parse headers
    hdrs_dict = parse_raw_headers(raw_hdrs) if raw_hdrs else {}
    assembled_hdrs = "\n".join(f"{k}: {v}" for k,v in hdrs_dict.items())

    # collect requested transformations
    transforms = []
    for t_id in request.form.getlist('transforms'):
        params = {}
        if val := request.form.get(f"{t_id}_value"):
            params['value'] = val
        transforms.append({'type': t_id, **params})

    # apply them in order
    for tinfo in transforms:
        repl = apply_transformation(tinfo['type'], repl, {'value': tinfo.get('value')})

    # build the final payload
    payload = tpl.replace("{{INJECT_PROMPT}}", repl)

    # fire off the POST
    result = replay_post_request(host, path, payload, assembled_hdrs)

    # record it
    rec = ManualTestRecord(
        hostname=host,
        endpoint=path,
        raw_headers=assembled_hdrs,
        payload_sent=payload,
        response_data=result.get("response_text"),
    )
    db.session.add(rec)
    db.session.commit()

    # If this was an AJAX submission, return JSON instead of redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True,
            "record": {
                "id": rec.id,
                "created_at": rec.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "payload_sent": rec.payload_sent,
                "response_data": rec.response_data
            }
        })
    else:
        return redirect(url_for('endpoints_bp.manual_test'))
    
# ********************************
# SERVICES
# ********************************
@endpoints_bp.route('/create', methods=['POST'])
@login_required
def handle_create_endpoint():
    """Handle the creation of a new endpoint."""
    try:
        # Get form data
        form_data = get_endpoint_form_data()
        
        # Validate required fields
        if not form_data["name"] or not form_data["hostname"] or not form_data["endpoint_path"]:
            flash("Name, hostname, and endpoint path are required", "error")
            return redirect(url_for("endpoints_bp.create_endpoint_form"))
        
        # Validate that the payload contains the injection prompt token
        if "{{INJECT_PROMPT}}" not in form_data["payload"]:
            flash("HTTP Payload must contain the {{INJECT_PROMPT}} token", "error")
            return redirect(url_for("endpoints_bp.create_endpoint_form"))
            
        # Validate that the token is not directly quoted (but can be part of a JSON string)
        if '"{{INJECT_PROMPT}}"' in form_data["payload"] and not any(
            pattern in form_data["payload"] 
            for pattern in [
                '"content": "{{INJECT_PROMPT}}"',
                '"prompt": "{{INJECT_PROMPT}}"',
                '"input": "{{INJECT_PROMPT}}"',
                '"text": "{{INJECT_PROMPT}}"'
            ]
        ):
            flash("The {{INJECT_PROMPT}} token should be part of a JSON string value (e.g., in a 'content' or 'prompt' field)", "error")
            return redirect(url_for("endpoints_bp.create_endpoint_form"))
        
        # Create new endpoint
        endpoint = Endpoint(
            name=form_data["name"],
            hostname=form_data["hostname"],
            endpoint=form_data["endpoint_path"],
            http_payload=form_data["payload"]
        )
        
        # Process headers if provided
        if form_data["raw_headers"]:
            parsed_headers = parse_raw_headers(form_data["raw_headers"])
            for key, value in parsed_headers.items():
                header = APIHeader(endpoint_id=endpoint.id, key=key, value=value)
                db.session.add(header)
        
        db.session.add(endpoint)
        db.session.commit()
        
        flash("Endpoint created successfully", "success")
        return redirect(url_for("endpoints_bp.view_endpoint_details", endpoint_id=endpoint.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating endpoint: {str(e)}", "error")
        return redirect(url_for("endpoints_bp.create_endpoint_form"))


@endpoints_bp.route('/get_suggestions', methods=['GET'])
@login_required
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
@login_required
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
@login_required
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
@login_required
def get_endpoint_json(endpoint_id):
    """
    GET /endpoints/<id>/json -> Returns the JSON representation of the endpoint.
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    return jsonify(endpoint_obj.to_dict())

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

@endpoints_bp.route('/<int:endpoint_id>/update_field', methods=['PUT'])
@login_required
def update_endpoint_field(endpoint_id):
    """
    PUT /endpoints/<id>/update_field -> Updates a single field of an endpoint via AJAX
    """
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    data = request.get_json(force=True)
    
    # Get the field name and value from the request
    field_name = list(data.keys())[0]  # Get the first (and only) key
    value = data[field_name]
    
    # Map the field name to the actual model attribute
    field_mapping = {
        'name': 'name',
        'hostname': 'hostname',
        'path': 'endpoint',  # Note: 'path' in frontend maps to 'endpoint' in model
        'timestamp': 'timestamp',
        'http_payload': 'http_payload'
    }
    
    if field_name not in field_mapping:
        return jsonify({"error": f"Invalid field: {field_name}"}), 400
        
    try:
        setattr(endpoint, field_mapping[field_name], value)
        db.session.commit()
        return jsonify({"message": f"Updated {field_name}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

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
