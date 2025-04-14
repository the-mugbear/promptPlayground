from datetime import datetime
from extensions import db
from models.model_TestCase import TestCase

def create_test_case(prompt, transformations=None, source=None, attack_type=None, data_type=None, nist_risk=None):
    """
    Create a new TestCase entry in the database.

    Args:
        prompt (str): The prompt for this test case (required).
        transformations (dict or list, optional): The transformations to apply to the prompt.
            Defaults to None.
        source (str, optional): Optional source information for the test case.
            Defaults to None.
        attack_type (str, optional): The attack type (e.g., "jailbreak" or "other").
            Defaults to None.
        data_type (str, optional): The data type (e.g., "text", "image", "audio").
            Defaults to None.
        nist_risk (str, optional): Optional NIST risk level.
            Defaults to None.

    Returns:
        TestCase: The newly created TestCase instance.
    """
    new_case = TestCase(
        prompt=prompt,
        transformations=transformations,
        source=source,
        attack_type=attack_type,
        data_type=data_type,
        nist_risk=nist_risk,
        created_at=datetime.now()  # Optional if the model's default is configured.
    )
    
    db.session.add(new_case)
    db.session.commit()
    
    return new_case

# Example usage:
if __name__ == "__main__":
    # Replace the following values as needed
    prompt_text = "Example prompt for test case creation."
    transformations_data = [{"type": "prepend_text", "value": "Note: "}]
    
    # Create a new test case
    test_case = create_test_case(
        prompt=prompt_text, 
        transformations=transformations_data,
        source="Manual Entry",
        attack_type="jailbreak",
        data_type="text",
        nist_risk="low"
    )
    print(f"Created TestCase: {test_case}")
