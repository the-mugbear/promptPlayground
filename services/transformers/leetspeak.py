from .base import Transformation


class LeetspeakTransform(Transformation):
    id = "leetspeak"
    name = "Leetspeak Encoding"
    description = "Transform text using leetspeak (1337 speak) character substitutions"

    def apply(self, prompt: str, params: dict = None) -> str:
        """Apply leetspeak transformation to the prompt."""
        
        # Default leetspeak substitutions
        default_replacements = {
            'a': '4', 'A': '4',
            'e': '3', 'E': '3', 
            'i': '1', 'I': '1',
            'o': '0', 'O': '0',
            's': '5', 'S': '5',
            't': '7', 'T': '7',
            'l': '1', 'L': '1',
            'g': '9', 'G': '9'
        }
        
        # Allow custom replacements via parameters
        if params and params.get("custom_replacements"):
            replacements = params["custom_replacements"]
        else:
            replacements = default_replacements
        
        result = prompt
        for char, replacement in replacements.items():
            result = result.replace(char, replacement)
        
        return result