# https://en.wikipedia.org/wiki/ROT13
# ROT13 is a simple letter substitution cipher that replaces a letter with the 13th letter after it in the Latin alphabet. 
from .base import Transformation
import codecs

class Rot13(Transformation):
    id = "rot13"
    name = "ROT13"
    description = "Applies ROT13 encoding to the prompt (shifts letters by 13 positions)."

    # https://docs.python.org/3/library/codecs.html#codec-base-classes
    def apply(self, prompt: str, params: dict = None) -> str:
        return codecs.encode(prompt, 'rot_13')