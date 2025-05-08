from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin
import logging
import sys
import requests
from requests.exceptions import SSLError, RequestException

from .strategies.openapi_strategy import OpenAPIStrategy
from .strategies.google_discovery import GoogleDiscoveryStrategy
from .strategies.generic_llm import GenericLLMStrategy
from .strategies.github import GitHubDiscoveryStrategy
from .strategies.weather import WeatherDiscoveryStrategy

# Get the logger for this module
logger = logging.getLogger(__name__)

class EndpointDiscoveryService:
    def __init__(self, api_key: Optional[str] = None):
        logger.info(f"Initializing EndpointDiscoveryService with API key: {'Present' if api_key else 'None'}")
        self.strategies = [
            WeatherDiscoveryStrategy(api_key),  # Try weather APIs first
            GitHubDiscoveryStrategy(api_key),
            OpenAPIStrategy(api_key),
            GoogleDiscoveryStrategy(api_key),
            GenericLLMStrategy(api_key),
        ]
        logger.info(f"Initialized {len(self.strategies)} discovery strategies")

    def _normalise(self, url: str):
        logger.debug(f"Normalizing URL: {url}")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        normalized = url.rstrip("/")
        logger.debug(f"Normalized URL: {normalized}")
        return normalized

    def discover_endpoints(self, base_url: str, timeout: int = 5) -> List[Dict]:
        logger.info(f"Starting endpoint discovery for: {base_url}")
        base_url = self._normalise(base_url)
        
        for i, strat in enumerate(self.strategies):
            strategy_name = strat.__class__.__name__
            logger.info(f"Trying strategy {i+1}/{len(self.strategies)}: {strategy_name}")
            try:
                results = strat.discover(base_url, timeout)
                if results:
                    logger.info(f"Strategy {strategy_name} found {len(results)} endpoints")
                    return results
                else:
                    logger.info(f"Strategy {strategy_name} found no endpoints")
            except Exception as e:
                logger.error(f"Error in strategy {strategy_name}: {str(e)}")
                
        logger.info(f"No endpoints found for {base_url} using any strategy")
        return []
