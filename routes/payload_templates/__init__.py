from flask import Blueprint

# Define the blueprint for payload template UI routes
payload_templates_bp = Blueprint(
    'payload_templates_bp', 
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/payload_templates'
)

# Import the routes at the end to register them
from . import views