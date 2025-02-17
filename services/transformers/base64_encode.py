# Base64 subclass
import base64

from .base import Transformation

class Base64Encode(Transformation):
    id = "base64_encode"
    name = "Base64 Encode"

    def apply(self, prompt: str, params: dict = None) -> str:
        return base64.b64encode(prompt.encode()).decode()