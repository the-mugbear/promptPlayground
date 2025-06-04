import json
import requests
import traceback
import logging
import socket
from services.common.header_parser_service import parse_raw_headers_with_cookies
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Moved the POST request functionality to a service file as it's common across endpoint creation/testing and test_run execution
def replay_post_request(hostname_url: str, endpoint_path: str, http_payload_as_string: str, raw_headers_or_dict, timeout=120, verify=True):
    """
    Replay a POST request using provided hostname, endpoint, payload, and raw headers.
    Parses any "Cookie" header into a cookies dict.
    Returns a dict with status_code, response_text, and headers_sent.
    """

    final_headers, cookies = {}, {} # Initialize
    if isinstance(raw_headers_or_dict, str):
        final_headers, cookies = parse_raw_headers_with_cookies(raw_headers_or_dict)
    elif isinstance(raw_headers_or_dict, dict):
        final_headers = raw_headers_or_dict.copy()
        cookies_str = final_headers.pop('Cookie', None) or final_headers.pop('cookie', None)
        if cookies_str and isinstance(cookies_str, str):
            for part in cookies_str.split(';'):
                if '=' in part:
                    name, value = part.split('=', 1)
                    cookies[name.strip()] = value.strip()
    
    final_headers.setdefault("Content-Type", "application/json")

    # Handle container networking - replace localhost/127.0.0.1 with host.containers.internal
    # Didn't work but left in case it ever does
    if hostname_url.startswith('http://127.0.0.1') or hostname_url.startswith('http://localhost'):
        hostname_url = hostname_url.replace('127.0.0.1', 'host.containers.internal').replace('localhost', 'host.containers.internal')
        print(f"Container networking: Updated hostname to {hostname_url}")

    # Build the URL
    url = f"{hostname_url.rstrip('/')}/{endpoint_path.lstrip('/')}"

    print("\n=== Request Details ===")
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(final_headers, indent=2)}")
    print(f"Raw Payload: {http_payload_as_string}")
    
    # --- Robust Hostname/Port Parsing for Logging ---
    try:
        parsed_url = urlparse(hostname_url) # Use urlparse for robust parsing
        host_for_resolve = parsed_url.hostname
        port_for_resolve = parsed_url.port

        log_port_str = f":{port_for_resolve}" if port_for_resolve else ""
        print(f"\nAttempting to resolve {host_for_resolve}{log_port_str}")
        if host_for_resolve:
            try:
                ip = socket.gethostbyname(host_for_resolve)
                print(f"Hostname ({host_for_resolve}) resolved to IP: {ip}")
            except socket.gaierror as e:
                print(f"Failed to resolve hostname ({host_for_resolve}): {e}")
        else:
            print("Could not determine host for DNS resolution from input.")
    except Exception as e_parse: # Catch any errors from urlparse or attribute access
        print(f"Error during hostname/port parsing for logging: {e_parse}")

    print("=====================\n")

    try:
        # replay_post_request expects http_payload_as_string to be a JSON string
        # because it tries json.loads() on it first.
        payload_to_send_to_requests = None
        send_as_json = False
        try:
            # Validate and parse the incoming http_payload_as_string
            parsed_json_payload = json.loads(http_payload_as_string)
            payload_to_send_to_requests = parsed_json_payload # Send as dict if valid JSON
            send_as_json = True
            print("Successfully parsed JSON payload for sending.")
            # print(f"Parsed JSON: {json.dumps(parsed_json_payload, indent=2)}") # Already logged above effectively
        except json.JSONDecodeError as e:
            print(f"\nPayload is not valid JSON: {str(e)}. Sending as raw text/data.")
            # print("Raw payload being sent as data:")
            # print(http_payload_as_string)
            payload_to_send_to_requests = http_payload_as_string # Send as raw string
            send_as_json = False

        print("\nSending POST request...")
        if send_as_json:
            resp = requests.post( # Use requests.post directly for clarity
                url,
                json=payload_to_send_to_requests, # requests handles dict -> json string
                headers=final_headers,
                cookies=cookies,
                timeout=timeout,
                verify=verify
            )
        else: # Send as raw data
            resp = requests.post(
                url,
                data=payload_to_send_to_requests, # requests sends data as-is
                headers=final_headers, # Ensure Content-Type is appropriate if not application/json
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
        try:
            parsed_response_json = resp.json()
            response_content_to_return = json.dumps(parsed_response_json, indent=2)
        except requests.exceptions.JSONDecodeError:
            response_content_to_return = resp.text
        return {
            "status_code": resp.status_code,
            "response_text": response_content_to_return,
            "headers_sent": final_headers,
            "error": None
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
