# app/endpoints/api.py
import logging
import json
from flask import request, jsonify
from flask_login import login_required

from extensions import db
from models.model_Endpoints import Endpoint, EndpointHeader

from . import endpoints_bp

logger = logging.getLogger(__name__)
logger.debug("Orchestrator: entering orchestrate()")

@endpoints_bp.route('/<int:endpoint_id>/json', methods=['GET'])
@login_required
def get_endpoint_json(endpoint_id):
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    return jsonify(endpoint_obj.to_dict()) # Assuming your model has a to_dict() method

@endpoints_bp.route('/<int:endpoint_id>/update_field', methods=['PUT'])
@login_required
def update_endpoint_field(endpoint_id):
    """
    Update a single field of an endpoint.
    """
    # Add 'method' to this list of allowed fields.
    allowed_fields = ['name', 'base_url', 'path', 'method']
    
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    data = request.get_json()
    
    if not data or len(data) != 1:
        return jsonify({'error': 'Invalid request format. Expecting a single key-value pair.'}), 400

    field_name = next(iter(data)) # Get the first (and only) key from the dict
    
    if field_name not in allowed_fields:
        # This is where your error message is coming from
        return jsonify({'error': f'Invalid field: {field_name}'}), 400

    new_value = data[field_name]

    # Use setattr to dynamically set the attribute on the endpoint object
    # e.g., setattr(endpoint, 'name', 'New Name') is like endpoint.name = 'New Name'
    setattr(endpoint, field_name, new_value)
    
    try:
        db.session.commit()
        return jsonify({'message': f'Endpoint field "{field_name}" updated successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating endpoint field: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update endpoint due to a database error.'}), 500

@endpoints_bp.route('/<int:endpoint_id>/headers', methods=['POST'])
@login_required
def add_endpoint_header(endpoint_id):
    """Adds a new header to an endpoint (called via AJAX)."""
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    data = request.get_json(force=True)
    
    key = data.get('key')
    value = data.get('value')
    
    if not key: # Value can be empty
        return jsonify({"error": "Header key is required"}), 400
        
    # Check if header with this key already exists for this endpoint
    existing_header = EndpointHeader.query.filter_by(endpoint_id=endpoint_id, key=key).first()
    if existing_header:
        return jsonify({"error": f"Header with key '{key}' already exists. Use update instead."}), 409 # Conflict

    try:
        new_header = EndpointHeader(endpoint_id=endpoint_id, key=key, value=value)
        db.session.add(new_header)
        db.session.commit()
        return jsonify({
            "message": "Header added successfully",
            "header": {"id": new_header.id, "key": new_header.key, "value": new_header.value}
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@endpoints_bp.route('/<int:endpoint_id>/headers/<int:header_id>', methods=['PUT'])
@login_required
def update_endpoint_header(endpoint_id, header_id):
    """Updates an existing header for an endpoint (called via AJAX)."""
    # Ensure header belongs to endpoint is implicit via query.
    header = EndpointHeader.query.filter_by(id=header_id, endpoint_id=endpoint_id).first_or_404()
    data = request.get_json(force=True)

    new_key = data.get('key', header.key).strip()
    new_value = data.get('value', header.value) # Keep old value if not provided

    if not new_key:
        return jsonify({"error": "Header key cannot be empty"}), 400

    # If key is changing, check for conflicts with other headers of the same endpoint
    if new_key != header.key:
        existing_with_new_key = EndpointHeader.query.filter(
            EndpointHeader.endpoint_id == endpoint_id,
            EndpointHeader.key == new_key,
            EndpointHeader.id != header_id # Exclude the current header itself
        ).first()
        if existing_with_new_key:
            return jsonify({"error": f"Another header with key '{new_key}' already exists."}), 409

    try:
        header.key = new_key
        header.value = new_value
        db.session.commit()
        return jsonify({
            "message": "Header updated successfully",
            "header": {"id": header.id, "key": header.key, "value": header.value}
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@endpoints_bp.route('/<int:endpoint_id>/headers/<int:header_id>', methods=['DELETE'])
@login_required
def delete_endpoint_header(endpoint_id, header_id):
    """Deletes a specific header from an endpoint (called via AJAX)."""
    header = EndpointHeader.query.filter_by(id=header_id, endpoint_id=endpoint_id).first_or_404()
    try:
        db.session.delete(header)
        db.session.commit()
        return jsonify({"message": "Header deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@endpoints_bp.route('/<int:endpoint_id>/details', methods=['GET'])
@login_required
def get_endpoint_details(endpoint_id):
    """
    Returns the default headers and payload for a specific endpoint.
    """
    endpoint = db.session.get(Endpoint, endpoint_id)
    if not endpoint:
        return jsonify({'error': 'Endpoint not found'}), 404

    # Convert the list of header objects into a dictionary
    headers_dict = {h.key: h.value for h in endpoint.headers}
    
    # Return the details in a JSON response
    return jsonify({
        # Format the headers as a nicely indented JSON string for the textarea
        'headers': json.dumps(headers_dict, indent=2) if headers_dict else '{}',
        # Provide the default payload template, or an empty JSON object string
        'payload': endpoint.payload_template.template if endpoint.payload_template else '{}'
    })