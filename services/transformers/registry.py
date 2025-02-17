from .base import Transformation
from .base64_encode import Base64Encode
from .prepend_text import PrependText
from .postpend_text import PostpendText
from .unicode_encode import UnicodeTagEncode
from .morsecode_encode import MorseCode

# When adding a transformation, create a class and place it in it's own file for modularity. Reference an existing class for format help.set
# Modify the TRANSFORMATIONS dict by adding it below.
# Modify the HTML form on templates/test_runs/create_test_run.html to add support for the new transformer

TRANSFORMATIONS = {
    "prepend_text": PrependText(),
    "postpend_text": PostpendText(),
    "unicode_encode": UnicodeTagEncode(),
    "base64_encode": Base64Encode(),
    "morse_code": MorseCode()
}

TRANSFORM_PARAM_CONFIG = {
    "prepend_text": {
        "param_keys": ["prepend_text_value"],
        "param_map": {"prepend_text_value": "text_to_prepend"},
        "default_params": {"text_to_prepend": ""}
    },
    "postpend_text": {
        "param_keys": ["postpend_text_value"],
        "param_map": {"postpend_text_value": "text_to_postpend"},
        "default_params": {"text_to_postpend": ""}
    },
    "base64_encode": {
        "param_keys": [],  # no user input needed
        "param_map": {},
        "default_params": {}
    },
    "unicode_encode": {
        "param_keys": [],  # no user input needed
        "param_map": {},
        "default_params": {}
    },
    "morse_code": {
        "param_keys": [],  # no user input needed
        "param_map": {},
        "default_params": {}
    },
    # "some_other_transform": {
    #   "param_keys": ["some_input_field"],
    #   "default_params": {"some_input_field":"foo"}
    # },
}

def apply_transformation(t_id, prompt, params):
    transform_obj = TRANSFORMATIONS.get(t_id)
    if not transform_obj:
        return prompt
    return transform_obj.apply(prompt, params=params)
