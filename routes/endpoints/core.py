"""
Core operations for managing API endpoints.
This module handles basic CRUD operations for endpoints including listing, viewing, creating, and deleting.
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from sqlalchemy.orm import joinedload
from models.model_Endpoints import Endpoint, APIHeader
from services.endpoints.api_templates import PAYLOAD_TEMPLATES
from services.common.header_parser_service import parse_raw_headers
from . import endpoints_bp

@endpoints_bp.route('/', methods=['GET'])
def list_endpoints():
    """
    Display a list of all endpoints.
    
    Returns:
        Rendered template with list of endpoints
    """
    endpoints = Endpoint.query.all()
    return render_template('endpoints/list_endpoints.html', endpoints=endpoints)

@endpoints_bp.route('/create', methods=['GET'])
@login_required
def create_endpoint_form():
    """
    Display form to create a new endpoint.
    
    Returns:
        Rendered template with endpoint creation form
    """
    return render_template('endpoints/create_endpoint.html', payload_templates=PAYLOAD_TEMPLATES)

@endpoints_bp.route('/<int:endpoint_id>', methods=['GET'])
@login_required
def view_endpoint_details(endpoint_id):
    """
    View details of a specific endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint to view
        
    Returns:
        Rendered template with endpoint details
    """
    ep = Endpoint.query.options(joinedload(Endpoint.headers)).get_or_404(endpoint_id)
    return render_template('endpoints/view_endpoint.html', endpoint=ep)

@endpoints_bp.route('/create', methods=['POST'])
@login_required
def handle_create_endpoint():
    """
    Handle the creation of a new endpoint.
    
    Creates a new endpoint with:
    - Basic endpoint information (name, hostname, path)
    - HTTP payload
    - Associated headers
    
    Returns:
        Redirect to the new endpoint's view page on success,
        or back to the creation form with error message on failure
    """
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
        
        # Add and commit the endpoint first to get its ID
        db.session.add(endpoint)
        db.session.commit()
        
        # Now process headers if provided
        if form_data["raw_headers"]:
            parsed_headers = parse_raw_headers(form_data["raw_headers"])
            for key, value in parsed_headers.items():
                header = APIHeader(endpoint_id=endpoint.id, key=key, value=value)
                db.session.add(header)
            db.session.commit()
        
        flash("Endpoint created successfully", "success")
        return redirect(url_for("endpoints_bp.view_endpoint_details", endpoint_id=endpoint.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating endpoint: {str(e)}", "error")
        return redirect(url_for("endpoints_bp.create_endpoint_form"))

@endpoints_bp.route('/<int:endpoint_id>/delete', methods=['POST'])
@login_required
def delete_endpoint(endpoint_id):
    """
    Delete an endpoint and all its associated data.
    
    Args:
        endpoint_id: The ID of the endpoint to delete
        
    Returns:
        Redirect to endpoints list with success/error message
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    db.session.delete(endpoint_obj)
    db.session.commit()
    flash(f'Endpoint {endpoint_id} deleted successfully.', 'success')
    return redirect(url_for('endpoints_bp.list_endpoints'))

@endpoints_bp.route('/<int:endpoint_id>/update', methods=['POST'])
@login_required
def update_endpoint(endpoint_id):
    """
    Update an existing endpoint's configuration.
    
    Args:
        endpoint_id: The ID of the endpoint to update
        
    Returns:
        Redirect to endpoint view with success/error message
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    data = get_endpoint_form_data()
    
    # Update fields with data from the form
    endpoint_obj.name = data["name"]
    endpoint_obj.hostname = data["hostname"]
    endpoint_obj.endpoint = data["endpoint_path"]
    endpoint_obj.http_payload = data["payload"]

    # Remove existing headers
    for header in endpoint_obj.headers:
        db.session.delete(header)
    endpoint_obj.headers = []

    # Add new headers if provided
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
    Get the JSON representation of an endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint to get
        
    Returns:
        JSON representation of the endpoint
    """
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    return jsonify(endpoint_obj.to_dict())

def get_endpoint_form_data(default_payload=None):
    """
    Extract and validate form data for endpoint creation/update.
    
    Args:
        default_payload: Optional default payload to use if none provided in form
        
    Returns:
        Dictionary containing validated form data
    """
    return {
        "name": request.form.get('name', '').strip(),
        "hostname": request.form.get('hostname', '').strip(),
        "endpoint_path": request.form.get('endpoint_path', '').strip(),
        "payload": request.form.get('http_payload', default_payload or '').strip(),
        "raw_headers": request.form.get('raw_headers', '').strip()
    } 