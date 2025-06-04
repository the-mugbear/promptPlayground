# services/common/http_request_service.py
import json
import requests
import traceback
import logging # Ensure logging is imported
import socket
from services.common.header_parser_service import parse_raw_headers_with_cookies
from urllib.parse import urlparse

logger = logging.getLogger(__name__) # This should already be at the top of your file

def replay_post_request(hostname_url: str, endpoint_path: str, http_payload_as_string: str, raw_headers_or_dict, timeout=120, verify=True):
    """
    Replay a POST request using provided hostname, endpoint, payload, and raw headers.
    Parses any "Cookie" header into a cookies dict.
    Returns a dict with status_code, response_text, and headers_sent.
    """

    final_headers, cookies = {}, {} 
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

    if hostname_url.startswith('http://127.0.0.1') or hostname_url.startswith('http://localhost'):
        hostname_url = hostname_url.replace('127.0.0.1', 'host.containers.internal').replace('localhost', 'host.containers.internal')
        logger.info(f"Container networking: Updated hostname to {hostname_url}") # Changed from print

    url = f"{hostname_url.rstrip('/')}/{endpoint_path.lstrip('/')}"

    logger.info(f"URL: {url}") # Changed from print
    logger.info(f"Headers: {json.dumps(final_headers, indent=2)}") # Changed from print
    # Log the payload that will be attempted; tasks/case.py prepares this as a JSON string
    logger.info(f"Payload String (to be sent or parsed): {http_payload_as_string}") # Changed from print
    
    try:
        parsed_url = urlparse(hostname_url) 
        host_for_resolve = parsed_url.hostname
        port_for_resolve = parsed_url.port

        log_port_str = f":{port_for_resolve}" if port_for_resolve else ""
        logger.debug(f"Attempting to resolve {host_for_resolve}{log_port_str}") # Changed from print, using DEBUG
        if host_for_resolve:
            try:
                ip = socket.gethostbyname(host_for_resolve)
                logger.debug(f"Hostname ({host_for_resolve}) resolved to IP: {ip}") # Changed from print, using DEBUG
            except socket.gaierror as e:
                logger.warning(f"Failed to resolve hostname ({host_for_resolve}): {e}") # Changed from print, using WARNING
        else:
            logger.warning("Could not determine host for DNS resolution from input.") # Changed from print
    except Exception as e_parse: 
        logger.error(f"Error during hostname/port parsing for logging: {e_parse}") # Changed from print

    try:
        payload_to_send_to_requests = None
        send_as_json_flag = False # Renamed to avoid conflict with 'json' module
        try:
            parsed_json_payload = json.loads(http_payload_as_string)
            payload_to_send_to_requests = parsed_json_payload 
            send_as_json_flag = True
            logger.debug("Successfully parsed http_payload_as_string as JSON for sending.") # Changed from print
            # logger.debug(f"Parsed JSON for request: {json.dumps(parsed_json_payload, indent=2)}") # Optional: if you want to see it again
        except json.JSONDecodeError as e:
            logger.warning(f"Payload is not valid JSON: {str(e)}. Sending as raw text/data.") # Changed from print
            payload_to_send_to_requests = http_payload_as_string 
            send_as_json_flag = False

        logger.info("Sending POST request...") # Changed from print
        if send_as_json_flag:
            resp = requests.post(
                url,
                json=payload_to_send_to_requests, # 'json' param takes a dict and serializes it
                headers=final_headers,
                cookies=cookies,
                timeout=timeout,
                verify=verify
            )
        else: 
            resp = requests.post(
                url,
                data=payload_to_send_to_requests, # 'data' param takes string or bytes
                headers=final_headers, 
                cookies=cookies,
                timeout=timeout,
                verify=verify
            )

        logger.info("\n=== Response Details ===") # Changed from print
        logger.info(f"Status Code: {resp.status_code}") # Changed from print
        logger.info(f"Response Headers: {json.dumps(dict(resp.headers), indent=2)}") # Changed from print
        # Log only a snippet of response text if it can be very long
        response_text_snippet = resp.text[:200] + "..." if len(resp.text) > 200 else resp.text
        logger.info(f"Response Text Snippet: {response_text_snippet}") # Changed from print
        logger.info("=====================") # Changed from print

        resp.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        try:
            parsed_resp = resp.json() # requests built-in JSON decoder
            response_text_to_return = json.dumps(parsed_resp, indent=2) # Pretty print for return
        except requests.exceptions.JSONDecodeError:
            response_text_to_return = resp.text # Return raw text if not JSON

        return {
            "status_code": resp.status_code,
            "response_text": response_text_to_return,
            "headers_sent": final_headers, # Return the headers that were actually sent
            "error": None # Explicitly indicate no error from this function's perspective
        }

    except requests.exceptions.RequestException as e:
        error_details = f"Error: {str(e)}\n"
        if hasattr(e, 'response') and e.response is not None:
            error_details += f"Status Code: {e.response.status_code}\nResponse Text: {e.response.text}\n"
        error_details += f"Traceback: {traceback.format_exc()}"
        
        logger.error("\n=== HTTP Request Error Details ===") # Changed from print
        logger.error(error_details) # Log the multi-line string directly
        logger.error("=====================") # Changed from print
        
        return {
            "status_code": e.response.status_code if hasattr(e, 'response') and e.response is not None else None,
            "response_text": error_details, # Return the detailed error string as response_text
            "headers_sent": final_headers,
            "error": str(e) # Provide the original error string as well
        }