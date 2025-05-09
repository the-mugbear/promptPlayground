"""
This module contains Celery tasks for importing datasets from Hugging Face and creating test suites.
The main task is invoked from routes/test_suites.py when a user selects datasets to import.

Task Flow:
1. User selects datasets to import from the web interface
2. import_dataset_task is invoked for each selected dataset
3. Task processes the dataset and creates test suites with associated test cases
4. Results are stored in the database

Key Functions:
- import_dataset_task: Main Celery task that orchestrates the import process
- _load_or_update_reference_in_task: Manages dataset reference records
- _load_huggingface_split_in_task: Loads data from Hugging Face
- _process_dataset_entry_in_task: Processes individual dataset entries into test cases
- _create_suite_in_task: Creates test suites from processed test cases
- _create_dataset_reference_in_task: Creates new dataset reference records
"""

import datetime
from datetime import timezone
import json
import os

from extensions import db
from models.model_TestSuite import TestSuite
from models.model_TestCase import TestCase
from models.model_DatasetReference import DatasetReference

from sqlalchemy.exc import SQLAlchemyError, InternalError
from celery_app import celery 
from datasets import load_dataset
from datasets.exceptions import DatasetNotFoundError 
from huggingface_hub import HfApi, HfFolder # For token usage


# Attempt to import services - handle gracefully if they don't exist in worker context initially
try:
    from hf_ingestor.services import create_test_case
    from hf_ingestor.classifier import nist_classify
except ImportError as e:
    print(f"WARN: Could not import services in celery_tasks: {e}. Define dummy functions.")
    # Define dummy functions if needed for testing, or ensure modules are importable
    def create_test_case(**kwargs): print("WARN: Using dummy create_test_case"); return None
    def nist_classify(prompt): print("WARN: Using dummy nist_classify"); return {"response_text": "{}"}

# --- Helper Functions (Adapted from app.py) ---
# Note: These run within the Celery task's app context provided by ContextTask
def _load_or_update_reference_in_task(dataset_name):
    """
    Checks if a dataset reference exists and updates it if found.
    Called by import_dataset_task to manage dataset reference records.
    
    Args:
        dataset_name (str): Name of the dataset to check/update
        
    Returns:
        DatasetReference or str: Existing reference if found, "create_new" if new needed
    """
    try:
        # Ensure we start with a clean transaction
        db.session.rollback()
        
        existing_ref = DatasetReference.query.filter_by(name=dataset_name).first()
        if existing_ref:
            # In a background task, we probably don't want interactive input.
            # Decide on a policy: either always skip if exists, or always update.
            # Let's choose to update the timestamp if found.
            try:
                existing_ref.date_added = datetime.datetime.now(timezone.utc)
                # Commit happens later, just stage the change
                print(f"Task: Found existing DatasetReference for '{dataset_name}'. Updating timestamp.")
                return existing_ref # Return existing reference
            except SQLAlchemyError as e:
                db.session.rollback() # Rollback this specific potential change
                print(f"Task Error: Error staging update for DatasetReference '{dataset_name}': {e}")
                return None # Signal error/skip
        return "create_new" # Signal to create a new one later
    except Exception as e:
        db.session.rollback()
        print(f"Task Error: Unexpected error in _load_or_update_reference_in_task: {e}")
        return None

def _load_huggingface_split_in_task(dataset_name, hf_token=None):
    """
    Loads a dataset split from Hugging Face.
    Called by import_dataset_task to fetch the actual dataset data.
    
    Args:
        dataset_name (str): Name of the dataset to load
        hf_token (str, optional): Hugging Face API token for private datasets
        
    Returns:
        Dataset: The loaded dataset split
    """
    print(f"Task: Loading dataset '{dataset_name}'...")
    try:
        # Use the token when loading the dataset
        ds = load_dataset(dataset_name, token=hf_token) # Pass the token here
        if 'train' in ds:
            return ds['train']
        elif 'test' in ds:
            print("Task: Using 'test' split for '{dataset_name}'.")
            return ds['test']
        else:
            available_splits = list(ds.keys())
            if available_splits:
                print(f"Task Warning: Using first split '{available_splits[0]}' for '{dataset_name}'.")
                return ds[available_splits[0]]
            else:
                print(f"Task Error: Dataset '{dataset_name}' has no splits.")
                return None
    except DatasetNotFoundError:
        print(f"Task Error: Dataset '{dataset_name}' not found on Hugging Face Hub.")
        return None
    except Exception as e:
        # Catch auth errors specifically if needed? Requires checking huggingface_hub exceptions
        print(f"Task Error: Error loading dataset '{dataset_name}': {e}")
        return None

def _process_dataset_entry_in_task(entry, prompt_field, dataset_name, attack_type):
    """
    Processes a single dataset entry into a test case.
    Called by import_dataset_task for each entry in the dataset.
    
    Args:
        entry (dict): Dataset entry containing the prompt
        prompt_field (str): Field name containing the prompt text
        dataset_name (str): Name of the source dataset
        attack_type (str): Type of attack to associate with the test case
        
    Returns:
        TestCase: Created test case object
    """
    prompt = entry.get(prompt_field)
    if not prompt:
        return None

    test_case_data = {
        "prompt": prompt, "transformations": None, "source": dataset_name,
        "attack_type": attack_type, "data_type": "text", "nist_risk": None
    }

    if attack_type.lower() != "jailbreak":
        # print(f"Task: Classifying prompt (first 50 chars): {prompt[:50]}...") # Reduce verbosity?
        try:
            response = nist_classify(prompt)
            api_data = {}
            if response and isinstance(response.get("response_text"), str):
                 try: api_data = json.loads(response["response_text"])
                 except json.JSONDecodeError: pass # Ignore parsing errors silently? Or log warning.
            choices = api_data.get("choices", [])
            # ... (rest of classification logic - simplified) ...
            # print(f"Task: Classification result obtained.")
        except Exception as e:
            print(f"Task Warning: Classification failed for prompt prefix '{prompt[:50]}...': {e}")

    try:
        tc = create_test_case(**test_case_data) # Assumes this stages the add (db.session.add)
        return tc
    except Exception as e:
        print(f"Task Error: Failed creating TestCase for prompt prefix '{prompt[:50]}...': {e}")
        return None

def _create_suite_in_task(created_test_cases, dataset_name, attack_type, user_id=None):
    """
    Creates a test suite from processed test cases.
    Called by import_dataset_task after processing all dataset entries.
    
    Args:
        created_test_cases (list): List of TestCase objects
        dataset_name (str): Name of the source dataset
        attack_type (str): Type of attack for the suite
        user_id (int, optional): ID of the user creating the suite
        
    Returns:
        TestSuite: Created test suite object
    """
    if not created_test_cases:
        return None

    # Non-interactive: always create the suite if cases exist
    new_suite = TestSuite(
        description=f"{dataset_name} (Imported)", # Make description clearer
        behavior=attack_type,
        objective=f"Test cases imported from Hugging Face dataset '{dataset_name}'",
        created_at=datetime.datetime.now(timezone.utc),
        user_id=user_id  # Add the user ID
    )
    new_suite.test_cases.extend(created_test_cases)
    try:
        db.session.add(new_suite)
        print(f"Task: TestSuite '{new_suite.description}' prepared for commit.")
        return new_suite
    except SQLAlchemyError as e:
        # Don't rollback yet, main task handler will do it
        print(f"Task Error: Failed preparing TestSuite '{new_suite.description}': {e}")
        raise # Re-raise to signal failure to the main task handler

def _create_dataset_reference_in_task(dataset_name):
    """
    Creates a new dataset reference record.
    Called by import_dataset_task when a new dataset is being imported.
    
    Args:
        dataset_name (str): Name of the dataset to create reference for
        
    Returns:
        DatasetReference: Created reference object
    """
    try:
        dataset_url = f"https://huggingface.co/datasets/{dataset_name}"
        dataset_ref = DatasetReference(
            name=dataset_name, url=dataset_url, added=True
        )
        db.session.add(dataset_ref)
        print(f"Task: DatasetReference '{dataset_ref.name}' prepared for commit.")
        return dataset_ref
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Task Error: Error preparing DatasetReference '{dataset_ref.name}': {e}")
        raise # Re-raise to signal failure
    except Exception as e:
        db.session.rollback()
        print(f"Task Error: Unexpected error in _create_dataset_reference_in_task: {e}")
        raise


# --- The Main Celery Task ---
@celery.task(bind=True)
def import_dataset_task(self, dataset_name, prompt_field, attack_type, hf_token=None, user_id=None):
    """
    Main Celery task for importing a dataset from Hugging Face.
    
    This task is invoked from routes/test_suites.py when a user selects datasets to import.
    The task orchestrates the entire import process:
    1. Checks/updates dataset reference
    2. Loads data from Hugging Face
    3. Processes entries into test cases
    4. Creates test suites
    5. Manages database transactions
    
    Args:
        self: Celery task instance (used for retries if needed)
        dataset_name (str): Name of the dataset to import
        prompt_field (str): Field name containing the prompt text
        attack_type (str): Type of attack to associate with test cases
        hf_token (str, optional): Hugging Face API token for private datasets
        user_id (int, optional): ID of the user importing the dataset
        
    Returns:
        bool: True if import succeeded, False if failed
    """
    print(f"--- Task started: Importing {dataset_name} ---")
    task_failed = False
    try:
        # 1. Check/Stage Reference Record Update/Creation
        reference_action = _load_or_update_reference_in_task(dataset_name)
        if reference_action is None: # Indicates error during check/update staging
            raise Exception(f"Failed to process DatasetReference for {dataset_name}")

        # 2. Load Data from Hugging Face (using token)
        prompt_ds = _load_huggingface_split_in_task(dataset_name, hf_token)
        if not prompt_ds:
            raise Exception(f"Failed to load dataset {dataset_name} from Hugging Face.")

        # 3. Process Entries (stage TestCases)
        created_test_cases = []
        total_entries = len(prompt_ds)
        print(f"Task: Processing {total_entries} entries for {dataset_name}...")
        for i, entry in enumerate(prompt_ds):
            if (i + 1) % 250 == 0: # Log progress less often in background task
                 print(f"  Task {dataset_name}: Processed {i+1}/{total_entries}...")
            tc = _process_dataset_entry_in_task(entry, prompt_field, dataset_name, attack_type)
            if tc:
                created_test_cases.append(tc)
        print(f"Task: Finished processing entries for {dataset_name}. Prepared {len(created_test_cases)} test cases.")

        # 4. Stage Suite Creation
        _create_suite_in_task(created_test_cases, dataset_name, attack_type, user_id) # Pass user_id

        # 5. Stage DatasetReference Creation if needed
        if reference_action == "create_new":
            _create_dataset_reference_in_task(dataset_name) # Raises exception on error

        # 6. Final Commit for THIS task/dataset
        print(f"Task: Attempting final commit for dataset '{dataset_name}'...")
        db.session.commit()
        print(f"Task: Commit successful for {dataset_name}.")

    except Exception as e:
        task_failed = True
        # Log the exception traceback for detailed debugging
        import traceback
        print(f"!!! TASK FAILED: Importing {dataset_name} !!!")
        print(f"Error: {e}")
        print(traceback.format_exc()) # Print full traceback to Celery logs
        db.session.rollback() # Rollback any changes made during this failed task
        print(f"Task: Rolled back changes for {dataset_name}.")
        # Optional: Update task state to FAILURE for tracking
        # self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        # raise # Re-raising might trigger Celery's retry logic if configured

    finally:
        print(f"--- Task finished: Importing {dataset_name} {'(FAILED)' if task_failed else '(Success)'} ---")

    # Return value is optional, could return success/fail status or number of items processed
    return not task_failed