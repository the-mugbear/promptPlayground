import requests
from urllib.parse import urljoin
from .base import EndpointDiscoveryStrategy

# ---------------------------------
# Anthropic API Discovery Strategy
# ---------------------------------
# Probes common Anthropic endpoints including model listing, metadata, and inference routes.
class AnthropicDiscoveryStrategy(EndpointDiscoveryStrategy):
    """
    Probes Anthropic-specific API routes and returns any that respond with JSON.
    Supports GET for model endpoints and POST for inference endpoints.
    """
    # All endpoints to check
    PATHS = [
        "/v1/models",                             # list available models (GET)
        "/v1/models/claude-3.7-sonnet",           # get model metadata (GET)
        "/v1/messages",                           # quickstart inference endpoint (POST)
        "/v1/complete",                           # legacy completion endpoint (POST)
        "/v1/chat/completions",                   # chat inference endpoint (POST)
        "/v1/embeddings",                         # embeddings endpoint (POST)
    ]

    # Map each path to its HTTP method
    METHOD_MAP = {
        "/v1/models": "GET",
        "/v1/models/claude-3.7-sonnet": "GET",
        "/v1/messages": "POST",
        "/v1/complete": "POST",
        "/v1/chat/completions": "POST",
        "/v1/embeddings": "POST",
    }

    # Payloads only needed for POST paths
    PAYLOADS = {
        "/v1/messages": {
            "model": "claude-chat",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens_to_sample": 0,
        },
        "/v1/complete": {
            "model": "claude-v1",
            "prompt": "ping",
            "max_tokens_to_sample": 0,
        },
        "/v1/chat/completions": {
            "model": "claude-chat",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens_to_sample": 0,
        },
        "/v1/embeddings": {
            "model": "claude-embedding",
            "input": "ping",
        },
    }

    def discover(self, base_url: str, timeout: int = 5):
        discovered = []
        headers = {
            "Accept": "application/json",
        }
        # Content-Type only needed for POST requests
        headers_post = {**headers, "Content-Type": "application/json"}

        # Anthropic uses X-API-Key for authentication
        if self.api_key:
            headers_post["X-API-Key"] = self.api_key
            headers["X-API-Key"] = self.api_key

        for path in self.PATHS:
            url = urljoin(base_url, path)
            method = self.METHOD_MAP.get(path, "GET")
            try:
                if method == "GET":
                    response = requests.get(url, headers=headers, timeout=timeout)
                else:
                    payload = self.PAYLOADS.get(path, {})
                    response = requests.post(url, headers=headers_post, json=payload, timeout=timeout)

                if response.status_code in (200, 400, 401, 403):
                    content_type = response.headers.get("Content-Type", "")
                    if "application/json" in content_type.lower():
                        discovered.append({
                            "url": url,
                            "method": method,
                            "status_code": response.status_code,
                        })
            except requests.RequestException:
                # ignore unreachable endpoints or timeouts
                continue

        return discovered
