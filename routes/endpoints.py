from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from extensions import db
from models.model_Endpoints import Endpoint, APIHeader
from services.endpoint_services import parse_headers_from_form, parse_headers_from_list_of_dict, headers_from_apiheader_list, parse_raw_headers
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
    """
    hostname = request.form.get('hostname')
    endpoint_path = request.form.get('endpoint')
    http_payload = request.form.get('http_payload')

    # Create the Endpoint
    new_endpoint = Endpoint(
        hostname=hostname,
        endpoint=endpoint_path,
        http_payload=http_payload
    )
    db.session.add(new_endpoint)
    db.session.flush()  # flush so we get new_endpoint.id before adding headers

    # Parse headers if user provided them as lines or key-value pairs
    # E.g., "Content-Type: application/json\nAuthorization: Bearer <token>"
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
