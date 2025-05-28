# services/endpoints/endpoint_services.py
import json
import logging
from models.model_Endpoints import Endpoint, APIHeader
from services.common.http_request_service import replay_post_request
from extensions import db

logger = logging.getLogger(__name__)

DEFAULT_PRINTABLE_ASCII = "".join(chr(i) for i in range(32, 127))

def identify_invalid_characters(endpoint_id: int, characters_to_test: str = None) -> dict:
    """
    Identifies characters that cause an endpoint to refuse a request.

    Args:
        endpoint_id: The ID of the endpoint to test.
        characters_to_test: A string of characters to test. Defaults to printable ASCII (32-126).

    Returns:
        A dictionary containing:
            - 'invalid_chars': A list of unique characters identified as invalid.
            - 'details': A list of dictionaries, each detailing the character tested,
                         status code, a summary of the response, and whether it was deemed invalid.
            - 'error': An error message if a significant issue occurred (e.g., endpoint not found).
                       This key will only be present if there's an error.
    """
    if characters_to_test is None:
        characters_to_test = DEFAULT_PRINTABLE_ASCII

    endpoint = db.session.get(Endpoint, endpoint_id)

    if not endpoint:
        logger.error(f"Endpoint with ID {endpoint_id} not found.")
        return {"invalid_chars": [], "details": [], "error": f"Endpoint with ID {endpoint_id} not found."}

    if not endpoint.http_payload or "{{INJECT_PROMPT}}" not in endpoint.http_payload:
        logger.error(f"Endpoint {endpoint_id} http_payload is missing or does not contain '{{INJECT_PROMPT}}'.")
        return {
            "invalid_chars": [],
            "details": [],
            "error": f"Endpoint http_payload is missing or does not contain '{{INJECT_PROMPT}}'."
        }

    invalid_chars_set = set()
    details_list = []

    refusal_keywords = ["refusal", "cannot process", "invalid character"]

    for char_to_test in characters_to_test:
        try:
            # Construct payload by replacing {{INJECT_PROMPT}}
            # Ensure the character is properly escaped for JSON if the payload is JSON
            # For simplicity, this example assumes direct string replacement.
            # If http_payload is a JSON string, more careful construction is needed.
            # For now, we'll assume it's a template where direct replacement is fine.
            # A robust solution might involve parsing JSON, injecting, then re-serializing.
            
            # Safely inject the character. If it's part of a JSON string, it needs to be escaped.
            # json.dumps(char_to_test)[1:-1] creates a JSON-escaped version of the char, without the outer quotes.
            escaped_char = json.dumps(char_to_test)[1:-1]
            payload_str = endpoint.http_payload.replace("{{INJECT_PROMPT}}", escaped_char)

            headers = {h.key: h.value for h in (endpoint.headers or [])}
            header_str = "\n".join(f"{k}: {v}" for k, v in headers.items()) # Convert to expected format

            response = replay_post_request(
                hostname=endpoint.hostname,
                endpoint=endpoint.endpoint, # This is the path, not the full URL
                payload=payload_str,
                headers=header_str
            )

            status_code = None
            response_text = ""
            is_refusal = False

            if response:
                status_code = response.get("status_code")
                response_text = response.get("response_text", "")
                response_text_lower = response_text.lower() if response_text else ""

                # Refusal conditions
                if status_code != 200 or status_code is None:
                    is_refusal = True
                else:
                    for keyword in refusal_keywords:
                        if keyword in response_text_lower:
                            is_refusal = True
                            break
            else: # No response from replay_post_request implies an issue
                is_refusal = True
                response_text = "No response from HTTP service"


            if is_refusal:
                invalid_chars_set.add(char_to_test)

            details_list.append({
                "character": char_to_test,
                "status_code": status_code,
                "response_summary": response_text[:200],  # Summary of response
                "is_invalid": is_refusal
            })

        except Exception as e:
            logger.error(f"Error testing character '{char_to_test}' for endpoint {endpoint_id}: {e}", exc_info=True)
            details_list.append({
                "character": char_to_test,
                "status_code": None,
                "response_summary": f"Exception during test: {str(e)}",
                "is_invalid": True # Treat exceptions during testing as an invalid/problematic character scenario
            })
            invalid_chars_set.add(char_to_test) # Add char to invalid if an exception occurs

    return {
        "invalid_chars": sorted(list(invalid_chars_set)),
        "details": details_list
    }

# Example usage (not part of the service, just for illustration if run directly)
if __name__ == '__main__':
    # This part requires a running Flask app context for db.session.get to work
    # and a configured Celery app for replay_post_request if it uses Celery tasks.
    # For direct execution, these would need to be mocked or the function refactored
    # to allow dependency injection.
    print("This script is intended to be used as a service module.")
    # Example:
    # Create a mock endpoint and test (requires more setup for DB and replay_post_request)
    # endpoint_id_to_test = 1 
    # results = identify_invalid_characters(endpoint_id_to_test, "<>!\\\"")
    # print(results)
    pass
