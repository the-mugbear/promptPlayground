"""
Endpoint testing operations.
This module handles testing of endpoints and retrieving test suggestions.
"""

from flask import request, jsonify
from flask_login import login_required
from models.model_Endpoints import Endpoint
from . import endpoints_bp

@endpoints_bp.route('/get_suggestions', methods=['GET'])
@login_required
def get_endpoint_suggestions():
    """
    Get suggestions for endpoint configurations based on existing endpoints.
    
    Returns:
        JSON response containing lists of:
        - Distinct hostnames
        - Distinct paths
        - Distinct payloads
    """
    hostnames = [row.hostname for row in Endpoint.query.with_entities(Endpoint.hostname).distinct().all() if row.hostname]
    paths = [row.endpoint for row in Endpoint.query.with_entities(Endpoint.endpoint).distinct().all() if row.endpoint]
    payloads = [row.http_payload for row in Endpoint.query.with_entities(Endpoint.http_payload).distinct().all() if row.http_payload]

    return jsonify({
        "hostnames": hostnames,
        "paths": paths,
        "payloads": payloads
    })

@endpoints_bp.route('/test', methods=['POST'])
@endpoints_bp.route('/<int:endpoint_id>/test', methods=['POST'])
@login_required
def test_endpoint(endpoint_id=None):
    """
    Test an endpoint with its current configuration.
    
    Can be used to test either:
    - An existing endpoint (with ID)
    - A new endpoint configuration (without ID)
    
    Args:
        endpoint_id: Optional ID of an existing endpoint to test
        
    Returns:
        JSON response with test results
    """
    if endpoint_id:
        # Test an existing endpoint
        endpoint = Endpoint.query.get_or_404(endpoint_id)
        host = endpoint.hostname
        path = endpoint.endpoint
        payload = endpoint.http_payload
        headers = {h.key: h.value for h in endpoint.headers}
    else:
        # Test a new endpoint configuration
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        host = data.get('hostname')
        path = data.get('endpoint')
        payload = data.get('http_payload')
        headers = data.get('headers', {})
        
        if not all([host, path, payload]):
            return jsonify({'error': 'Missing required fields'}), 400
    
    # TODO: Implement actual endpoint testing logic
    # This would typically involve:
    # 1. Validating the endpoint configuration
    # 2. Making a test request
    # 3. Analyzing the response
    # 4. Returning the results
    
    return jsonify({
        'message': 'Endpoint testing not yet implemented',
        'endpoint': {
            'host': host,
            'path': path,
            'has_payload': bool(payload),
            'header_count': len(headers)
        }
    }) 