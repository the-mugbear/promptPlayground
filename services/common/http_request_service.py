# services/common/http_request_service.py
import json
import requests
import traceback
import logging
from typing import Dict, Any, Union

# Other imports remain the same...
from services.common.header_parser_service import parse_raw_headers_with_cookies, parse_cookie_header
from urllib.parse import urlparse
import socket

logger = logging.getLogger(__name__)

# --- 1. The "Core" Executor Function ---
def _execute_request(
    method: str,
    url: str,
    headers: Dict[str, Any] = None,
    cookies: Dict[str, Any] = None,
    payload_json: Dict[str, Any] = None,
    payload_data: Union[str, bytes] = None,
    files: Dict[str, Any] = None,  # For future file/image/audio uploads
    timeout: int = 120,
    verify: bool = True
) -> Dict[str, Any]:
    """
    Internal function that directly executes an HTTP request with prepared data.
    """

    logger.debug(f"Core executor: Making {method} request to {url}")
    try:
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            cookies=cookies,
            json=payload_json,
            data=payload_data,
            files=files,
            timeout=timeout,
            verify=verify
        )

        logger.info(f"Response received: Status {resp.status_code}")
        # Return a rich dictionary that the rest of the app can use
        return {
            "status_code": resp.status_code,
            "response_headers": dict(resp.headers),
            "response_body": resp.text,
            "error_message": None
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request Exception: {e}", exc_info=True)
        resp_from_error = getattr(e, 'response', None)

        error_response = {
            "status_code": resp_from_error.status_code if resp_from_error else None,
            "response_headers": dict(resp_from_error.headers) if resp_from_error else {},
            "response_body": resp_from_error.text if resp_from_error else "",
            "error_message": str(e)
        }
        return error_response


# --- 2. The "Wrapper" Function ---
def execute_api_request(
    method: str,
    hostname_url: str,
    endpoint_path: str,
    raw_headers_or_dict: Union[str, Dict[str, Any]],
    http_payload_as_string: str = None,
    files_to_upload: Dict[str, Any] = None,  # Ready for the future!
    timeout: int = 120,
    verify: bool = True
) -> Dict[str, Any]:
    """
    Prepares and executes an API request, handling complex inputs like header strings
    and string-based payloads. This is the primary interface for other services.
    """
    # --- Preparation Step 1: Headers and Cookies ---
    final_headers, cookies = {}, {}
    if isinstance(raw_headers_or_dict, str):
        final_headers, cookies = parse_raw_headers_with_cookies(
            raw_headers_or_dict)
    elif isinstance(raw_headers_or_dict, dict):
        final_headers = raw_headers_or_dict.copy()
        cookies_str = final_headers.pop(
            'Cookie', None) or final_headers.pop('cookie', None)
        if cookies_str:
            # Use the sophisticated cookie parsing instead of simple split
            logger.debug(f"Parsing cookie header: {cookies_str}")
            cookies = parse_cookie_header(cookies_str)
            logger.debug(f"Extracted cookies: {cookies}")

    # --- Preparation Step 2: URL ---
    if hostname_url.startswith(('http://127.0.0.1', 'http://localhost')):
        hostname_url = hostname_url.replace('127.0.0.1', 'host.containers.internal').replace(
            'localhost', 'host.containers.internal')
        logger.info(
            f"Container networking: Updated hostname to {hostname_url}")

    final_url = f"{hostname_url.rstrip('/')}/{endpoint_path.lstrip('/')}"

    # --- Preparation Step 3: Payload ---
    payload_json = None
    payload_data = None
    # This logic correctly determines how to treat the string payload
    if http_payload_as_string:
        try:
            # Prefer sending as JSON if possible, as it's a common use case
            payload_json = json.loads(http_payload_as_string)
            logger.debug("Payload interpreted as JSON.")
        except json.JSONDecodeError:
            payload_data = http_payload_as_string
            logger.debug("Payload is not JSON, will be sent as raw data.")

    # --- Logging Step ---
    logger.info(f"Preparing to send {method.upper()} request to {final_url}")
    logger.info(f"Headers: {json.dumps(final_headers, indent=2)}")
    if http_payload_as_string:
        logger.info(
            f"Payload Body (first 500 chars): {http_payload_as_string[:500]}")

    # --- Execution Step ---
    # Call the core executor with the cleanly prepared arguments
    result = _execute_request(
        method=method,
        url=final_url,
        headers=final_headers,
        cookies=cookies,
        payload_json=payload_json,
        payload_data=payload_data,
        files=files_to_upload,  # Pass files through
        timeout=timeout,
        verify=verify
    )

    # Add the request headers and cookies to the final result for debugging purposes
    result['request_headers_sent'] = final_headers.copy()
    result['request_cookies_sent'] = cookies.copy()
    
    # Also add a combined view showing what the actual HTTP request looked like
    combined_debug_headers = final_headers.copy()
    if cookies:
        # Add the cookies back as a Cookie header for debugging visibility
        cookie_header_value = "; ".join(f"{k}={v}" for k, v in cookies.items())
        combined_debug_headers['Cookie'] = cookie_header_value
    result['request_headers_with_cookies'] = combined_debug_headers
    
    return result
