# app/endpoints/api.py
from flask import request, jsonify
from flask_login import login_required

from extensions import db
from models.model_Endpoints import Endpoint, APIHeader

from . import endpoints_bp

@endpoints_bp.route('/<int:endpoint_id>/json', methods=['GET'])
@login_required
def get_endpoint_json(endpoint_id):
    endpoint_obj = Endpoint.query.get_or_404(endpoint_id)
    return jsonify(endpoint_obj.to_dict()) # Assuming your model has a to_dict() method

@endpoints_bp.route('/<int:endpoint_id>/update_field', methods=['PUT'])
@login_required
def update_endpoint_field(endpoint_id):
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    data = request.get_json(force=True) # force=True if content-type might not be application/json
    
    field_name = list(data.keys())[0]
    value = data[field_name]
    
    field_mapping = {
        'name': 'name',
        'hostname': 'hostname',
        'path': 'endpoint',
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
    existing_header = APIHeader.query.filter_by(endpoint_id=endpoint_id, key=key).first()
    if existing_header:
        return jsonify({"error": f"Header with key '{key}' already exists. Use update instead."}), 409 # Conflict

    try:
        new_header = APIHeader(endpoint_id=endpoint_id, key=key, value=value)
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
    header = APIHeader.query.filter_by(id=header_id, endpoint_id=endpoint_id).first_or_404()
    data = request.get_json(force=True)

    new_key = data.get('key', header.key).strip()
    new_value = data.get('value', header.value) # Keep old value if not provided

    if not new_key:
        return jsonify({"error": "Header key cannot be empty"}), 400

    # If key is changing, check for conflicts with other headers of the same endpoint
    if new_key != header.key:
        existing_with_new_key = APIHeader.query.filter(
            APIHeader.endpoint_id == endpoint_id,
            APIHeader.key == new_key,
            APIHeader.id != header_id # Exclude the current header itself
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
    header = APIHeader.query.filter_by(id=header_id, endpoint_id=endpoint_id).first_or_404()
    try:
        db.session.delete(header)
        db.session.commit()
        return jsonify({"message": "Header deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500