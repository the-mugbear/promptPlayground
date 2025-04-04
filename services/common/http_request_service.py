import json
import requests
import traceback
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

    # Build the URL
    url = f"{hostname.rstrip('/')}/{endpoint_path.lstrip('/')}"

    try:
        # Attempt to parse payload as JSON first
        try:
            parsed_json = json.loads(http_payload)
            resp = requests.post(
                url,
                json=parsed_json,
                headers=final_headers,
                cookies=cookies,
                timeout=timeout,
                verify=verify
            )
        except json.JSONDecodeError:
            # Fallback to sending as raw text if JSON parsing fails
            resp = requests.post(
                url,
                data=http_payload,
                headers=final_headers,
                cookies=cookies,
                timeout=timeout,
                verify=verify
            )

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
        return {
            "status_code": None,
            "response_text": error_details,
            "headers_sent": final_headers
        }
