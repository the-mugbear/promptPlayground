# routes/chains/__init__.py
from flask import Blueprint

chains_bp = Blueprint(
    'chains_bp', 
    __name__, 
    url_prefix='/chains' # All routes in this blueprint will start with /chains
)

from . import views_core
from . import api