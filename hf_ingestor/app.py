import os
import sys
import json
import argparse # Added for potential command-line args
from datetime import datetime, timezone # Added timezone

# Standard Library
import os
import sys
import json
from datetime import datetime, timezone

# Third-Party Libraries
from flask import Flask
from dotenv import load_dotenv
from datasets import load_dataset
from sqlalchemy.exc import SQLAlchemyError # Import for specific DB errors

# Local Application Imports
# Ensure parent directory is on sys.path (keep this logic)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from extensions import db
# Import specific models needed
from models.model_TestSuite import TestSuite 
from models.model_DatasetReference import DatasetReference
from models.model_TestCase import TestCase # Needed if create_test_case returns it or for type hints
from models.model_PromptFilter import PromptFilter
# Import services/classifiers used
from hf_ingestor.services import create_test_case 
from classifier import nist_classify
# ---------------------

# --- Load environment variables ---
load_dotenv()
# --------------------------------

# --- Configuration Function ---
def configure_app_for_db():
    """Creates and configures a minimal Flask app for DB context."""
    app = Flask(__name__)
    
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME')

    if not all([db_user, db_pass, db_name]):
        raise ValueError("Missing required database configuration in environment variables (DB_USER, DB_PASSWORD, DB_NAME).")

    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    return app
# -----------------------------

# --- Helper Functions (Refactored Logic) ---

def load_or_update_reference(dataset_name):
    """Checks for existing DatasetReference, prompts user if found, updates or signals to proceed."""
    existing_ref = DatasetReference.query.filter_by(name=dataset_name).first()
    if existing_ref:
        decision = input(f"A DatasetReference for '{dataset_name}' already exists. Process again? (y/n): ").strip().lower()
        if decision != 'y':
            print("Skipping dataset processing based on user input.")
            return None # Signal to skip
        else:
            try:
                existing_ref.date_added = datetime.now(timezone.utc) # Use UTC consistently
                db.session.commit()
                print(f"Updating existing DatasetReference (id: {existing_ref.id}).")
                return existing_ref # Return existing reference
            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Error updating DatasetReference '{dataset_name}': {e}")
                return None # Signal error/skip
    return "create_new" # Signal to create a new one later

def load_huggingface_split(dataset_name):
    """Loads dataset and tries common splits ('train', 'test')."""
    print(f"Loading dataset '{dataset_name}' from Hugging Face...")
    try:
        ds = load_dataset(dataset_name)
        # Prioritize 'train', then 'test', add others if needed
        if 'train' in ds:
            return ds['train']
        elif 'test' in ds:
            print("Using 'test' split as 'train' split not found.")
            return ds['test']
        else:
             # Attempt to get the first available split if neither train nor test exists
             available_splits = list(ds.keys())
             if available_splits:
                  print(f"Warning: Neither 'train' nor 'test' split found. Using first available split: '{available_splits[0]}'")
                  return ds[available_splits[0]]
             else:
                  print(f"Error: Dataset '{dataset_name}' has no available splits.")
                  return None
                  
    except Exception as e: # Catch specific errors if possible (e.g., DatasetNotFoundError)
        print(f"Error loading dataset '{dataset_name}': {e}")
        return None

def confirm_prompt_field(prompt_ds, prompt_field):
    """Shows the first prompt and asks user for confirmation."""
    if not prompt_ds or len(prompt_ds) == 0:
        print("Dataset split is empty, cannot confirm prompt field.")
        return False
        
    first_prompt = prompt_ds[0].get(prompt_field)
    if first_prompt is None:
         print(f"Error: Prompt field '{prompt_field}' not found in the first dataset entry.")
         # Optionally print available fields: print(prompt_ds[0].keys())
         return False
         
    print(f"\n--- First entry prompt (field: '{prompt_field}') ---")
    print(first_prompt)
    print("----------------------------------------------------")
    user_input = input("Is the above the correct prompt text? (y/n): ").strip().lower()
    return user_input == 'y'

def process_dataset_entry(entry, prompt_field, dataset_name, attack_type):
    """Processes a single entry: gets prompt, classifies, creates TestCase."""
    prompt = entry.get(prompt_field)
    if not prompt:
        return None # Skip entry if prompt field is missing

    test_case_data = {
        "prompt": prompt,
        "transformations": None,
        "source": dataset_name,
        "attack_type": attack_type,
        "data_type": "text", # Assuming text for now
        "nist_risk": None
    }

    if attack_type.lower() != "jailbreak":
        # Only classify non-jailbreak ones for NIST risk (as we will get jailbroken)
        print(f"Classifying prompt (first 50 chars): {prompt[:50]}...")
        try:
            response = nist_classify(prompt) # Assumes this function exists and works
            # Safely parse JSON response
            api_data = {}
            if response and isinstance(response.get("response_text"), str):
                 try:
                      api_data = json.loads(response["response_text"])
                 except json.JSONDecodeError:
                      print(f"Warning: Could not parse JSON response from nist_classify for prompt: {prompt[:50]}...")
            
            choices = api_data.get("choices", [])
            if choices and isinstance(choices, list) and len(choices) > 0:
                 content = choices[0].get("message", {}).get("content")
                 # TODO: Parse 'content' to extract NIST risk if applicable
                 # test_case_data["nist_risk"] = parse_nist_risk(content) 
                 print(f"Classification result: {content}")
            else:
                 print("Warning: No valid classification choice found in response.")
                 
        except Exception as e:
            print(f"Error during classification for prompt '{prompt[:50]}...': {e}")

    # Create TestCase object using the service (assumes it calls db.session.add)
    try:
        # Pass data as kwargs, assumes create_test_case handles them
        tc = create_test_case(**test_case_data) 
        return tc
    except Exception as e:
        print(f"Error creating TestCase for prompt '{prompt[:50]}...': {e}")
        # Potentially rollback if create_test_case does complex things before adding
        # db.session.rollback() 
        return None

def create_suite_interactive(created_test_cases, default_description, default_behavior):
    """Asks user if a suite should be created and saves it."""
    if not created_test_cases:
        print("No test cases were created, skipping suite creation.")
        return

    suite_choice = input(f"\nCreate a TestSuite named '{default_description}' for the {len(created_test_cases)} created test cases? (y/n): ").strip().lower()
    if suite_choice == 'y':
        new_suite = TestSuite(
            description=default_description,
            behavior=default_behavior,
            objective=None, # Add input for this if needed
            created_at=datetime.now(timezone.utc) # Use UTC consistently
        )
        new_suite.test_cases.extend(created_test_cases)
        
        try:
            db.session.add(new_suite)
            # Commit should happen *after* processing the whole dataset
            # db.session.commit() 
            print(f"TestSuite '{new_suite.description}' prepared.")
            return new_suite # Return prepared suite
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Error preparing TestSuite '{new_suite.description}': {e}")
    return None

def create_dataset_reference(dataset_name):
     """Creates the DatasetReference record."""
     dataset_url = f"https://huggingface.co/datasets/{dataset_name}"
     dataset_ref = DatasetReference(
         name=dataset_name,
         url=dataset_url,
         added=True,
         # date_added defaults to utcnow in model
     )
     try:
         db.session.add(dataset_ref)
         # Commit should happen *after* processing the whole dataset
         # db.session.commit() 
         print(f"DatasetReference '{dataset_ref.name}' prepared.")
         return dataset_ref # Return prepared reference
     except SQLAlchemyError as e:
         db.session.rollback()
         print(f"Error preparing DatasetReference '{dataset_ref.name}': {e}")
     return None
     
# --- Main Processing Function ---

def process_single_dataset(attack_type, dataset_name, prompt_field):
    """Handles processing for one dataset, including DB operations."""
    print(f"\n--- Processing Dataset: {dataset_name} ---")

    # 1. Check/Update Reference Record (includes a commit if updated)
    reference_action = load_or_update_reference(dataset_name)
    if reference_action is None: # Indicates skip or error
        return

    # 2. Load Data from Hugging Face
    prompt_ds = load_huggingface_split(dataset_name)
    if not prompt_ds:
        return # Error message already printed

    # 3. Confirm Prompt Field with User
    if not confirm_prompt_field(prompt_ds, prompt_field):
        print("Aborting dataset processing due to incorrect prompt field.")
        return

    # 4. Process Entries and Create Test Cases (calls db.session.add via service)
    created_test_cases = []
    print(f"Processing {len(prompt_ds)} entries...")
    for i, entry in enumerate(prompt_ds):
        # Add progress indicator?
        if (i + 1) % 100 == 0:
             print(f"  Processed {i+1}/{len(prompt_ds)} entries...")
             
        tc = process_dataset_entry(entry, prompt_field, dataset_name, attack_type)
        if tc:
            created_test_cases.append(tc)
    print(f"Finished processing entries. Created {len(created_test_cases)} test cases.")

    # 5. Ask User to Create Suite (calls db.session.add)
    new_suite = create_suite_interactive(created_test_cases, dataset_name, attack_type)

    # 6. Create/Prepare DatasetReference if it didn't exist (calls db.session.add)
    if reference_action == "create_new":
        create_dataset_reference(dataset_name)
        
    # 7. Final Commit for this dataset
    try:
        print(f"Committing changes for dataset '{dataset_name}'...")
        db.session.commit()
        print("Commit successful.")
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Database error during final commit for '{dataset_name}': {e}")
        print("Changes for this dataset have been rolled back.")

# --- Script Execution ---

if __name__ == "__main__":
    # Create app and context once
    app = configure_app_for_db()
    with app.app_context():

        # Define datasets to process (consider moving to JSON/YAML file)
        datasets_to_process = {
            "rubend18/ChatGPT-Jailbreak-Prompts": ("Prompt", "jailbreak"), 
            "deadbits/vigil-jailbreak-ada-002": ("text", "jailbreak"), 
            "jdineen/human-jailbreaks": ("text", "jailbreak"), 
            "Nannanzi/evaluation_jailbreak_safe": ("prompt", "jailbreak"), 
            "dvilasuero/jailbreak-classification-gemma": ("prompt", "jailbreak"), 
            "usisoftware-org/JailbreakBench": ("prompt", "jailbreak"), 
            "jackhhao/jailbreak-classification": ("prompt", "jailbreak"), 
            "allenai/tulu-3-trustllm-jailbreaktrigger-eval": ("prompt", "jailbreak"), 
            "SpawnedShoyo/ai-jailbreak": ("text", "jailbreak"), 
            # "GuardrailsAI/detect-jailbreak": ("prompt", "jailbreak"), 
            "mrcuddle/Synthetic-JailBreak-RP": ("instruction", "jailbreak"), 
            # "efgmarquez/jailbreak_dataset": ("statement", "jailbreak"), 
            "EthanQzx/ImmuniPrompt-JailbreakDatasets": ("prompt", "jailbreak"), 
            "jkazdan/amazing-jailbreak-llama": ("prompt", "jailbreak"), 
            "sevdeawesome/jailbreak_success": ("jailbreak_prompt_text", "jailbreak"), 
            "BornSaint/harmful_instructor": ("inputs", "harm"), 
            "r1char9/prompt-2-prompt-injection": ("prompt_injection", "prompt_injection"),
            "Arthur-AI/arthur_prompt_injection_benchmark": ("text", "prompt_injection"),
            "hackaprompt/hackaprompt-dataset": ("prompt", "jailbreak")
        }

        # Loop through datasets and process each one
        for name, (field, att_type) in datasets_to_process.items():
            process_single_dataset(att_type, name, field)

        print("\n--- Ingestion Script Finished ---")