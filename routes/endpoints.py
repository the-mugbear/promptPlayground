from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from extensions import db
from models.model_Endpoints import Endpoint, APIHeader
from services.endpoint_services import parse_headers_from_form, parse_headers_from_list_of_dict, headers_from_apiheader_list, parse_raw_headers
from werkzeug.exceptions import BadRequest
import requests
import json

endpoints_bp = Blueprint('endpoints_bp', __name__, url_prefix='/endpoints')

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
    return render_template('endpoints/create_endpoint.html')

@endpoints_bp.route('/create', methods=['POST'])
def handle_create_endpoint():
    """
    POST /endpoints/create -> Saves the new endpoint info and its headers in the DB
    
    Expected form data:
        - hostname: str
        - endpoint: str
        - http_payload: str (JSON format)
        - raw_headers: str (newline-separated key:value pairs)
        
    Returns:
        Redirect to endpoints list on success
        
    Raises:
        BadRequest: If payload is not valid JSON or missing required fields
    """
    try:
        hostname = request.form.get('hostname')
        endpoint_path = request.form.get('endpoint')
        raw_payload = request.form.get('http_payload', '')

        # Validate and structure the HTTP payload
        if raw_payload:
            try:
                # First parse the input to ensure it's valid JSON
                payload_dict = json.loads(raw_payload)
                
                # Ensure required fields exist
                required_fields = ['model', 'messages', 'stream']
                missing_fields = [field for field in required_fields if field not in payload_dict]
                if missing_fields:
                    raise BadRequest(f"Missing required fields in payload: {', '.join(missing_fields)}")
                
                # Validate messages structure
                if not isinstance(payload_dict['messages'], list):
                    raise BadRequest("'messages' must be a list")
                
                for msg in payload_dict['messages']:
                    if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                        raise BadRequest("Each message must have 'role' and 'content' fields")
                
                # Store as formatted JSON string
                formatted_payload = json.dumps({
                    "model": payload_dict['model'],
                    "messages": payload_dict['messages'],
                    "stream": payload_dict['stream']
                }, indent=2)
                
            except json.JSONDecodeError as e:
                raise BadRequest(f"Invalid JSON payload: {str(e)}")
        else:
            # If no payload provided, use the default template
            formatted_payload = json.dumps({
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "PLACEHOLDER"}
                ],
                "stream": False
            }, indent=2)

        # Create the Endpoint
        new_endpoint = Endpoint(
            hostname=hostname,
            endpoint=endpoint_path,
            http_payload=formatted_payload  # Store the formatted JSON string
        )
        db.session.add(new_endpoint)
        db.session.flush()

        # Parse headers
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
        return redirect(url_for('endpoints_bp.list_endpoints'))

    except BadRequest as e:
        db.session.rollback()
        flash(str(e), 'error')
        return redirect(url_for('endpoints_bp.create_endpoint'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating endpoint: {str(e)}', 'error')
        return redirect(url_for('endpoints_bp.create_endpoint'))


# Originally even if the user submitted a proper JSON formatted payload we were saving the raw string from the form
# this is intended to ensure it's proper JSON before saving to DB
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
        # else we do data=... 
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


@endpoints_bp.route('/<int:endpoint_id>', methods=['GET'])
def view_endpoint_details(endpoint_id):
    """
    GET /endpoints/<id> -> Shows the details of a single endpoint, including headers
    """
    ep = Endpoint.query.get_or_404(endpoint_id)
    return render_template('endpoints/view_endpoint.html', endpoint=ep)


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
