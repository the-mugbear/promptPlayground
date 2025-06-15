# routes/chains/__init__.py

from flask import Blueprint

# Blueprint for core chain views (UI)
chains_bp = Blueprint('chains_bp', __name__, url_prefix='/chains')

# Blueprint for chain-related APIs
chains_api_bp = Blueprint('chains_api_bp', __name__)

# Import the routes to register them with the blueprints
from . import views_core
from . import api