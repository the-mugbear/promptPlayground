from flask import Blueprint

test_suites_bp = Blueprint("test_suites_bp", __name__, url_prefix="/test_suites")

from . import core
from . import test_cases
from . import import_export 