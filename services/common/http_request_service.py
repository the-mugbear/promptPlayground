import json
import requests
import traceback
import logging
import socket
from services.common.header_parser_service import parse_raw_headers_with_cookies

# Moved the POST request functionality to a service file as it's common across endpoint creation/testing and test_run execution
def replay_post_request(hostname, endpoint_path, http_payload, raw_headers, timeout=120, verify=True):
    """
    Replay a POST request using provided hostname, endpoint, payload, and raw headers.
    Parses any "Cookie" header into a cookies dict.
    Returns a dict with status_code, response_text, and headers_sent.
    """
    # Parse headers and set default Content-Type if missing
    final_headers, cookies = parse_raw_headers_with_cookies(raw_headers)
    final_headers.setdefault("Content-Type", "application/json")

    # Handle container networking - replace localhost/127.0.0.1 with host.containers.internal
    # Didn't work but left in case it ever does
    if hostname.startswith('http://127.0.0.1') or hostname.startswith('http://localhost'):
        hostname = hostname.replace('127.0.0.1', 'host.containers.internal').replace('localhost', 'host.containers.internal')
        print(f"Container networking: Updated hostname to {hostname}")

    # Build the URL
    url = f"{hostname.rstrip('/')}/{endpoint_path.lstrip('/')}"
    print("\n=== Request Details ===")
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(final_headers, indent=2)}")
    print(f"Raw Payload: {http_payload}")
    
    # Try to resolve the hostname
    try:
        host = hostname.split('://')[1].split(':')[0]
        port = int(hostname.split(':')[-1].split('/')[0])
        print(f"\nAttempting to resolve {host}:{port}")
        try:
            ip = socket.gethostbyname(host)
            print(f"Hostname resolved to IP: {ip}")
        except socket.gaierror as e:
            print(f"Failed to resolve hostname: {e}")
    except Exception as e:
        print(f"Error parsing hostname/port: {e}")
    
    print("=====================\n")

    try:
        # First try to parse as JSON to validate format
        try:
            parsed_json = json.loads(http_payload)
            print("Successfully parsed JSON payload")
            print(f"Parsed JSON: {json.dumps(parsed_json, indent=2)}")
            
            # Make the request with JSON payload
            print("\nSending POST request with JSON payload...")
            resp = requests.post(
                url,
                json=parsed_json,
                headers=final_headers,
                cookies=cookies,
                timeout=timeout,
                verify=verify
            )
        except json.JSONDecodeError as e:
            print(f"\nFailed to parse JSON: {str(e)}")
            print("Raw payload:")
            print(http_payload)
            print("\nFalling back to raw text...")
            
            # Make the request with raw text
            resp = requests.post(
                url,
                data=http_payload,
                headers=final_headers,
                cookies=cookies,
                timeout=timeout,
                verify=verify
            )

        print(f"\n=== Response Details ===")
        print(f"Status Code: {resp.status_code}")
        print(f"Response Headers: {json.dumps(dict(resp.headers), indent=2)}")
        print(f"Response Text: {resp.text[:200]}...")
        print("=====================\n")

        resp.raise_for_status()

        # Pretty-print response if JSON, otherwise return raw text
        try:
            parsed_resp = json.loads(resp.text)
            response_text = json.dumps(parsed_resp, indent=2)
        except json.JSONDecodeError:
            response_text = resp.text

        return {
            "status_code": resp.status_code,
            "response_text": response_text,
            "headers_sent": final_headers
        }

    except requests.exceptions.RequestException as e:
        error_details = f"Error: {str(e)}\n"
        if hasattr(e, 'response') and e.response is not None:
            error_details += f"Status Code: {e.response.status_code}\nResponse Text: {e.response.text}\n"
        error_details += f"Traceback: {traceback.format_exc()}"
        print(f"\n=== Error Details ===")
        print(error_details)
        print("=====================\n")
        return {
            "status_code": None,
            "response_text": error_details,
            "headers_sent": final_headers
        }
