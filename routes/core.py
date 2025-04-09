from flask import Blueprint, render_template, abort, request, redirect, flash, url_for
from extensions import db
from models.model_DatasetReference import DatasetReference  # Import the new model

core_bp = Blueprint('core_bp', __name__)

# ********************************
# ROUTES
# ********************************

@core_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # This POST form will be used for adding a new dataset reference.
        name = request.form.get('dataset_name', '').strip()
        url_value = request.form.get('dataset_url', '').strip()
        added = request.form.get('dataset_added') == 'on'
        
        if not name or not url_value:
            flash("Both name and URL are required to add a new dataset reference.", "error")
        else:
            new_dataset = DatasetReference(name=name, url=url_value, added=added)
            db.session.add(new_dataset)
            db.session.commit()
            flash("New dataset reference added successfully!", "success")
        return redirect(url_for('core_bp.index'))

    # For GET requests, retrieve a search query if provided.
    search_query = request.args.get('q', '').strip()
    if search_query:
        # Search in name (or URL) using a simple case-insensitive 'like' query.
        dataset_refs = DatasetReference.query.filter(
            DatasetReference.name.ilike(f"%{search_query}%")
        ).order_by(DatasetReference.date_added.desc()).all()
    else:
        dataset_refs = DatasetReference.query.order_by(DatasetReference.date_added.desc()).all()

    return render_template('index.html', dataset_references=dataset_refs, search_query=search_query)
    

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
def create_dataset_reference():
    if request.method == 'POST':
        name = request.form.get('name')
        url_value = request.form.get('url')
        # For example, a checkbox or radio to set "added"
        added = request.form.get('added') == 'on'
        if not name or not url_value:
            flash("Both name and URL are required.", "error")
            return redirect(url_for('core_bp.create_dataset_reference'))
        new_ref = DatasetReference(name=name, url=url_value, added=added)
        db.session.add(new_ref)
        db.session.commit()
        flash("Dataset reference created successfully.", "success")
        return redirect(url_for('core_bp.index'))
    return render_template('dataset/create.html')
