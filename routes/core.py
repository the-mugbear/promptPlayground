from flask import Blueprint, render_template, abort, request, redirect, flash, url_for
from flask_login import current_user
from extensions import db

from models.model_TestRun import TestRun
from models.model_TestSuite import TestSuite
from sqlalchemy import desc

core_bp = Blueprint('core_bp', __name__)

# ********************************
# ROUTES
# ********************************
@core_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':

        # --- PROTECT POST REQUEST ---
        if not current_user.is_authenticated: # Manual check as decorator applies to whole function
             flash('You must be logged in to add references.', 'warning')
             return redirect(url_for('auth_bp.login', next=request.url))
        # --- END PROTECTION ---


    # Get user's test runs if logged in
    user_test_runs = []
    if current_user.is_authenticated:
        user_test_runs = TestRun.query.filter_by(user_id=current_user.id).order_by(desc(TestRun.created_at)).limit(5).all()

    # Get recent test suites
    recent_test_suites = TestSuite.query.order_by(desc(TestSuite.created_at)).limit(5).all()

    return render_template('index.html', 
                         user_test_runs=user_test_runs,
                         recent_test_suites=recent_test_suites)    

# ********************************
# SERVICES
# ********************************
@core_bp.route('/visual/<effect>')
def visual(effect):
    # List of available visual effects
    valid_effects = ['matrix_rain', 'neon_grid_glitch', 'neon_circles', '8_bit_fire']
    if effect not in valid_effects:
        abort(404)
    # Render the corresponding template, e.g., matrix_rain.html
    return render_template(f"testing_grounds/{effect}.html")