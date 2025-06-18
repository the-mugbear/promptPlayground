from .base import Transformation


class CharacterSubstitutionTransform(Transformation):
    id = "character_substitution"
    name = "Character Substitution"
    description = "Replace characters with special symbols for obfuscation"

    def apply(self, prompt: str, params: dict = None) -> str:
        """Apply character substitution transformation to the prompt."""
        
        # Default character substitutions
        default_substitutions = {
            'a': '@',
            'e': '€', 
            'i': '!',
            'o': 'ø',
            'u': 'µ',
            's': '$',
        }
        
        # Allow custom substitutions via parameters
        if params and params.get("custom_substitutions"):
            substitutions = params["custom_substitutions"]
        else:
            substitutions = default_substitutions
        
        result = prompt
        for char, substitute in substitutions.items():
            # Replace both lowercase and uppercase
            result = result.replace(char, substitute)
            result = result.replace(char.upper(), substitute)
        
        return result