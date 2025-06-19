#!/usr/bin/env python3
"""
Debug script for chain execution issues.
This script helps diagnose problems with API chains, especially header templating and data extraction.
"""

import logging
import json
from services.common.templating_service import render_template_string

# Setup detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_header_templating():
    """Test header templating with sessionID replacement"""
    print("=" * 60)
    print("TESTING HEADER TEMPLATING")
    print("=" * 60)
    
    # Example chain context with sessionID extracted from first step
    chain_context = {
        'sessionID': 'abc123-session-token-xyz789'
    }
    
    # Example headers template that uses sessionID twice
    headers_template = '''{
        "Authorization": "Bearer {{ sessionID }}",
        "X-Session-Token": "{{ sessionID }}",
        "Content-Type": "application/json",
        "User-Agent": "FuzzyPrompts-Chain/1.0"
    }'''
    
    print(f"Headers template:\n{headers_template}")
    print(f"Chain context: {chain_context}")
    
    try:
        rendered_headers_str = render_template_string(headers_template, chain_context)
        print(f"Rendered headers string:\n{rendered_headers_str}")
        
        # Try to parse as JSON
        rendered_headers = json.loads(rendered_headers_str)
        print(f"Parsed headers dict:\n{json.dumps(rendered_headers, indent=2)}")
        
        return rendered_headers
        
    except Exception as e:
        print(f"ERROR in header templating: {e}")
        return None

def test_payload_templating():
    """Test payload templating"""
    print("\n" + "=" * 60)
    print("TESTING PAYLOAD TEMPLATING")
    print("=" * 60)
    
    chain_context = {
        'sessionID': 'abc123-session-token-xyz789',
        'userId': '12345'
    }
    
    payload_template = '''{
        "session": "{{ sessionID }}",
        "user_id": "{{ userId }}",
        "action": "get_data"
    }'''
    
    print(f"Payload template:\n{payload_template}")
    print(f"Chain context: {chain_context}")
    
    try:
        rendered_payload_str = render_template_string(payload_template, chain_context)
        print(f"Rendered payload string:\n{rendered_payload_str}")
        
        # Try to parse as JSON
        rendered_payload = json.loads(rendered_payload_str)
        print(f"Parsed payload dict:\n{json.dumps(rendered_payload, indent=2)}")
        
        return rendered_payload
        
    except Exception as e:
        print(f"ERROR in payload templating: {e}")
        return None

def test_data_extraction():
    """Test data extraction scenarios"""
    print("\n" + "=" * 60)
    print("TESTING DATA EXTRACTION")
    print("=" * 60)
    
    # Simulate API response from first step
    mock_response_data = {
        "status_code": 200,
        "response_headers": {
            "Content-Type": "application/json",
            "Set-Cookie": "session=abc123-session-token-xyz789; Path=/; HttpOnly"
        },
        "response_body": '{"sessionToken": "abc123-session-token-xyz789", "userId": 12345, "status": "authenticated"}',
        "error_message": None
    }
    
    # Test different extraction rules
    extraction_rules = [
        {
            "variable_name": "sessionID",
            "source_type": "json_body",
            "source_identifier": "sessionToken"
        },
        {
            "variable_name": "sessionID_from_header", 
            "source_type": "header",
            "source_identifier": "Set-Cookie"
        },
        {
            "variable_name": "userId",
            "source_type": "json_body", 
            "source_identifier": "userId"
        }
    ]
    
    print(f"Mock response data:\n{json.dumps(mock_response_data, indent=2)}")
    
    chain_context = {}
    
    for rule in extraction_rules:
        print(f"\nTesting extraction rule: {rule}")
        try:
            from services.common.data_extraction_service import extract_data_from_response
            extracted_value = extract_data_from_response(mock_response_data, rule)
            variable_name = rule["variable_name"]
            chain_context[variable_name] = extracted_value
            print(f"Extracted {variable_name} = {extracted_value}")
            
        except Exception as e:
            print(f"ERROR extracting {rule['variable_name']}: {e}")
    
    print(f"\nFinal chain context: {chain_context}")
    return chain_context

def test_complete_chain_scenario():
    """Test a complete 2-step chain scenario"""
    print("\n" + "=" * 80)
    print("TESTING COMPLETE CHAIN SCENARIO")
    print("=" * 80)
    
    # Step 1: Login/Authentication (GET request)
    print("STEP 1: Authentication GET request")
    step1_context = {}
    
    # Simulate step 1 response
    step1_response = {
        "status_code": 200,
        "response_headers": {"Content-Type": "application/json"},
        "response_body": '{"sessionToken": "abc123-session-token-xyz789", "expiresIn": 3600}',
        "error_message": None
    }
    
    # Extract sessionID from step 1
    extraction_rule = {
        "variable_name": "sessionID",
        "source_type": "json_body",
        "source_identifier": "sessionToken"
    }
    
    try:
        from services.common.data_extraction_service import extract_data_from_response
        session_id = extract_data_from_response(step1_response, extraction_rule)
        step1_context["sessionID"] = session_id
        print(f"Step 1 - Extracted sessionID: {session_id}")
    except Exception as e:
        print(f"Step 1 - ERROR extracting sessionID: {e}")
        return
    
    # Step 2: Use sessionID in headers (twice)
    print("\nSTEP 2: Using sessionID in headers")
    
    step2_headers_template = '''{
        "Authorization": "Bearer {{ sessionID }}",
        "X-Session-Token": "{{ sessionID }}",
        "Content-Type": "application/json"
    }'''
    
    try:
        rendered_headers_str = render_template_string(step2_headers_template, step1_context)
        rendered_headers = json.loads(rendered_headers_str)
        print(f"Step 2 - Rendered headers: {json.dumps(rendered_headers, indent=2)}")
        
        # Check if both sessionID replacements worked
        auth_header = rendered_headers.get("Authorization", "")
        session_header = rendered_headers.get("X-Session-Token", "")
        
        if session_id in auth_header and session_id in session_header:
            print("✅ SUCCESS: sessionID correctly replaced in both headers")
        else:
            print("❌ FAILURE: sessionID not properly replaced")
            print(f"   Authorization header: {auth_header}")
            print(f"   X-Session-Token header: {session_header}")
            print(f"   Expected sessionID: {session_id}")
            
    except Exception as e:
        print(f"Step 2 - ERROR in header templating: {e}")

def test_problematic_scenarios():
    """Test scenarios that commonly cause 400 errors"""
    print("\n" + "=" * 80) 
    print("TESTING PROBLEMATIC SCENARIOS")
    print("=" * 80)
    
    scenarios = [
        {
            "name": "Empty sessionID",
            "context": {"sessionID": ""},
            "template": '{"auth": "{{ sessionID }}"}'
        },
        {
            "name": "None sessionID", 
            "context": {"sessionID": None},
            "template": '{"auth": "{{ sessionID }}"}'
        },
        {
            "name": "Missing sessionID variable",
            "context": {},
            "template": '{"auth": "{{ sessionID }}"}'
        },
        {
            "name": "Special characters in sessionID",
            "context": {"sessionID": "token-with-special-chars!@#$%^&*()"},
            "template": '{"auth": "{{ sessionID }}"}'
        },
        {
            "name": "JSON injection attempt",
            "context": {"sessionID": '"; "injected": "value'},
            "template": '{"auth": "{{ sessionID }}"}'
        }
    ]
    
    for scenario in scenarios:
        print(f"\nTesting: {scenario['name']}")
        print(f"Context: {scenario['context']}")
        print(f"Template: {scenario['template']}")
        
        try:
            rendered = render_template_string(scenario['template'], scenario['context'])
            print(f"Rendered: {rendered}")
            
            # Try to parse as JSON
            json.loads(rendered)
            print("✅ Valid JSON produced")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_header_templating()
    test_payload_templating()
    test_data_extraction()
    test_complete_chain_scenario()
    test_problematic_scenarios()
    
    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)