from abc import ABC, abstractmethod
import logging
import sys
from typing import List, Dict, Optional

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add console handler if not already present
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

class EndpointDiscoveryStrategy(ABC):
    """Base class for endpoint discovery strategies."""
    
    def __init__(self, api_key: str = None):
        """Initialize the strategy with optional API key."""
        self.api_key = api_key
        logger.debug(f"Initialized {self.__class__.__name__} with API key: {'Yes' if api_key else 'No'}")

    @abstractmethod
    def discover(self, base_url: str, timeout: int = 5) -> list:
        """Discover endpoints using this strategy.
        
        Args:
            base_url: The base URL to discover endpoints from
            timeout: Request timeout in seconds
            
        Returns:
            List of discovered endpoints, each containing:
            - url: The endpoint URL
            - method: HTTP method
            - status_code: Response status code
            - is_authenticated: Whether authentication is required
            - suggested_payload: Optional suggested payload for testing
        """
        pass
