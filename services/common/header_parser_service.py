# services/header_parser_service.py
import json
from http.cookies import SimpleCookie

def parse_cookie_header(cookie_header: str) -> dict:
    """
    Parse a Cookie header string.
    If the cookie header appears to be in JSON format, load it using json.loads.
    Otherwise, use SimpleCookie to parse key=value pairs.
    """
    cookie_header = cookie_header.strip()
    if cookie_header.startswith("{") and cookie_header.endswith("}"):
        try:
            return json.loads(cookie_header)
        except json.JSONDecodeError:
            pass  # Fallback to SimpleCookie if JSON parsing fails

    simple_cookie = SimpleCookie()
    simple_cookie.load(cookie_header)
    return {key: morsel.value for key, morsel in simple_cookie.items()}

def parse_raw_headers(raw_headers: str) -> dict:
    """
    Parse a raw header string (e.g., copied from developer tools) into a dictionary.
    For the 'Cookie' header, process it using SimpleCookie and store it as a JSON string.
    
    :param raw_headers: The raw headers as a newline-separated string.
    :return: A dictionary of header keys and their values.
    """
    headers = {}
    if not raw_headers:
        return headers

    for line in raw_headers.splitlines():
        line = line.strip()
        if not line:
            continue
        if ':' not in line:
            # This line might be a request line; log it for debugging.
            print(f"Skipping line without colon: {line}")
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if key.lower() == 'cookie':
            cookies = parse_cookie_header(value)
            headers[key] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        else:
            headers[key] = value
    return headers

def parse_raw_headers_with_cookies(raw_headers: str) -> (dict, dict):
    """
    Parse a raw header string and return a tuple of two dictionaries:
      (headers_dict, cookies_dict)
    The cookies are extracted from the 'Cookie' header.
    """
    headers = {}
    cookies = {}
    if not raw_headers:
        return headers, cookies

    for line in raw_headers.splitlines():
        line = line.strip()
        if not line or ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if key.lower() == 'cookie':
            cookies = parse_cookie_header(value)
        else:
            headers[key] = value
    return headers, cookies

def headers_from_apiheader_list(header_objects):
    """
    Given a list of APIHeader objects, return a dict
    { "Content-Type": "application/json", ... }
    """
    headers_dict = {}
    for h in header_objects:
        headers_dict[h.key] = h.value
    return headers_dict
