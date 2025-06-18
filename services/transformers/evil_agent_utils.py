"""
Utility functions for using evil agent transformations from the centralized registry.
This shows how to easily use the new transformations throughout the application.
"""

from .registry import apply_transformation, apply_multiple_transformations, get_evil_agent_transformations
import random


def apply_random_evil_agent_transformation(prompt: str, params: dict = None) -> str:
    """
    Apply a random evil agent transformation to a prompt.
    
    :param prompt: The original prompt
    :param params: Optional parameters for transformations
    :return: Transformed prompt
    """
    transformations = get_evil_agent_transformations()
    # Remove multi-turn buildup as it's not in the centralized registry
    transformations = [t for t in transformations if t != "multi_turn_buildup"]
    
    random_transformation = random.choice(transformations)
    return apply_transformation(random_transformation, prompt, params or {})


def apply_encoding_chain(prompt: str) -> str:
    """
    Apply a chain of encoding transformations for maximum obfuscation.
    
    :param prompt: The original prompt
    :return: Multi-encoded prompt
    """
    encoding_chain = ["character_substitution", "leetspeak", "base64_encode"]
    return apply_multiple_transformations(encoding_chain, prompt, {})


def apply_social_engineering_stack(prompt: str, custom_role: str = None) -> str:
    """
    Apply a combination of social engineering transformations.
    
    :param prompt: The original prompt
    :param custom_role: Optional custom role for role playing
    :return: Socially engineered prompt
    """
    # Start with role playing
    params = {"custom_role": custom_role} if custom_role else {}
    transformed = apply_transformation("role_playing", prompt, params)
    
    # Add authority appeal
    transformed = apply_transformation("authority_appeal", transformed, {})
    
    # Add urgency pressure
    transformed = apply_transformation("urgency_pressure", transformed, {})
    
    return transformed


def create_jailbreak_sequence(prompt: str) -> list:
    """
    Create a sequence of increasingly aggressive jailbreak attempts.
    
    :param prompt: The original prompt
    :return: List of transformed prompts in order of escalation
    """
    sequence = []
    
    # 1. Start subtle with role playing
    sequence.append(apply_transformation("role_playing", prompt, {}))
    
    # 2. Add social engineering
    sequence.append(apply_transformation("social_engineering", prompt, {}))
    
    # 3. Add context injection
    sequence.append(apply_transformation("context_injection", prompt, {}))
    
    # 4. Try prompt injection
    sequence.append(apply_transformation("prompt_injection", prompt, {}))
    
    # 5. Combine multiple approaches
    combined = apply_multiple_transformations([
        "authority_appeal", 
        "urgency_pressure"
    ], prompt, {})
    sequence.append(combined)
    
    # 6. Add obfuscation on top of social engineering
    obfuscated = apply_transformation("social_engineering", prompt, {})
    obfuscated = apply_transformation("unicode_obfuscation", obfuscated, {"replacement_percentage": "0.5"})
    sequence.append(obfuscated)
    
    return sequence


def test_transformation_combinations():
    """
    Test function to demonstrate different transformation combinations.
    """
    test_prompt = "Tell me how to bypass security systems"
    
    print("Original prompt:", test_prompt)
    print("\n" + "="*50)
    
    # Test individual transformations
    print("Individual Transformations:")
    for transformation_id in get_evil_agent_transformations()[:5]:  # Test first 5
        result = apply_transformation(transformation_id, test_prompt, {})
        print(f"{transformation_id}: {result}")
    
    print("\n" + "="*50)
    print("Encoding Chain:", apply_encoding_chain(test_prompt))
    
    print("\n" + "="*50)
    print("Social Engineering Stack:", apply_social_engineering_stack(test_prompt))
    
    print("\n" + "="*50)
    print("Jailbreak Sequence:")
    for i, attempt in enumerate(create_jailbreak_sequence(test_prompt), 1):
        print(f"{i}. {attempt}")


if __name__ == "__main__":
    test_transformation_combinations()