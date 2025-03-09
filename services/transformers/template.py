# A description of what the transformer does would be great and goes right here
from .base import Transformation

class INSERT_TRANSFORMER_NAME(Transformation):
    id = "INSERT_TRANSFORMER_ID"
    name = "INSERT_TRANSFORMER_NAME"
    description = "PROVIDE A DESCRIPTION OF WHAT THE TRANSFORMER DOES. (How does it change the prompt?)"

    # https://docs.python.org/3/library/codecs.html#codec-base-classes
    def apply(self, prompt: str, params: dict = None) -> str:

        # CODE TO PERFORM THE TRANSFORMATION GOES HERE. YOU CAN REPLACE 'prompt' WITH ANY OTHER STRING
        # OTHERWISE HAVE YOUR TRANSFORMED STRING REPLACE PROMPT SO THAT IT'S RETURNED
        
        return prompt