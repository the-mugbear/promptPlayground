# services/chain_execution_service.py
from urllib.parse import urlparse # Add this import
from models.model_APIChain import APIChain, APIChainStep
from models.model_Endpoints import Endpoint
from .common.templating_service import render_string_with_context, TemplateRenderingError

from .common.data_extraction_service import extract_data_from_response, DataExtractionError
from services.common.http_request_service import execute_api_request
from extensions import db
import logging 

logger = logging.getLogger(__name__) 

class ChainExecutionError(Exception):
    """Custom exception for chain execution errors."""
    def __init__(self, message, step_order=None, original_exception=None):
        super().__init__(message)
        self.step_order = step_order
        self.original_exception = original_exception
        logger.error(f"ChainExecutionError at step {step_order}: {message}", exc_info=original_exception)


class APIChainExecutor:
    def __init__(self):
        pass

    def execute_chain(self, chain_id: int, execute_until_step_id: int = None):
        chain = db.session.get(APIChain, chain_id)
        if not chain:
            raise ChainExecutionError(f"APIChain with ID {chain_id} not found.")

        # This context is built dynamically, carrying values from one step to the next.
        chain_context = {}
        execution_results = []

        steps_to_execute = chain.steps.all() if hasattr(chain.steps, 'all') else chain.steps

        for step in steps_to_execute:
            # Initialize the result dict for this step
            step_result = {}
            try:
                # --- Phase 1: PREPARE & RENDER ---
                current_endpoint_config = step.endpoint
                if not current_endpoint_config:
                    raise ValueError(f"Endpoint configuration not found for step {step.step_order}")

                step_result = {"step_order": step.step_order, "endpoint_name": current_endpoint_config.name, "status": "processing"}
                
                # Render all necessary components using the current state of the chain_context
                rendered_base_url = render_string_with_context(current_endpoint_config.hostname, chain_context)
                rendered_path = render_string_with_context(current_endpoint_config.endpoint, chain_context)
                rendered_headers = {h.key: render_string_with_context(h.value, chain_context) for h in current_endpoint_config.headers}
                rendered_payload_str = render_string_with_context(current_endpoint_config.http_payload, chain_context) if current_endpoint_config.http_payload else None

                # --- Phase 2: EXECUTE ---
                logger.info(f"Executing Step {step.step_order}: '{current_endpoint_config.name}' with method {current_endpoint_config.method}")
                api_response_data = execute_api_request(
                    method=current_endpoint_config.method,
                    hostname_url=rendered_base_url,
                    endpoint_path=rendered_path,
                    raw_headers_or_dict=rendered_headers,
                    http_payload_as_string=rendered_payload_str
                )
                
                # Populate result with response info for logging and extraction
                step_result["response_status_code"] = api_response_data.get("status_code")
                response_body = api_response_data.get("response_body", "")
                step_result["response_body_preview"] = response_body[:200] + ("..." if len(response_body) > 200 else "")

                # --- Phase 3: VALIDATE ---
                # Consolidated check for any kind of failure from the API call
                is_successful_call = not api_response_data.get("error_message") and 200 <= (api_response_data.get("status_code") or 0) < 300
                
                if not is_successful_call:
                    err_msg = api_response_data.get("error_message") or f"API call returned error status: {api_response_data.get('status_code')}"
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
                            extracted_value = extract_data_from_response(api_response_data, rule)
                            chain_context[variable_name] = extracted_value
                            extracted_data[variable_name] = extracted_value
                    
                    # Create a preview of extracted data for logging/UI
                    step_result["extracted_data_preview"] = {k: str(v)[:50] + '...' if len(str(v)) > 50 else str(v) for k,v in extracted_data.items()}

            except (ValueError, TemplateRenderingError, DataExtractionError, ChainExecutionError) as e:
                # Catch our own controlled exceptions
                step_result.setdefault("status", "error")
                step_result["message"] = str(e)
                # This will be caught by the CLI command's handler, stopping the chain
                raise ChainExecutionError(f"Error at step {step.step_order}: {e}", step_order=step.step_order, original_exception=e) from e
            
            except Exception as e_unexpected:
                # Catch any other unexpected errors
                step_result.setdefault("status", "error")
                step_result["message"] = f"An unexpected error occurred: {str(e_unexpected)}"
                raise ChainExecutionError(f"Unexpected error at step {step.step_order}", step_order=step.step_order, original_exception=e_unexpected) from e_unexpected

            finally:
                # This 'finally' block ensures that the result of the step,
                # whether it ended in success or error, is always recorded.
                execution_results.append(step_result)
            
            # Check to see if we should stop here ( used in testing the upto link functionality )
            if execute_until_step_id is not None and step.id == execute_until_step_id:
                logger.info(f"Partial execution requested. Stopping after step {step.step_order} (ID: {step.id}).")
                break # Exit the loop

        logger.info(f"Chain execution completed for Chain ID: {chain_id}. Final context keys: {list(chain_context.keys())}")
        return {"final_context": chain_context, "step_results": execution_results}