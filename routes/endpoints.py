from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from extensions import db
from models.model_Endpoints import Endpoint, APIHeader
import requests

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

    # Grab any override from the form
    override_payload = request.form.get('test_payload', '')

    # If no override, default to the endpoint's stored payload
    actual_payload = override_payload if override_payload.strip() else endpoint.http_payload

    # Perform the POST request
    response_text = ""
    try:
        # Example using requests:
        # Construct the URL
        url = f"{endpoint.hostname.rstrip('/')}/{endpoint.endpoint.lstrip('/')}"
        # Possibly parse JSON or do something else
        # Here's a minimal approach
        resp = requests.post(url, data=actual_payload, timeout=10)
        resp.raise_for_status()
        response_text = resp.text
    except requests.exceptions.RequestException as e:
        response_text = f"Error: {str(e)}"

    # Render the same template, passing "what was sent" and "what was received"
    return render_template(
        'endpoints/view_endpoint.html',
        endpoint=endpoint,
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