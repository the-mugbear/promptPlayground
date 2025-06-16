# models/__init__.py

from extensions import db

# Import association tables first since they only depend on db
from .associations import test_run_suites, test_run_filters, test_suite_cases

# Now import all models
from .model_User import User
from .model_Endpoints import Endpoint, EndpointHeader 
from .model_TestCase import TestCase
from .model_TestSuite import TestSuite
from .model_TestExecution import TestExecution
from .model_TestRunAttempt import TestRunAttempt 
from .model_TestRun import TestRun
from .model_PromptFilter import PromptFilter
from .model_Invitation import Invitation
from .model_Dialogue import Dialogue 
from .model_ManualTestRecord import ManualTestRecord 
from .model_APIChain import APIChain, APIChainStep
from .model_PayloadTemplate import PayloadTemplate


# Import association tables if they are defined in models/associations.py
# and if you need to access them directly via the models package.
# Usually, they are just used by the relationships in the main models.
# from .associations import test_run_suites, test_run_filters, etc.
__all__ = [
    'db',
    'User', 'EndpointHeader', 'Endpoint', 'TestCase', 'TestSuite',
    'TestExecution', 'TestRunAttempt', 'TestRun', 'PromptFilter',
    'Invitation', 'Dialogue', 'ManualTestRecord',
    'APIChain', 'APIChainStep',
    'test_suite_cases', 'test_run_suites', 'test_run_filters', 'PayloadTemplate'
]