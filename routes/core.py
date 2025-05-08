from flask import Blueprint, render_template, abort, request, redirect, flash, url_for
from flask_login import login_required, current_user
from extensions import db
from models.model_Reference import Reference  # Updated import
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

        # This POST form will be used for adding a new reference.
        name = request.form.get('dataset_name', '').strip()
        url_value = request.form.get('dataset_url', '').strip()
        excerpt = request.form.get('excerpt', '').strip()
        added = request.form.get('dataset_added') == 'on'
        
        if not name or not url_value:
            flash("Both name and URL are required to add a new reference.", "error")
        else:
            new_ref = Reference(
                name=name,
                url=url_value,
                excerpt=excerpt,
                added=added
            )
            db.session.add(new_ref)
            db.session.commit()
            flash("New reference added successfully!", "success")
        return redirect(url_for('core_bp.index'))

    # For GET requests, retrieve a search query if provided.
    search_query = request.args.get('q', '').strip()
    if search_query:
        # Search in name (or URL) using a simple case-insensitive 'like' query.
        dataset_refs = Reference.query.filter(
            Reference.name.ilike(f"%{search_query}%")
        ).order_by(Reference.date_added.desc()).all()
    else:
        dataset_refs = Reference.query.order_by(Reference.date_added.desc()).all()

    # Get user's test runs if logged in
    user_test_runs = []
    if current_user.is_authenticated:
        user_test_runs = TestRun.query.filter_by(user_id=current_user.id).order_by(desc(TestRun.created_at)).limit(5).all()

    # Get recent test suites
    recent_test_suites = TestSuite.query.order_by(desc(TestSuite.created_at)).limit(5).all()

    return render_template('index.html', 
                         dataset_references=dataset_refs, 
                         search_query=search_query,
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

@core_bp.route('/dataset/create', methods=['GET', 'POST'])
@login_required
def create_dataset_reference():
    if request.method == 'POST':
        name = request.form.get('name')
        url_value = request.form.get('url')
        excerpt = request.form.get('excerpt', '').strip()
        # For example, a checkbox or radio to set "added"
        added = request.form.get('added') == 'on'
        if not name or not url_value:
            flash("Both name and URL are required.", "error")
            return redirect(url_for('core_bp.create_dataset_reference'))
        new_ref = Reference(
            name=name,
            url=url_value,
            excerpt=excerpt,
            added=added
        )
        db.session.add(new_ref)
        db.session.commit()
        flash("Reference created successfully.", "success")
        return redirect(url_for('core_bp.index'))
    return render_template('dataset/create.html')
