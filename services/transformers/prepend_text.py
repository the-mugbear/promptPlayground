from .base import Transformation

# Prepend subclass
class PrependText(Transformation):
    id = "prepend_text"
    name = "Prepend Text"
    description = "Prepends text to each prompt."

    def apply(self, prompt: str, params: dict = None) -> str:
        if not params:
            return prompt
        prefix = params.get('value') or params.get('text_to_prepend', '')
        return f"{prefix}{prompt}"