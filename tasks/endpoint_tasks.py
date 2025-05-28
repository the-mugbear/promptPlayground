# tasks/endpoint_tasks.py
import logging
import json # Added for JSON operations
from datetime import datetime # Added for timestamping
from celery_app import celery # Assuming celery_app.py initializes Celery app instance
from services.endpoints.endpoint_services import identify_invalid_characters
from services.crawler.crawler_service import crawl_site # Added for site crawl
from tasks.base import ContextTask # Import ContextTask for potential future use or consistency
from extensions import db # Added for database operations
from models.model_Endpoints import Endpoint # Added for Endpoint model

logger = logging.getLogger(__name__)

@celery.task(name="tasks.perform_invalid_character_check", base=ContextTask)
def perform_invalid_character_check_task(endpoint_id):
    """
    Celery task to perform an invalid character check for a given endpoint.
    """
    logger.info(f"Starting invalid character check for endpoint ID: {endpoint_id}")
    try:
        # Using default printable ASCII characters for the check
        results = identify_invalid_characters(endpoint_id=endpoint_id)
        
        if "error" in results:
            logger.error(f"Error during invalid character check for endpoint {endpoint_id}: {results['error']}")
        else:
            invalid_chars_str = "".join(results['invalid_chars'])
            # Log full details for better diagnostics, but summarize for general info
            # Consider logging details at DEBUG level if too verbose for INFO
            logger.info(f"Invalid character check for endpoint {endpoint_id} completed. Found {len(invalid_chars_str)} invalid characters: '{invalid_chars_str}'.")
            logger.debug(f"Full details for endpoint {endpoint_id}: {results['details']}") # Log details at debug level

            if invalid_chars_str: # Only update if there are invalid characters found
                endpoint = db.session.get(Endpoint, endpoint_id)
                if endpoint:
                    endpoint.identified_invalid_characters = invalid_chars_str
                    try:
                        db.session.commit()
                        logger.info(f"Saved identified invalid characters '{invalid_chars_str}' to endpoint {endpoint_id}.")
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"Failed to save identified invalid characters for endpoint {endpoint_id}: {e}", exc_info=True)
                else:
                    logger.warning(f"Endpoint {endpoint_id} not found, could not save invalid characters.")
            elif not results['invalid_chars']: # No invalid characters found
                logger.info(f"No invalid characters identified for endpoint {endpoint_id}. Nothing to save.")
        
        return results
    except Exception as e:
        logger.error(f"Unexpected exception in perform_invalid_character_check_task for endpoint {endpoint_id}: {e}", exc_info=True)
        # Depending on retry policy, could raise e to trigger retry
        return {"error": f"Unexpected exception: {str(e)}", "invalid_chars": [], "details": []}


@celery.task(name="tasks.perform_site_crawl", base=ContextTask)
def perform_site_crawl_task(endpoint_id):
    logger.info(f"Starting site crawl for endpoint ID: {endpoint_id}")
    # ContextTask ensures db.session is available and managed.
    endpoint = db.session.get(Endpoint, endpoint_id)

    if not endpoint:
        logger.error(f"Endpoint {endpoint_id} not found for site crawl.")
        return {"error": "Endpoint not found", "crawled_pages": {}, "all_discovered_links": []}

    # Update status to in_progress and set timestamp
    endpoint.last_crawl_status = "in_progress"
    endpoint.last_crawl_timestamp = datetime.utcnow()
    try:
        db.session.commit()
        logger.info(f"Site crawl status for endpoint {endpoint_id} set to 'in_progress'.")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update crawl status to 'in_progress' for endpoint {endpoint_id}: {e}", exc_info=True)
        # Optionally, re-raise or return to indicate this initial failure
        return {"error": "Failed to set crawl status to in_progress", "crawled_pages": {}, "all_discovered_links": []}


    start_url = endpoint.hostname # Assuming hostname includes scheme e.g. "http://example.com"
    
    # Ensure start_url has a scheme, default to http if not present, as crawl_site expects it.
    if not start_url.startswith("http://") and not start_url.startswith("https://"):
        # More robust scheme checking might be needed if hostname can be just "example.com"
        # For now, assuming it might be "example.com" or "http://example.com"
        # If it's just "example.com", prepend "http://"
        if "://" not in start_url: # Check if any scheme is present
            start_url = "http://" + start_url
            logger.info(f"Defaulted scheme to http for start_url: {start_url}")
        else: # A different scheme might be present, or it's malformed. Log and potentially error.
            logger.warning(f"Hostname {start_url} has an unusual scheme or format. Proceeding as is.")
            
    # Default parameters for the crawl for now
    max_depth = 1 
    domain_restriction = True
    additional_paths = None # e.g. ['/robots.txt', '/sitemap.xml']
    custom_strings_patterns = None

    try:
        results = crawl_site( # This is the actual crawl operation
            start_url=start_url,
            max_depth=max_depth,
            domain_restriction=domain_restriction,
            additional_paths=additional_paths,
            custom_strings_patterns=custom_strings_patterns
        )

        num_crawled = len(results.get('crawled_pages', {}))
        num_links = len(results.get('all_discovered_links', []))
        logger.info(f"Site crawl for endpoint {endpoint_id} ({start_url}) completed by service. Crawled {num_crawled} pages. Found {num_links} unique links (within depth {max_depth}).")

        # Aggregate found strings
        aggregated_strings_found = {}
        for _url, page_data in results.get('crawled_pages', {}).items():
            if page_data.get('found_strings'):
                for category, items_list in page_data['strings_found'].items():
                    if items_list:
                        if category not in aggregated_strings_found:
                            aggregated_strings_found[category] = set()
                        aggregated_strings_found[category].update(items_list)
        
        # Convert sets to lists for JSON serialization
        final_aggregated_strings = {k: sorted(list(v)) for k, v in aggregated_strings_found.items()}

        # Update endpoint with results
        endpoint.discovered_links_json = json.dumps(results.get('all_discovered_links', []))
        endpoint.found_strings_summary_json = json.dumps(final_aggregated_strings)
        endpoint.last_crawl_status = "completed"
        # endpoint.last_crawl_timestamp is already set at the beginning

        try:
            db.session.commit()
            logger.info(f"Successfully saved crawl results for endpoint {endpoint_id}. Status: completed.")
            if final_aggregated_strings:
                 logger.info(f"Overall summary of unique strings found and saved for endpoint {endpoint_id}: {final_aggregated_strings}")
            else:
                logger.info(f"No strings of interest found and saved during crawl for endpoint {endpoint_id}.")

        except Exception as e_commit:
            db.session.rollback()
            logger.error(f"Failed to save crawl results for endpoint {endpoint_id}: {e_commit}", exc_info=True)
            # Status remains 'in_progress' or could be set to 'failed_to_save'
            endpoint.last_crawl_status = "error_saving_results" # Custom status
            try:
                db.session.commit() # Attempt to save the error status
            except:
                db.session.rollback() # Give up if even this fails

        return results # Return the full results dict from crawl_site
        
    except Exception as e:
        logger.error(f"Site crawl task failed for endpoint {endpoint_id} ({start_url}): {type(e).__name__} - {e}", exc_info=True)
        if endpoint: # Check if endpoint object exists
            endpoint.last_crawl_status = "failed"
            # endpoint.last_crawl_timestamp is already set
            try:
                db.session.commit()
                logger.info(f"Site crawl status for endpoint {endpoint_id} set to 'failed'.")
            except Exception as e_commit_fail:
                db.session.rollback()
                logger.error(f"Failed to update crawl status to 'failed' for endpoint {endpoint_id}: {e_commit_fail}", exc_info=True)
        return {"error": f"Crawl task failed: {type(e).__name__} - {str(e)}", "crawled_pages": {}, "all_discovered_links": []}
