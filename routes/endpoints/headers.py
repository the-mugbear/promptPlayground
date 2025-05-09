"""
Header management operations for endpoints.
This module handles operations related to API headers including updating and deleting headers.
"""

from flask import request, jsonify
from flask_login import login_required
from extensions import db
from models.model_Endpoints import Endpoint, APIHeader
from . import endpoints_bp

@endpoints_bp.route('/<int:endpoint_id>/update_header', methods=['PUT'])
@login_required
def update_header(endpoint_id):
    """
    Update an existing header for an endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint whose header to update
        
    Returns:
        JSON response with success/error message
    """
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    data = request.get_json()
    
    if not data or 'header_id' not in data or 'key' not in data or 'value' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
        
    header = APIHeader.query.get(data['header_id'])
    if not header or header.endpoint_id != endpoint_id:
        return jsonify({'error': 'Header not found'}), 404
        
    try:
        header.key = data['key']
        header.value = data['value']
        db.session.commit()
        return jsonify({
            'message': 'Header updated successfully',
            'header': {
                'id': header.id,
                'key': header.key,
                'value': header.value
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@endpoints_bp.route('/<int:endpoint_id>/delete_header', methods=['DELETE'])
@login_required
def delete_header(endpoint_id):
    """
    Delete a header from an endpoint.
    
    Args:
        endpoint_id: The ID of the endpoint whose header to delete
        
    Returns:
        JSON response with success/error message
    """
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    data = request.get_json()
    
    if not data or 'header_id' not in data:
        return jsonify({'error': 'Missing header_id'}), 400
        
    header = APIHeader.query.get(data['header_id'])
    if not header or header.endpoint_id != endpoint_id:
        return jsonify({'error': 'Header not found'}), 404
        
    try:
        db.session.delete(header)
        db.session.commit()
        return jsonify({'message': 'Header deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500 