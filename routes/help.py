from flask import Blueprint, render_template

help_bp = Blueprint('help_bp', __name__, url_prefix='/help')

# ********************************
# ROUTES
# ********************************
@help_bp.route('/index')
def index():
    return render_template('help/index.html')

# Learn the steps to configure and execute a test run.
@help_bp.route('/create_test_run')
def create_test_run():
    return render_template('help/create_test_run.html')

# Instructions on creating, testing, and deleting endpoints.
@help_bp.route('/manage_endpoints')
def manage_endpoints():
    return render_template('help/manage_endpoints.html')

# Guide on adding new transformations and registering them for use in suite creation
@help_bp.route('/using_transformations')
def using_transformations():
    return render_template('help/using_transformations.html')

# Guide on adding new transformations and registering them for use in suite creation
@help_bp.route('/adding_transformers')
def adding_transformers():
    return render_template('help/adding_transformers.html')

# Understand the execution status, response codes, and more.
@help_bp.route('/results')
def results():
    return render_template('help/results.html')

# Citations / Resource Links
@help_bp.route('/citations')
def citations():
    return render_template('help/citations.html')
