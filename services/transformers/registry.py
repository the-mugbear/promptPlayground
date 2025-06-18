from .base import Transformation
from .base64_encode import Base64Encode
from .prepend_text import PrependText
from .postpend_text import PostpendText
from .unicode_encode import UnicodeTagEncode
from .morsecode_encode import MorseCode
from .reverse import ReverseEncode
from .rot13 import Rot13

# Evil Agent / Adversarial Transformations
from .role_playing import RolePlayingTransform
from .social_engineering import SocialEngineeringTransform
from .context_injection import ContextInjectionTransform
from .prompt_injection import PromptInjectionTransform
from .authority_appeal import AuthorityAppealTransform
from .urgency_pressure import UrgencyPressureTransform
from .leetspeak import LeetspeakTransform
from .unicode_obfuscation import UnicodeObfuscationTransform
from .character_substitution import CharacterSubstitutionTransform

# When adding a transformation, create a class and place it in it's own file for modularity. Reference an existing class for format help.set
# Modify the TRANSFORMATIONS dict by adding it below.
# Modify the HTML form on templates/test_runs/create_test_run.html to add support for the new transformer

TRANSFORMATIONS = {
    # Basic Transformations
    "prepend_text": PrependText(),
    "postpend_text": PostpendText(),
    "unicode_encode": UnicodeTagEncode(),
    "base64_encode": Base64Encode(),
    "morse_code": MorseCode(),
    "reverse_string": ReverseEncode(),
    "rot13": Rot13(),
    
    # Evil Agent / Adversarial Transformations
    "role_playing": RolePlayingTransform(),
    "social_engineering": SocialEngineeringTransform(),
    "context_injection": ContextInjectionTransform(),
    "prompt_injection": PromptInjectionTransform(),
    "authority_appeal": AuthorityAppealTransform(),
    "urgency_pressure": UrgencyPressureTransform(),
    "leetspeak": LeetspeakTransform(),
    "unicode_obfuscation": UnicodeObfuscationTransform(),
    "character_substitution": CharacterSubstitutionTransform(),
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
    
    # Evil Agent / Adversarial Transformation Configurations
    "role_playing": {
        "param_keys": ["custom_role"],
        "param_map": {"custom_role": "custom_role"},
        "default_params": {"custom_role": ""}
    },
    "social_engineering": {
        "param_keys": ["custom_technique"],
        "param_map": {"custom_technique": "custom_technique"},
        "default_params": {"custom_technique": ""}
    },
    "context_injection": {
        "param_keys": ["custom_context"],
        "param_map": {"custom_context": "custom_context"},
        "default_params": {"custom_context": ""}
    },
    "prompt_injection": {
        "param_keys": ["custom_pattern"],
        "param_map": {"custom_pattern": "custom_pattern"},
        "default_params": {"custom_pattern": ""}
    },
    "authority_appeal": {
        "param_keys": ["custom_authority"],
        "param_map": {"custom_authority": "custom_authority"},
        "default_params": {"custom_authority": ""}
    },
    "urgency_pressure": {
        "param_keys": ["custom_phrase"],
        "param_map": {"custom_phrase": "custom_phrase"},
        "default_params": {"custom_phrase": ""}
    },
    "leetspeak": {
        "param_keys": [],  # no user input needed, uses default replacements
        "param_map": {},
        "default_params": {}
    },
    "unicode_obfuscation": {
        "param_keys": ["replacement_percentage"],
        "param_map": {"replacement_percentage": "replacement_percentage"},
        "default_params": {"replacement_percentage": "0.3"}
    },
    "character_substitution": {
        "param_keys": [],  # no user input needed, uses default substitutions
        "param_map": {},
        "default_params": {}
    },
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

def get_transformations_by_category():
    """
    Get transformations organized by category for easier UI organization.
    
    :return: Dictionary with categories as keys and transformation info as values
    """
    return {
        "basic": {
            "name": "Basic Transformations",
            "transformations": [
                {"id": "prepend_text", "name": TRANSFORMATIONS["prepend_text"].name},
                {"id": "postpend_text", "name": TRANSFORMATIONS["postpend_text"].name},
                {"id": "reverse_string", "name": TRANSFORMATIONS["reverse_string"].name},
            ]
        },
        "encoding": {
            "name": "Encoding & Obfuscation",
            "transformations": [
                {"id": "base64_encode", "name": TRANSFORMATIONS["base64_encode"].name},
                {"id": "unicode_encode", "name": TRANSFORMATIONS["unicode_encode"].name},
                {"id": "morse_code", "name": TRANSFORMATIONS["morse_code"].name},
                {"id": "rot13", "name": TRANSFORMATIONS["rot13"].name},
                {"id": "leetspeak", "name": TRANSFORMATIONS["leetspeak"].name},
                {"id": "unicode_obfuscation", "name": TRANSFORMATIONS["unicode_obfuscation"].name},
                {"id": "character_substitution", "name": TRANSFORMATIONS["character_substitution"].name},
            ]
        },
        "adversarial": {
            "name": "Adversarial / Evil Agent",
            "transformations": [
                {"id": "role_playing", "name": TRANSFORMATIONS["role_playing"].name},
                {"id": "social_engineering", "name": TRANSFORMATIONS["social_engineering"].name},
                {"id": "context_injection", "name": TRANSFORMATIONS["context_injection"].name},
                {"id": "prompt_injection", "name": TRANSFORMATIONS["prompt_injection"].name},
                {"id": "authority_appeal", "name": TRANSFORMATIONS["authority_appeal"].name},
                {"id": "urgency_pressure", "name": TRANSFORMATIONS["urgency_pressure"].name},
            ]
        }
    }

def get_evil_agent_transformations():
    """
    Get list of transformation IDs that are commonly used for evil agent attacks.
    
    :return: List of transformation IDs
    """
    return [
        "role_playing",
        "social_engineering", 
        "context_injection",
        "prompt_injection",
        "authority_appeal",
        "urgency_pressure",
        "leetspeak",
        "unicode_obfuscation",
        "character_substitution",
        "base64_encode",
        "rot13"
    ]
