import requests
from urllib.parse import urljoin
from .base import EndpointDiscoveryStrategy

class GitHubDiscoveryStrategy(EndpointDiscoveryStrategy):
    """Strategy for discovering GitHub API endpoints."""
    
    def discover(self, base_url: str, timeout: int = 5) -> list:
        """Discover GitHub API endpoints."""
        if not base_url.endswith('api.github.com'):
            return []
            
        endpoints = []
        common_paths = [
            '/user',
            '/user/repos',
            '/repos',
            '/search/repositories',
            '/search/users',
            '/search/code',
            '/rate_limit',
            '/zen'
        ]
        
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'FuzzyPrompts/1.0'
        }
        
        if self.api_key:
            headers['Authorization'] = f'token {self.api_key}'
            
        for path in common_paths:
            try:
                url = urljoin(base_url, path)
                response = requests.get(url, headers=headers, timeout=timeout)
                
                if response.status_code in [200, 201, 204]:
                    endpoints.append({
                        'url': url,
                        'method': 'GET',
                        'status_code': response.status_code,
                        'is_authenticated': bool(self.api_key)
                    })
                    
                    # If this is a collection endpoint, add a POST endpoint
                    if path in ['/user/repos', '/repos']:
                        endpoints.append({
                            'url': url,
                            'method': 'POST',
                            'status_code': 201,
                            'is_authenticated': True,
                            'suggested_payload': {
                                'name': 'test-repo',
                                'description': 'Test repository',
                                'private': False
                            }
                        })
                        
            except requests.RequestException:
                continue
                
        return endpoints 