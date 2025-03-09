from .base import Transformation
from .base64_encode import Base64Encode
from .prepend_text import PrependText
from .postpend_text import PostpendText
from .unicode_encode import UnicodeTagEncode
from .morsecode_encode import MorseCode
from .reverse import ReverseEncode
from .rot13 import Rot13

# When adding a transformation, create a class and place it in it's own file for modularity. Reference an existing class for format help.set
# Modify the TRANSFORMATIONS dict by adding it below.
# Modify the HTML form on templates/test_runs/create_test_run.html to add support for the new transformer

TRANSFORMATIONS = {
    "prepend_text": PrependText(),
    "postpend_text": PostpendText(),
    "unicode_encode": UnicodeTagEncode(),
    "base64_encode": Base64Encode(),
    "morse_code": MorseCode(),
    "reverse_string": ReverseEncode(),
    "rot13": Rot13()
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
    "reverse_string": {
        "param_keys": [],  # no user input needed
        "param_map": {},
        "default_params": {}
    },
    "rot13": {
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

# The functions below are support functions for the create_suite.html page to help apply transformations in bulk
# while respecting the sequence of selections
def apply_multiple_transformations(t_ids, prompt, all_params):
    """
    Apply a list of transformation IDs in sequence to a single prompt string.

    :param t_ids: List of transformation IDs (strings) in the order they should be applied
    :param prompt: The original test case string
    :param all_params: Dictionary of user inputs, e.g. {
        'prepend_text_value': 'Foo_',
        'postpend_text_value': '_Bar',
        ...
      }
    :return: The transformed string after all transformations are applied.
    """
    transformed = prompt
    for t_id in t_ids:
        transformed = apply_transformation(t_id, transformed, all_params)
    return transformed


def apply_transformations_to_lines(t_ids, lines, all_params):
    """
    Apply a list of transformation IDs to multiple prompt lines (test cases).

    :param t_ids: List of transformation IDs (strings)
    :param lines: List of test case strings
    :param all_params: Dictionary of user inputs
    :return: New list of transformed strings
    """
    results = []
    for line in lines:
        new_line = apply_multiple_transformations(t_ids, line, all_params)
        results.append(new_line)
    return results
