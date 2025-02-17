from .base import Transformation

class UnicodeTagEncode(Transformation):
    id = "unicode_encode"
    name = "Unicode Tag Encode"
    description = "Converts each character into \\uXXXX format."

    def apply(self, prompt: str, params: dict = None) -> str:
        return "".join(f"\\u{ord(c):04X}" for c in prompt)
