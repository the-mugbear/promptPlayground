# transformations/morse_code.py
from .base import Transformation

# Minimal dictionary for letters, digits, etc.
MORSE_CODE_DICT = {
    'A': '.-',    'B': '-...',  'C': '-.-.',  'D': '-..',
    'E': '.',     'F': '..-.',  'G': '--.',   'H': '....',
    'I': '..',    'J': '.---',  'K': '-.-',   'L': '.-..',
    'M': '--',    'N': '-.',    'O': '---',   'P': '.--.',
    'Q': '--.-',  'R': '.-.',   'S': '...',   'T': '-',
    'U': '..-',   'V': '...-',  'W': '.--',   'X': '-..-',
    'Y': '-.--',  'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.'
    # You can add punctuation if you like.
}

class MorseCode(Transformation):
    id = "morse_code"
    name = "Morse Code"
    description = "Convert each character to a .- style code."

    def apply(self, prompt: str, params: dict = None) -> str:
        """
        We'll uppercase the prompt, then convert known characters to Morse.
        Unrecognized chars can be skipped or replaced with '?'.
        """
        uppercase_prompt = prompt.upper()
        parts = []
        for char in uppercase_prompt:
            if char in MORSE_CODE_DICT:
                code = MORSE_CODE_DICT[char]
                parts.append(code)
            # else skip or add '?'
            # else:
            #     parts.append('?')
        return ' '.join(parts)
