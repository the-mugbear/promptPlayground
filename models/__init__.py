# models/__init__.py
# Added to enforce the order of table creation. The addition of TestRunAttempt was causing issues with TestExecution
from models.model_TestSuite import TestSuite
from models.model_TestCase import TestCase
from models.model_TestRun import TestRun
from models.model_TestRunAttempt import TestRunAttempt  # Import before TestExecution
from models.model_TestExecution import TestExecution
from models.model_Endpoints import Endpoint, APIHeader
