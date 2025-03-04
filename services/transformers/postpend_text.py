from .base import Transformation

# Postpend subclass
class PostpendText(Transformation):
    id = "postpend_text"
    name = "Postpend Text"
    description = "Postpends text to each prompt."

    def apply(self, prompt: str, params: dict = None) -> str:
        if not params:
            return prompt
        return f"{prompt}{params.get('value','')}"