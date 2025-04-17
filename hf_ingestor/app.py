import os
import sys
import json

# Ensure parent directory is on sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from datetime import datetime
from flask import Flask
from datasets import load_dataset
from models.model_TestCase import TestCase
from models.model_TestSuite import TestSuite
from models.model_DatasetReference import DatasetReference
from classifier import nist_classify
from extensions import db
from hf_ingestor.services import create_test_case


# Create a minimal Flask app solely to provide an application context
dummy_app = Flask(__name__)
# Assume the instance folder is at the same level as this file's parent directory.
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
db_path = os.path.join(base_dir, "instance", "fuzzy.db")
dummy_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
dummy_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the db on dummy app
db.init_app(dummy_app)

def parse_datasets_and_create_suite(attack_type, dataset_name, prompt_field):
    """
    Loads a dataset from Hugging Face, creates TestCase entries for each prompt,
    and then asks if a TestSuite should be created that associates all these cases.
    
    Args:
        is_jailbreak (bool): If True, treat all prompts as jailbreaks.
        dataset_name (str): Identifier for the dataset in load_dataset.
    """
    # Check if a DatasetReference with this name already exists.
    existing_ref = DatasetReference.query.filter_by(name=dataset_name).first()
    if existing_ref:
        decision = input(f"A DatasetReference for '{dataset_name}' already exists. Process the dataset again? (y/n): ")
        if decision.strip().lower() != 'y':
            print("Dataset processing aborted based on user input.")
            return
        else:
            # Optionally update the reference's date_added.
            existing_ref.date_added = datetime.now()
            db.session.commit()
            print(f"Updating existing DatasetReference (id: {existing_ref.id}).")

    # Load dataset and extract the 'train' split
    ds = load_dataset(dataset_name)

    try:
        prompt_ds = ds['train']
    except:
        print("Failure to access dataset on train")

    try:
        prompt_ds = ds['test']
    except:
        print("Failure to access dataset on test")

    
    if not prompt_ds:
        print("Dataset is empty.")
        return

    # Check the first prompt only once
    first_prompt = prompt_ds[0].get(prompt_field)
    user_input = input("Is the following the correct prompt from the dataset? (y/n)\n" + first_prompt + "\n")
    if user_input.strip().lower() != 'y':
        print("Please adjust your dataset or update the parsing logic.")
        return

    created_test_cases = []
    # Set the suite behavior to be the attack type by default.
    suite_behavior = attack_type

    # Loop through each entry in the dataset
    for entry in prompt_ds:
        prompt = prompt = entry.get(prompt_field)
        if not prompt:
            continue

        if attack_type.lower() == "jailbreak":
            # Create a TestCase for jailbreak entries.
            tc = create_test_case(
                prompt=prompt,
                transformations=None,
                source=dataset_name,
                attack_type=attack_type,
                data_type=None,
                nist_risk=None
            )
            created_test_cases.append(tc)

            suite_behavior = 'jailbreak'
        else:
            # For non-jailbreak cases, perform classification.
            response = nist_classify(prompt)
            try:
                api_data = json.loads(response["response_text"])
            except json.JSONDecodeError as e:
                print("Error parsing response_text:", e)
                api_data = {}
            
            choices = api_data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content")
                print("******")
                print(content)

    # After creating all test cases, ask if a testsuite should be made.
    suite_choice = input("Would you like to create a TestSuite from these test cases? (y/n): ")
    if suite_choice.strip().lower() == 'y':
        suite_description = dataset_name
        new_suite = TestSuite(
            description=suite_description,
            behavior=suite_behavior,
            objective=None,
            created_at=datetime.now()
        )
        # Associate the created test cases with the new TestSuite
        new_suite.test_cases.extend(created_test_cases)
        db.session.add(new_suite)
        db.session.commit()
        print(f"TestSuite created with id: {new_suite.id}")

    # Create a DatasetReference record.
    dataset_url = f"https://huggingface.co/datasets/{dataset_name}"
    # Assuming DatasetReference supports an attack_type field; if not, you may need to update the model.
    dataset_ref = DatasetReference(
        name=dataset_name,
        url=dataset_url,
        added=True,
    )
    db.session.add(dataset_ref)
    db.session.commit()
    print(f"DatasetReference created with id: {dataset_ref.id}")

if __name__ == "__main__":
    with dummy_app.app_context():

        # Dictionary where keys are dataset names and values are tuples with (prompt_field, attack_type)
        datasets = {
            "rubend18/ChatGPT-Jailbreak-Prompts": ("Prompt", "jailbreak"),
            "deadbits/vigil-jailbreak-ada-002": ("text", "jailbreak"),
            "jdineen/human-jailbreaks": ("text", "jailbreak"),
            "Nannanzi/evaluation_jailbreak_safe": ("prompt", "jailbreak"),
            "dvilasuero/jailbreak-classification-gemma": ("prompt", "jailbreak"),
            "usisoftware-org/JailbreakBench": ("prompt", "jailbreak"),
            "jackhhao/jailbreak-classification": ("prompt", "jailbreak"),
            "allenai/tulu-3-trustllm-jailbreaktrigger-eval": ("prompt", "jailbreak"),
            "SpawnedShoyo/ai-jailbreak": ("text", "jailbreak"),
            "GuardrailsAI/detect-jailbreak": ("prompt", "jailbreak"),
            "mrcuddle/Synthetic-JailBreak-RP": ("instruction", "jailbreak"),
            "efgmarquez/jailbreak_dataset": ("statement", "jailbreak"),
            "EthanQzx/ImmuniPrompt-JailbreakDatasets": ("prompt", "jailbreak"),
            "jkazdan/amazing-jailbreak-llama": ("prompt", "jailbreak"),
            "sevdeawesome/jailbreak_success": ("jailbreak_prompt_text", "jailbreak"),
            "BornSaint/harmful_instructor": ("inputs", "harm")
        }

        for dataset_name, (prompt_field, attack_type) in datasets.items():
            parse_datasets_and_create_suite(attack_type, dataset_name, prompt_field)