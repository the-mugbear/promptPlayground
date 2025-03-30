# services/header_parser_service.py
import json
from http.cookies import SimpleCookie

def parse_raw_headers(raw_headers: str) -> dict:
    """
    Parse a raw header string (e.g., copied from developer tools) into a dictionary.
    If a header is 'Cookie', parse its value using SimpleCookie and return a JSON-serialized string.
    
    :param raw_headers: The raw headers as a newline-separated string.
    :return: A dictionary of header keys and their values.
    """
    headers = {}
    if not raw_headers:
        return headers

    # Process each non-empty line that contains a colon
    for line in raw_headers.splitlines():
        line = line.strip()
        if not line or ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        
        if key.lower() == 'cookie':
            simple_cookie = SimpleCookie()
            simple_cookie.load(value)
            cookies_dict = {cookie_key: morsel.value 
                            for cookie_key, morsel in simple_cookie.items()}
            # Serialize cookies to a JSON string to store in APIHeader.value
            headers[key] = json.dumps(cookies_dict)
        else:
            headers[key] = value
    return headers
