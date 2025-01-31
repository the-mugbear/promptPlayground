from flask import Blueprint, request, render_template, redirect, url_for, flash
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

@endpoints_bp.route('/<int:endpoint_id>/test', methods=['GET', 'POST'])
def test_endpoint(endpoint_id):
    """
    GET  /endpoints/<id>/test -> Shows a page to confirm or provide new payload
    POST /endpoints/<id>/test -> Submits a POST request to the stored hostname + endpoint
    """
    ep = Endpoint.query.get_or_404(endpoint_id)

    if request.method == 'GET':
        return render_template('endpoints/test_endpoint.html', endpoint=ep)
    
    # POST request
    # Optionally, user might override the default payload in a <textarea> or input
    test_payload = request.form.get('test_payload', ep.http_payload)
    # Build the full URL
    url = f"{ep.hostname.rstrip('/')}/{ep.endpoint.lstrip('/')}"
    
    # Gather headers from DB
    headers = {}
    for h in ep.headers:
        headers[h.key] = h.value

    try:
        response = requests.post(url, data=test_payload, headers=headers, timeout=10)
        response.raise_for_status()
        result_text = response.text  # or response.json() if JSON
        flash(f"Success! Response: {result_text}", 'success')
    except requests.exceptions.HTTPError as e:
        flash(f"HTTP Error: {str(e)}", 'error')
    except requests.exceptions.RequestException as e:
        flash(f"Request Exception: {str(e)}", 'error')

    return redirect(url_for('endpoints_bp.list_endpoints'))

@endpoints_bp.route('/<int:endpoint_id>', methods=['GET'])
def view_endpoint_details(endpoint_id):
    """
    GET /endpoints/<id> -> Shows the details of a single endpoint, including headers
    """
    ep = Endpoint.query.get_or_404(endpoint_id)
    return render_template('endpoints/view_endpoint.html', endpoint=ep)
