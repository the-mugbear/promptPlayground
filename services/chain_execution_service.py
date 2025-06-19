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

    def execute_chain(self, chain_id: int, execute_until_step_id: int = None, initial_context: dict = None):
        chain = db.session.get(APIChain, chain_id)
        if not chain:
            raise ChainExecutionError(
                f"APIChain with ID {chain_id} not found.")

        # This context is built dynamically, carrying values from one step to the next.
        # Start with any provided initial context (e.g., from test cases)
        chain_context = initial_context.copy() if initial_context else {}
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
                
                # Enhanced debugging for header templating
                logger.info(f"Step {step.step_order} - Current chain context: {chain_context}")
                logger.info(f"Step {step.step_order} - Headers template: {step.headers or '{}'}")
                logger.info(f"Step {step.step_order} - Payload template: {step.payload or '{}'}")
                
                try:
                    rendered_headers_str = render_template_string(step.headers or '{}', chain_context)
                    logger.info(f"Step {step.step_order} - Rendered headers string: {rendered_headers_str}")
                    rendered_headers = json.loads(rendered_headers_str)
                    logger.info(f"Step {step.step_order} - Parsed headers dict: {rendered_headers}")
                except Exception as header_error:
                    logger.error(f"Step {step.step_order} - Header templating/parsing error: {header_error}")
                    raise ChainExecutionError(f"Header templating failed: {header_error}") from header_error
                
                try:
                    rendered_payload_str = render_template_string(step.payload or '{}', chain_context)
                    logger.info(f"Step {step.step_order} - Rendered payload: {rendered_payload_str}")
                except Exception as payload_error:
                    logger.error(f"Step {step.step_order} - Payload templating error: {payload_error}")
                    raise ChainExecutionError(f"Payload templating failed: {payload_error}") from payload_error

                logger.info(
                    f"Executing Step {step.step_order}: '{current_endpoint_config.name}' with method {current_endpoint_config.method}")
                logger.info(f"Step {step.step_order} - Target URL: {current_endpoint_config.base_url}{current_endpoint_config.path}")
                logger.info(f"Step {step.step_order} - Final headers: {rendered_headers}")
                logger.info(f"Step {step.step_order} - Final payload: {rendered_payload_str}")
                
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
                    # Enhanced error reporting
                    status_code = api_response_data.get('status_code')
                    error_message = api_response_data.get("error_message")
                    response_body = api_response_data.get("response_body", "")
                    request_headers = api_response_data.get("request_headers_sent", {})
                    
                    err_msg = f"API call failed with status {status_code}"
                    if error_message:
                        err_msg += f" - {error_message}"
                    
                    # Log detailed error information
                    logger.error(f"Step {step.step_order} - API call failed:")
                    logger.error(f"  Status Code: {status_code}")
                    logger.error(f"  Error Message: {error_message}")
                    logger.error(f"  Response Body: {response_body[:500]}{'...' if len(response_body) > 500 else ''}")
                    logger.error(f"  Request Headers: {request_headers}")
                    logger.error(f"  Target URL: {current_endpoint_config.base_url}{current_endpoint_config.path}")
                    logger.error(f"  HTTP Method: {current_endpoint_config.method}")
                    
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
            endpoint = step.endpoint
            
            # --- Determine the correct templates to use (Step > Endpoint) ---
            payload_template = step.payload if step.payload is not None else endpoint.payload_template.template if endpoint.payload_template else '{}'
            headers_template = step.headers if step.headers is not None else json.dumps({h.key: h.value for h in endpoint.headers})

            # 1. Render Templates
            rendered_payload = render_template_string(payload_template, context)
            rendered_headers_str = render_template_string(headers_template, context)
            
            rendered_headers_dict = {}
            if rendered_headers_str and rendered_headers_str.strip():
                try:
                    rendered_headers_dict = json.loads(rendered_headers_str)
                except json.JSONDecodeError as e:
                    raise ChainExecutionError(f"Invalid JSON in rendered Headers for step {step.step_order}: {e}")

            # --- Handle Authentication ---
            if endpoint.auth_method == 'bearer' and endpoint.credentials_encrypted:
                # NOTE: You would decrypt the credentials here before using them.
                # For now, we'll assume they are plain text for the example.
                token = endpoint.credentials_encrypted 
                rendered_headers_dict['Authorization'] = f'Bearer {token}'
            elif endpoint.auth_method == 'api_key' and endpoint.credentials_encrypted:
                # This part would need to know the header name for the API key,
                # which is another field we could add to the Endpoint model.
                # For now, let's assume a common header name.
                api_key_header = "X-API-Key" 
                rendered_headers_dict[api_key_header] = endpoint.credentials_encrypted

            # 2. Execute Request using new Endpoint attributes
            response_data = execute_api_request(
                method=endpoint.method,
                hostname_url=endpoint.base_url, 
                endpoint_path=endpoint.path,    
                raw_headers_or_dict=rendered_headers_dict,
                http_payload_as_string=rendered_payload,
                timeout=endpoint.timeout_seconds
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
                    'url': f"{endpoint.base_url.rstrip('/')}/{endpoint.path.lstrip('/')}",
                    'headers': rendered_headers_dict,
                    'payload': rendered_payload,
                    'headers_template': headers_template,
                    'payload_template': payload_template
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

