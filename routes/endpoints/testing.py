"""
Endpoint testing operations.
This module handles testing of endpoints and retrieving test suggestions.
"""

from flask import request, jsonify
from flask_login import login_required
from models.model_Endpoints import Endpoint
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import parse_raw_headers
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
        JSON response with test results including:
        - Status code
        - Response text
        - Headers sent
        - Payload sent
    """
    try:
        if endpoint_id:
            # Test an existing endpoint
            endpoint = Endpoint.query.get_or_404(endpoint_id)
            host = endpoint.hostname
            path = endpoint.endpoint
            payload = endpoint.http_payload
            # Convert headers dictionary to raw headers string
            headers = "\n".join(f"{h.key}: {h.value}" for h in endpoint.headers)
        else:
            # Test a new endpoint configuration
            data = request.form if request.form else request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            host = data.get('hostname')
            path = data.get('endpoint')
            payload = data.get('http_payload')
            raw_headers = data.get('raw_headers', '')
            
            if not all([host, path, payload]):
                return jsonify({'error': 'Missing required fields'}), 400
                
            headers = raw_headers
        
        # Make the test request
        result = replay_post_request(host, path, payload, headers)
        
        # Return the results
        return jsonify({
            'status_code': result.get('status_code'),
            'response': result.get('response_text'),
            'headers_sent': result.get('headers_sent'),
            'payload': payload
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500 