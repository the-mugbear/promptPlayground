# app/endpoints/__init__.py
from flask import Blueprint

# Define the Blueprint
# All routes defined in other files in this package will be registered with this blueprint
endpoints_bp = Blueprint(
    'endpoints_bp',
    __name__,
    url_prefix='/endpoints'
)

# Import routes from other modules in this package to register them
# These imports must be at the bottom to avoid circular dependencies with endpoints_bp
from . import views_core
from . import api
from . import views_testing
from . import views_manual_test