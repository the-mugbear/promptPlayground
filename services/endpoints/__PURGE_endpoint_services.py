from flask import request, render_template
import json

def parse_raw_headers(raw_headers_str):
    """
    Given user typed lines like:
      Content-Type: application/json
      Authorization: Bearer xyz123

    returns a dict:
      {"Content-Type": "application/json", "Authorization": "Bearer xyz123"}
    """
    headers = {}
    for line in raw_headers_str.splitlines():
        line = line.strip()
        if not line:
            continue
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        headers[key.strip()] = value.strip()
    return headers

def headers_from_apiheader_list(header_objects):
    """
    Given a list of APIHeader objects, return a dict
    { "Content-Type": "application/json", ... }
    """
    headers_dict = {}
    for h in header_objects:
        headers_dict[h.key] = h.value
    return headers_dict
