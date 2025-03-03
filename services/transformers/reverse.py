from .base import Transformation

class ReverseEncode(Transformation):
    id = "reverse"
    name = "Reverse Strings"
    description = "Reverses the characters in strings (test -> tset)."

    def apply(self, prompt: str, params: dict = None) -> str:
        return prompt[::-1]
