from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from . import EndpointDiscoveryService
from typing import List, Dict
import time
import logging
import sys
from extensions import db
from models.model_Endpoints import Endpoint, DiscoveredEndpoint
from urllib.parse import urlparse

# Get the logger for this module
logger = logging.getLogger(__name__)

def _handle_discovery_error(self, exc, task_name: str, max_retries: int = 3) -> Dict:
    """Helper function to handle discovery task errors with retry logic."""
    logger.error(f"Error in {task_name}: {str(exc)}", exc_info=True)
    try:
        retry_delay = 5 * (2 ** self.request.retries)
        logger.warning(f"Retrying {task_name} in {retry_delay} seconds...")
        self.retry(exc=exc, countdown=retry_delay)
    except MaxRetriesExceededError:
        logger.error(f"Max retries exceeded for {task_name}")
        return {
            'error': f'Failed to discover endpoints after {max_retries} retries: {str(exc)}',
            'endpoints': []
        }

def _save_discovered_endpoints(endpoint_id: int, results: List[Dict]) -> None:
    """Save discovered endpoints to the database."""
    try:
        # Get the parent endpoint
        endpoint = Endpoint.query.get(endpoint_id)
        if not endpoint:
            logger.error(f"Parent endpoint {endpoint_id} not found")
            return

        # Clear existing discovered endpoints
        DiscoveredEndpoint.query.filter_by(endpoint_id=endpoint_id).delete()
        
        # Save new discovered endpoints
        for result in results:
            # Extract path from URL
            parsed_url = urlparse(result['url'])
            path = parsed_url.path
            
            discovered = DiscoveredEndpoint(
                endpoint_id=endpoint_id,
                path=path,
                status_code=result.get('status_code', 0),
                method=result.get('method', 'GET'),
                response_headers=result.get('response_headers'),
                response_body=result.get('response_body')
            )
            db.session.add(discovered)
        
        db.session.commit()
        logger.info(f"Saved {len(results)} discovered endpoints for endpoint {endpoint_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving discovered endpoints: {str(e)}")

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def discover_endpoints_task(self, base_url: str, strategy: str = 'auto', api_key: str = None, endpoint_id: int = None) -> List[Dict]:
    """
    Celery task for discovering endpoints with retry logic.
    
    Args:
        base_url: The base URL to discover endpoints from
        strategy: The discovery strategy to use
        api_key: Optional API key for authentication
        endpoint_id: Optional ID of the parent endpoint to store discovered endpoints
        
    Returns:
        List of discovered endpoints
    """
    logger.info(f"Starting endpoint discovery task for {base_url} with strategy {strategy}")
    try:
        discovery_service = EndpointDiscoveryService(api_key)
        results = discovery_service.discover_endpoints(base_url, timeout=5)
        logger.info(f"Discovery task completed. Found {len(results)} endpoints")
        
        # If endpoint_id is provided, save the discovered endpoints
        if endpoint_id is not None:
            # Check if endpoint exists
            endpoint = Endpoint.query.get(endpoint_id)
            if not endpoint:
                # Create a new endpoint if it doesn't exist
                parsed_url = urlparse(base_url)
                endpoint = Endpoint(
                    name=f"Discovered API - {parsed_url.netloc}",
                    hostname=parsed_url.netloc,
                    endpoint="/",
                    http_payload="{}"  # Empty JSON payload
                )
                db.session.add(endpoint)
                db.session.commit()
                logger.info(f"Created new endpoint with ID {endpoint.id} for {base_url}")
            
            _save_discovered_endpoints(endpoint.id, results)
        
        return results
        
    except Exception as e:
        logger.error(f"Error in discover_endpoints_task: {str(e)}", exc_info=True)
        return _handle_discovery_error(self, e, "discover_endpoints_task")

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def discover_openapi_task(self, base_url: str, api_key: str = None, endpoint_id: int = None) -> List[Dict]:
    """Celery task for OpenAPI/Swagger discovery."""
    logger.info(f"Starting OpenAPI discovery task for {base_url}")
    try:
        discovery_service = EndpointDiscoveryService(api_key)
        results = discovery_service._discover_openapi(base_url)
        logger.info(f"OpenAPI discovery completed. Found {len(results)} endpoints")
        
        # Save discovered endpoints if endpoint_id is provided
        if endpoint_id and results:
            _save_discovered_endpoints(endpoint_id, results)
            
        return results
    except Exception as exc:
        return _handle_discovery_error(self, exc, "OpenAPI discovery task")

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def discover_google_task(self, base_url: str, api_key: str = None, endpoint_id: int = None) -> List[Dict]:
    """Celery task for Google Discovery API discovery."""
    logger.info(f"Starting Google API discovery task for {base_url}")
    try:
        discovery_service = EndpointDiscoveryService(api_key)
        results = discovery_service._discover_google(base_url)
        logger.info(f"Google API discovery completed. Found {len(results)} endpoints")
        
        # Save discovered endpoints if endpoint_id is provided
        if endpoint_id and results:
            _save_discovered_endpoints(endpoint_id, results)
            
        return results
    except Exception as exc:
        return _handle_discovery_error(self, exc, "Google API discovery task")

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def discover_heuristic_task(self, base_url: str, api_key: str = None, endpoint_id: int = None) -> List[Dict]:
    """Celery task for heuristic discovery."""
    logger.info(f"Starting heuristic discovery task for {base_url}")
    try:
        discovery_service = EndpointDiscoveryService(api_key)
        results = discovery_service._discover_heuristic(base_url)
        logger.info(f"Heuristic discovery completed. Found {len(results)} endpoints")
        
        # Save discovered endpoints if endpoint_id is provided
        if endpoint_id and results:
            _save_discovered_endpoints(endpoint_id, results)
            
        return results
    except Exception as exc:
        return _handle_discovery_error(self, exc, "heuristic discovery task") 