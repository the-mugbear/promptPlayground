from urllib.parse import urljoin
import requests, concurrent.futures
from .base import EndpointDiscoveryStrategy

_PATHS = [                 # trimmed to essentials
    "/v1/chat/completions", "/v1/completions",
    "/chat", "/completions", "/generate"
]

class GenericLLMStrategy(EndpointDiscoveryStrategy):
    HTTP_METHODS = ["POST", "GET"]

    def discover(self, base_url: str, timeout: int = 5):
        discovered = []
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futs = {
                pool.submit(requests.request, m, urljoin(base_url, ep),
                            headers=h, json={"prompt": "ping"}, timeout=timeout):
                (ep, m) for ep in _PATHS for m in self.HTTP_METHODS
            }
            for fut in concurrent.futures.as_completed(futs):
                ep, m = futs[fut]
                try:
                    r = fut.result()
                    if r.status_code in (200, 400, 401, 403):
                        if "json" in r.headers.get("content-type", ""):
                            discovered.append({"url": urljoin(base_url, ep),
                                               "method": m,
                                               "status_code": r.status_code})
                except requests.RequestException:
                    pass
        return discovered
