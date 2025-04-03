from flask import Blueprint, render_template

testing_grounds_bp = Blueprint('testing_grounds_bp', __name__, url_prefix='/testing_grounds')

# ********************************
# ROUTES
# ********************************
@testing_grounds_bp.route('/index')
def index():
    return render_template('testing_grounds/index.html')