"""
Endpoints blueprint for managing API endpoints and their configurations.
This module serves as the entry point for all endpoint-related routes.
"""

from flask import Blueprint

endpoints_bp = Blueprint('endpoints_bp', __name__, url_prefix='/endpoints')

# Import all route modules
from . import core
from . import manual_test
from . import headers
from . import testing 