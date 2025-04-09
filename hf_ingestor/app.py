import os
import sys
import json

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path: sys.path.insert(0, parent_dir)

from datasets import load_dataset
from models.model_TestCase import TestCase
from models.model_TestSuite import TestSuite
from datetime import datetime
from classifier import nist_classify
from extensions import db

# Login using e.g. `huggingface-cli login` to access this dataset
ds = load_dataset("Nannanzi/evaluation_jailbreak_unsafe")
prompt_ds = ds['train']

for entry in prompt_ds:
    response = nist_classify(entry['prompt'])
    # The real API JSON is in response["response_text"]
    try:
        api_data = json.loads(response["response_text"])
    except json.JSONDecodeError as e:
        print("Error parsing response_text:", e)
        api_data = {}

    choices = api_data.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content")
        print('******')
        print(content)


x = 4