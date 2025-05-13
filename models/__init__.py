# models/__init__.py

from extensions import db

# Import association tables first since they only depend on db
from .associations import test_run_suites, test_run_filters

# Now import all models
from .model_User import User
from .model_Endpoints import Endpoint, APIHeader    # Your table name is 'endpoints' but model is 'Endpoint'
from .model_TestCase import TestCase
from .model_TestSuite import TestSuite
from .model_TestExecution import TestExecution # If this is your attempts/results model
from .model_TestRunAttempt import TestRunAttempt # Or this one
from .model_TestRun import TestRun
from .model_PromptFilter import PromptFilter
from .model_Invitation import Invitation
from .model_Reference import Reference # If you have this
from .model_DatasetReference import DatasetReference # If you have this
from .model_Dialogue import Dialogue # If you have this
from .model_ManualTestRecord import ManualTestRecord # If you have this

# Import association tables if they are defined in models/associations.py
# and if you need to access them directly via the models package.
# Usually, they are just used by the relationships in the main models.
# from .associations import test_run_suites, test_run_filters, etc.

__all__ = [
    'db',
    'User', 'APIHeader', 'Endpoint', 'TestCase', 'TestSuite',
    'TestExecution', 'TestRunAttempt', 'TestRun', 'PromptFilter',
    'Invitation', 'Reference', 'DatasetReference', 'Dialogue', 'ManualTestRecord',
    'test_run_suites', 'test_run_filters'
]