from flask import Blueprint, render_template, send_from_directory

help_bp = Blueprint('help_bp', __name__, url_prefix='/help')

# ********************************
# ROUTES
# ********************************
@help_bp.route('/index')
def index():
    return render_template('help/index.html')

# Plugin Support
@help_bp.route('/plugin')
def plugin():
    return render_template('help/post_inspector.html')

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
    research_items = [
        {
            "title": "Best-of-N Jailbreaking",
            "url": "https://jplhughes.github.io/bon-jailbreaking/",
            "description": "...a simple black-box algorithm that jailbreaks frontier AI systems across modalities. BoN Jailbreaking works by repeatedly "
            "sampling variations of a prompt with a combination of augmentations - such as random shuffling or capitalization for textual prompts - until "
            "a harmful response is elicited..."
        },
        {
            "title": "API Reference",
            "url": "https://example.com/api",
            "description": "..."
        }
    ]
    return render_template('help/citations.html', research_items=research_items)



# ********************************
# SERVICES
# ********************************
@help_bp.route('/download_extension')
def download_extension():
    return send_from_directory('static', 'POSTInspector.xpi', as_attachment=True)
