import requests, json
from urllib.parse import urljoin
from .base import EndpointDiscoveryStrategy

class GoogleDiscoveryStrategy(EndpointDiscoveryStrategy):
    SUFFIX = "?discovery=rest&version=v1"

    def discover(self, base_url: str, timeout: int = 5):
        try:
            spec = requests.get(urljoin(base_url, self.SUFFIX), timeout=timeout).json()
        except Exception:
            return []
        results = []
        def walk(res, prefix=""):
            for data in res.values():
                for m_def in data.get("methods", {}).values():
                    results.append({"url": urljoin(base_url, m_def["path"]),
                                    "method": m_def["httpMethod"]})
                walk(data.get("resources", {}), prefix)
        walk(spec.get("resources", {}))
        return results
