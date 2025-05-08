import requests
from urllib.parse import urljoin, urlparse
from .base import EndpointDiscoveryStrategy
import logging
import sys

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

class WeatherDiscoveryStrategy(EndpointDiscoveryStrategy):
    """Strategy for discovering weather API endpoints."""
    
    def discover(self, base_url: str, timeout: int = 5) -> list:
        """Discover weather API endpoints."""
        logger.info(f"Starting weather API discovery for: {base_url}")
        
        # Normalize the base URL
        parsed = urlparse(base_url)
        if not parsed.scheme:
            base_url = f"https://{base_url}"
            logger.debug(f"Added HTTPS scheme to URL: {base_url}")
        
        # Check if it's a weather API
        if not any(domain in base_url for domain in ['api.openweathermap.org', 'api.weatherapi.com', 'api.weather.gov']):
            logger.info(f"URL {base_url} is not a recognized weather API")
            return []
            
        endpoints = []
        
        # OpenWeatherMap specific endpoints
        if 'openweathermap.org' in base_url:
            logger.info("Detected OpenWeatherMap API")
            weather_paths = [
                '/data/2.5/weather',
                '/data/2.5/forecast',
                '/data/2.5/forecast/daily',
                '/data/2.5/group',
                '/data/2.5/find',
                '/geo/1.0/direct',
                '/geo/1.0/reverse'
            ]
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'FuzzyPrompts/1.0'
            }
            
            # Add API key if provided
            if self.api_key:
                logger.debug("Using provided API key for OpenWeatherMap")
                headers['appid'] = self.api_key
            
            for path in weather_paths:
                try:
                    # Add required query parameters
                    url = f"{urljoin(base_url, path)}?q=London&units=metric"
                    if self.api_key:
                        url += f"&appid={self.api_key}"
                    
                    logger.debug(f"Trying OpenWeatherMap endpoint: {url}")
                    response = requests.get(url, headers=headers, timeout=timeout)
                    logger.debug(f"Response status: {response.status_code}")
                    
                    # Accept both successful responses and rate limit responses
                    if response.status_code in [200, 201, 204, 401, 429]:
                        logger.info(f"Found valid endpoint: {url} (status: {response.status_code})")
                        endpoints.append({
                            'url': url,
                            'method': 'GET',
                            'status_code': response.status_code,
                            'is_authenticated': bool(self.api_key),
                            'suggested_payload': {
                                'q': 'London',
                                'units': 'metric'
                            }
                        })
                    else:
                        logger.debug(f"Endpoint {url} returned status {response.status_code}")
                        
                except requests.RequestException as e:
                    logger.error(f"Request failed for {url}: {str(e)}")
                    continue
                    
        # WeatherAPI.com specific endpoints
        elif 'weatherapi.com' in base_url:
            logger.info("Detected WeatherAPI.com")
            weather_paths = [
                '/v1/current.json',
                '/v1/forecast.json',
                '/v1/search.json',
                '/v1/history.json',
                '/v1/marine.json',
                '/v1/future.json'
            ]
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'FuzzyPrompts/1.0'
            }
            
            if self.api_key:
                logger.debug("Using provided API key for WeatherAPI.com")
                headers['key'] = self.api_key
            
            for path in weather_paths:
                try:
                    url = f"{urljoin(base_url, path)}?q=London"
                    if self.api_key:
                        url += f"&key={self.api_key}"
                    
                    logger.debug(f"Trying WeatherAPI.com endpoint: {url}")
                    response = requests.get(url, headers=headers, timeout=timeout)
                    logger.debug(f"Response status: {response.status_code}")
                    
                    if response.status_code in [200, 201, 204, 401, 429]:
                        logger.info(f"Found valid endpoint: {url} (status: {response.status_code})")
                        endpoints.append({
                            'url': url,
                            'method': 'GET',
                            'status_code': response.status_code,
                            'is_authenticated': bool(self.api_key),
                            'suggested_payload': {
                                'q': 'London'
                            }
                        })
                    else:
                        logger.debug(f"Endpoint {url} returned status {response.status_code}")
                        
                except requests.RequestException as e:
                    logger.error(f"Request failed for {url}: {str(e)}")
                    continue
                    
        # Weather.gov specific endpoints
        elif 'weather.gov' in base_url:
            logger.info("Detected Weather.gov API")
            weather_paths = [
                '/points',
                '/alerts',
                '/zones',
                '/offices',
                '/products',
                '/stations'
            ]
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'FuzzyPrompts/1.0'
            }
            
            for path in weather_paths:
                try:
                    url = urljoin(base_url, path)
                    logger.debug(f"Trying Weather.gov endpoint: {url}")
                    response = requests.get(url, headers=headers, timeout=timeout)
                    logger.debug(f"Response status: {response.status_code}")
                    
                    if response.status_code in [200, 201, 204]:
                        logger.info(f"Found valid endpoint: {url} (status: {response.status_code})")
                        endpoints.append({
                            'url': url,
                            'method': 'GET',
                            'status_code': response.status_code,
                            'is_authenticated': False
                        })
                    else:
                        logger.debug(f"Endpoint {url} returned status {response.status_code}")
                        
                except requests.RequestException as e:
                    logger.error(f"Request failed for {url}: {str(e)}")
                    continue
        
        logger.info(f"Weather API discovery complete. Found {len(endpoints)} endpoints")
        return endpoints 