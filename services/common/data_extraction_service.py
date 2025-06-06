# services/common/data_extraction_service.py
import json

class DataExtractionError(ValueError):
    """Custom error for data extraction issues."""
    pass

# Modified to accept the dictionary from execute_api_request
def extract_data_from_response(response_data: dict, extraction_rule: dict) -> any:
    """
    Extracts data from an HTTP response data dictionary based on a single extraction rule.
    
    response_data schema (expected from execute_api_request):
    {
        "status_code": int,
        "response_headers": dict,
        "response_body": str,
        "error_message": str | None
        # ... other keys like request_headers_sent
    }
    """
    source_type = extraction_rule.get("source_type")
    source_identifier = extraction_rule.get("source_identifier")
    variable_name = extraction_rule.get("variable_name", "N/A")

    # Even if there was an HTTP error, we might still want to extract from the response
    # if response_data.get("error_message"):
    #     logger.warning(f"Attempting data extraction for '{variable_name}' despite earlier HTTP error: {response_data['error_message']}")

    status_code = response_data.get("status_code")
    actual_response_headers = response_data.get("response_headers", {})
    response_body_text = response_data.get("response_body", "")

    if source_type == "status_code":
        return status_code
    
    elif source_type == "raw_body":
        return response_body_text

    elif source_type == "header":
        if not source_identifier:
            raise DataExtractionError(f"Rule for '{variable_name}': source_identifier (header name) is required for source_type 'header'")

        # The .get() method is case-sensitive. HTTP headers are case-insensitive.
        # This loop finds the header regardless of its case.
        for key, value in actual_response_headers.items():
            if key.lower() == source_identifier.lower():
                return value
        # If the loop finishes without finding the header, return None.
        return None

    elif source_type == "json_body":
        if not response_body_text: # Handle if response_body is empty string or None
             raise DataExtractionError(f"Rule for '{variable_name}': Response body is empty, cannot parse as JSON.")
        try:
            response_json = json.loads(response_body_text)
        except json.JSONDecodeError as e:
            raise DataExtractionError(f"Rule for '{variable_name}': Response body is not valid JSON. Body: '{response_body_text[:100]}...'. Details: {e}") from e
        
        if not source_identifier: # Get the whole JSON body
            return response_json
        
        keys = source_identifier.split('.')
        current_val = response_json
        try:
            for key_part in keys:
                if isinstance(current_val, list):
                    try:
                        idx = int(key_part)
                        current_val = current_val[idx]
                    except (IndexError, ValueError, TypeError) as e_list:
                        raise KeyError(f"Index '{key_part}' invalid or out of bounds in path '{source_identifier}' for variable '{variable_name}'. Path traversal stopped at list.") from e_list
                elif isinstance(current_val, dict):
                    current_val = current_val[key_part]
                else:
                    raise KeyError(f"Path '{source_identifier}' for variable '{variable_name}' attempts to traverse a non-dict/list type ({type(current_val)}) at segment '{key_part}'.")
            return current_val
        except KeyError as e_key:
            raise DataExtractionError(f"Rule for '{variable_name}': Key or path '{source_identifier}' not found in JSON response. Missing segment: {e_key}") from e_key
        except Exception as e_general:
             raise DataExtractionError(f"Rule for '{variable_name}': Unexpected error traversing JSON path '{source_identifier}'. Details: {e_general}") from e_general
    else:
        raise DataExtractionError(f"Rule for '{variable_name}': Unsupported source_type: {source_type}")
