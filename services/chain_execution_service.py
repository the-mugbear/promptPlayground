# services/chain_execution_service.py
import logging
import json

from urllib.parse import urlparse  # Add this import
from models.model_APIChain import APIChain, APIChainStep
from models.model_Endpoints import Endpoint
from services.common.templating_service import render_template_string

from .common.data_extraction_service import extract_data_from_response, DataExtractionError
from services.common.templating_service import render_template_string
from services.common.http_request_service import execute_api_request
from services.common.data_extraction_service import extract_data_from_response, DataExtractionError

from extensions import db


logger = logging.getLogger(__name__)


class ChainExecutionError(Exception):
    """Custom exception for chain execution errors."""
    def __init__(self, message, step_order=None, original_exception=None):
        super().__init__(message)
        self.step_order = step_order
        self.original_exception = original_exception
        logger.error(
            f"ChainExecutionError at step {step_order}: {message}", exc_info=original_exception)


class APIChainExecutor:
    def __init__(self):
        pass

    def execute_chain(self, chain_id: int, execute_until_step_id: int = None):
        chain = db.session.get(APIChain, chain_id)
        if not chain:
            raise ChainExecutionError(
                f"APIChain with ID {chain_id} not found.")

        # This context is built dynamically, carrying values from one step to the next.
        chain_context = {}
        execution_results = []

        # Sort steps by their defined order
        steps_to_execute = sorted(chain.steps, key=lambda s: s.step_order)

        for step in steps_to_execute:
            # Initialize the result dict for this step
            step_result = {}
            try:
                # --- Phase 1: PREPARE & RENDER ---
                current_endpoint_config = step.endpoint
                if not current_endpoint_config:
                    raise ValueError(
                        f"Endpoint configuration not found for step {step.step_order}")

                step_result = {"step_order": step.step_order,
                               "endpoint_name": current_endpoint_config.name, "status": "processing"}

                # Render all necessary components using the current state of the chain_context
                # The headers for an endpoint are now a single JSON string template
                rendered_headers = json.loads(render_template_string(step.headers or '{}', chain_context))
                rendered_payload_str = render_template_string(step.payload or '{}', chain_context)

                logger.info(
                    f"Executing Step {step.step_order}: '{current_endpoint_config.name}' with method {current_endpoint_config.method}")
                
                # --- Phase 2: EXECUTE ---
                api_response_data = execute_api_request(
                    method=current_endpoint_config.method,
                    hostname_url=current_endpoint_config.base_url, # Base URL is not templated per step
                    endpoint_path=current_endpoint_config.path,   # Path is not templated per step
                    raw_headers_or_dict=rendered_headers,
                    http_payload_as_string=rendered_payload_str
                )

                # Populate result with response info for logging and extraction
                step_result["response_status_code"] = api_response_data.get(
                    "status_code")
                response_body = api_response_data.get("response_body", "")
                step_result["response_body_preview"] = response_body[:200] + \
                    ("..." if len(response_body) > 200 else "")

                # --- Phase 3: VALIDATE ---
                # Consolidated check for any kind of failure from the API call
                is_successful_call = not api_response_data.get("error_message") and 200 <= (
                    api_response_data.get("status_code") or 0) < 300

                if not is_successful_call:
                    err_msg = api_response_data.get(
                        "error_message") or f"API call returned error status: {api_response_data.get('status_code')}"
                    raise ChainExecutionError(f"API call failed: {err_msg}")

                step_result["status"] = "success"
                logger.info(f"Step {step.step_order} successful with status {api_response_data.get('status_code')}.")

                # --- Phase 4: EXTRACT ---
                if step.data_extraction_rules:
                    extracted_data = {}
                    for rule in step.data_extraction_rules:
                        variable_name = rule.get("variable_name")
                        if variable_name:
                            # DataExtractionError will be caught by the main exception handler below
                            extracted_value = extract_data_from_response(
                                api_response_data, rule)
                            chain_context[variable_name] = extracted_value
                            extracted_data[variable_name] = extracted_value

                    # Create a preview of extracted data for logging/UI
                    step_result["extracted_data_preview"] = {k: str(
                        v)[:50] + '...' if len(str(v)) > 50 else str(v) for k, v in extracted_data.items()}

            except (ValueError, DataExtractionError, ChainExecutionError) as e:
                step_result.setdefault("status", "error")
                step_result["message"] = str(e)
                raise ChainExecutionError(
                    f"Error at step {step.step_order}: {e}", step_order=step.step_order, original_exception=e) from e

            except Exception as e_unexpected:
                step_result.setdefault("status", "error")
                step_result["message"] = f"An unexpected error occurred: {str(e_unexpected)}"
                raise ChainExecutionError(
                    f"Unexpected error at step {step.step_order}", step_order=step.step_order, original_exception=e_unexpected) from e_unexpected

            finally:
                # This 'finally' block ensures that the result of the step,
                # whether it ended in success or error, is always recorded.
                execution_results.append(step_result)

            # Check to see if we should stop here ( used in testing the upto link functionality )
            if execute_until_step_id is not None and step.id == execute_until_step_id:
                logger.info(f"Partial execution requested. Stopping after step {step.step_order} (ID: {step.id}).")
                break  # Exit the loop

        logger.info(f"Chain execution completed for Chain ID: {chain_id}. Final context keys: {list(chain_context.keys())}")
        return {"final_context": chain_context, "step_results": execution_results}

    def execute_single_step(self, step, context):
        """
        Executes a single, prepared step of an API chain.

        This method performs three main actions:
        1. Renders the headers and payload using the current context.
        2. Executes the HTTP request using the http_request_service.
        3. Extracts data from the response using the data_extraction_service.

        Args:
            step (APIChainStep): The step object to execute.
            context (dict): The current dictionary of context variables.

        Returns:
            dict: A dictionary containing the request, response, and any new
                  context variables that were extracted.
        """
        try:
            payload_template = step.payload if step.payload is not None else step.endpoint.http_payload or '{}'
            headers_template = step.headers if step.headers is not None else json.dumps({h.key: h.value for h in step.endpoint.headers})

            # 1. RENDER TEMPLATES
            rendered_payload = render_template_string(payload_template, context)
            rendered_headers_str = render_template_string(headers_template, context)

            rendered_headers_dict = {}
            if rendered_headers_str and rendered_headers_str.strip():
                try:
                    rendered_headers_dict = json.loads(rendered_headers_str)
                except json.JSONDecodeError as e:
                    raise ChainExecutionError(f"Invalid JSON in rendered headers for step {step.step_order}: {e}")

            # 2. EXECUTE REQUEST
            # Use the actual function from your http_request_service
            response_data = execute_api_request(
                method=step.endpoint.method,
                hostname_url=step.endpoint.hostname,
                endpoint_path=step.endpoint.endpoint,
                raw_headers_or_dict=rendered_headers_dict,
                http_payload_as_string=rendered_payload
            )

            # 3. EXTRACT DATA
            new_context_variables = {}
            for rule in step.data_extraction_rules:
                try:
                    # The rule itself contains the variable_name to use as the key
                    variable_name = rule.get("variable_name")
                    if not variable_name:
                        continue # Skip rules without a name

                    # Use the actual function from your data_extraction_service
                    extracted_value = extract_data_from_response(response_data, rule)
                    new_context_variables[variable_name] = extracted_value
                except DataExtractionError as e:
                    # Log the extraction error but don't stop the whole chain
                    print(f"Data extraction warning for step {step.step_order}: {e}")


            # Return a comprehensive result for the debugger UI
            return {
                'request': {
                    'url': f"{step.endpoint.hostname.rstrip('/')}/{step.endpoint.endpoint.lstrip('/')}",
                    'headers': rendered_headers_dict,
                    'payload': rendered_payload,
                },
                'response': {
                    'status_code': response_data.get('status_code'),
                    'headers': response_data.get('response_headers'),
                    'body': response_data.get('response_body'),
                },
                'new_context_variables': new_context_variables
            }

        except Exception as e:
            # Catch any other exceptions and wrap them in our custom error
            raise ChainExecutionError(f"Fatal error in step {step.step_order} ({step.name}): {e}")

