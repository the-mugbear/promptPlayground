from flask import request, render_template
import json

def parse_headers_from_list_of_dict(list_of_dicts):
    """
    Converts a list of {"key": ..., "value": ...} into a dict.
    E.g. [
      {"key":"Content-Type","value":"application/json"},
      {"key":"Authorization","value":"Bearer XYZ"}
    ]
    => {"Content-Type": "application/json","Authorization": "Bearer XYZ"}
    """
    headers_dict = {}
    for item in list_of_dicts:
        key = item.get("key")
        val = item.get("value")
        if key and val:
            headers_dict[key] = val
    return headers_dict

def parse_headers_from_form(raw_headers_str):
    """
    Given user-typed lines like:
      Content-Type: application/json
      Authorization: Bearer <token>
    returns a dict:
      {"Content-Type":"application/json","Authorization":"Bearer <token>"}
    """
    headers = {}
    lines = raw_headers_str.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ':' not in line:
            continue
        key, val = line.split(':', 1)
        headers[key.strip()] = val.strip()
    return headers

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
