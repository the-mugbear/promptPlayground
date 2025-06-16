from flask import Blueprint

test_runs_bp = Blueprint('test_runs_bp', __name__, url_prefix='/test_runs')

# Import all route modules
from . import core
from . import execution
from . import filters
from . import status
from . import api 