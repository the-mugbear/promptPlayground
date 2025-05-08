import requests, yaml, json
from urllib.parse import urljoin
from .base import EndpointDiscoveryStrategy

_DOC_PATHS = [
    "/.well-known/openapi.yaml", "/.well-known/openapi.json",
    "/openapi.yaml", "/openapi.json",
    "/swagger.yaml", "/swagger.json",
]

class OpenAPIStrategy(EndpointDiscoveryStrategy):
    def _get(self, url, timeout):
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            if url.endswith((".yaml", ".yml")):
                return yaml.safe_load(r.text)
            return r.json()           # .json or explicit content‑type
        return None

    def discover(self, base_url: str, timeout: int = 5):
        results = []
        for p in _DOC_PATHS:
            spec = self._get(urljoin(base_url, p), timeout)
            if not spec:
                continue
            for path, ops in spec.get("paths", {}).items():
                for method in ops:
                    clean = path.replace("{", "").replace("}", "")
                    results.append({"url": urljoin(base_url, clean),
                                    "method": method.upper(),
                                    "spec_source": p})
            if results:
                return results        # stop after first working spec
        return results
