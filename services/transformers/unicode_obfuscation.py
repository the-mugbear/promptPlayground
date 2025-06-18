import random
from .base import Transformation


class UnicodeObfuscationTransform(Transformation):
    id = "unicode_obfuscation"
    name = "Unicode Obfuscation"
    description = "Replace characters with similar-looking Unicode characters for adversarial testing"

    def apply(self, prompt: str, params: dict = None) -> str:
        """Apply Unicode obfuscation transformation to the prompt."""
        
        # Default Unicode character mappings (similar-looking characters)
        default_unicode_map = {
            'a': 'а',  # Cyrillic a (U+0430)
            'e': 'е',  # Cyrillic e (U+0435)
            'o': 'о',  # Cyrillic o (U+043E)
            'p': 'р',  # Cyrillic p (U+0440)
            'c': 'с',  # Cyrillic c (U+0441)
            'y': 'у',  # Cyrillic y (U+0443)
            'x': 'х',  # Cyrillic x (U+0445)
        }
        
        # Allow custom Unicode mappings via parameters
        if params and params.get("custom_mappings"):
            unicode_map = params["custom_mappings"]
        else:
            unicode_map = default_unicode_map
        
        # Get replacement percentage (default 30%)
        replacement_percentage = params.get("replacement_percentage", 0.3) if params else 0.3
        
        result = prompt
        for char, unicode_char in unicode_map.items():
            if random.random() < replacement_percentage:
                result = result.replace(char, unicode_char)
        
        return result