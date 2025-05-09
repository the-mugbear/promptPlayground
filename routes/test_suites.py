import json
import yaml
import os

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from extensions import db
from models.model_TestCase import TestCase
from models.model_TestSuite import TestSuite
from celery_app import celery
from services.transformers.registry import apply_transformations_to_lines, TRANSFORM_PARAM_CONFIG, apply_transformation
from services.transformers.helpers import process_transformations
from models.associations import test_suite_cases
from datetime import datetime

test_suites_bp = Blueprint("test_suites_bp", __name__, url_prefix="/test_suites")

# ********************************
# ROUTES
# ********************************
@test_suites_bp.route('/list', methods=['GET'])
def list_test_suites():
    """
    GET /test_suites/list -> Display a page with all existing test suites
    """
    # Query the DB for all test suites
    test_suites = TestSuite.query.all()
    return render_template('test_suites/list_test_suites.html', test_suites=test_suites)

#  three.js experiment
@test_suites_bp.route('/list3', methods=['GET'])
def list_three():
    """
    GET /test_suites/list -> Display a page with all existing test suites
    """
    # Query the DB for all test suites
    test_suites = TestSuite.query.all()
    return render_template('test_suites/list_test_suites_three.html', test_suites=test_suites)

@test_suites_bp.route('/create', methods=['GET'])
@login_required 
def create_test_suite_form():
    """
    GET /test_suites/create -> Display an HTML form to create a new test suite
    """
    # If you want to display existing test cases to add to the new suite, fetch them:
    # orphaned_test_cases = TestCase.query.filter(~TestCase.test_suites.any()).all()
    # existing_test_cases = TestCase.query.all()
    existing_test_suites = TestSuite.query.all()

    return render_template(
        'test_suites/create_suite.html', 
        # existing_test_cases=existing_test_cases, 
        existing_suites=existing_test_suites,
        # orphaned_test_cases=orphaned_test_cases
    )

@test_suites_bp.route('/<int:suite_id>/details', methods=["GET"])
@login_required 
def test_suite_details(suite_id):
    # Retrieve the test suite by its ID, or return a 404 error if not found.
    test_suite = TestSuite.query.get_or_404(suite_id)
    
    # For each test case in the suite, apply its transformations to the prompt.
    for test_case in test_suite.test_cases:
        # Start with the original prompt.
        transformed_prompt = test_case.prompt  
        for tinfo in (test_case.transformations or []):
            t_type = tinfo.get("type")
            params = {}
            if "value" in tinfo:
                params["value"] = tinfo["value"]
            transformed_prompt = apply_transformation(t_type, transformed_prompt, params)
        # Attach the transformed prompt to the test case.
        test_case.transformed_prompt = transformed_prompt

    return render_template('test_suites/test_suite_details.html', test_suite=test_suite)

# ********************************
# SERVICES
# ********************************
@test_suites_bp.route('/create', methods=['POST'])
@login_required 
def create_test_suite():
    """
    POST /test_suites/create -> Handle the form submission to create a new test suite.
    """
    description = request.form.get('description')
    behavior = request.form.get('behavior')
    objective = request.form.get('objective')

    # Process suite-level transformations (default for test cases that inherit)
    suite_transformations = process_transformations(request.form)

    # Create the test suite.
    new_suite = TestSuite(
        description=description,
        behavior=behavior,
        objective=objective,
        user_id=current_user.id
    )
    db.session.add(new_suite)
    db.session.commit()

    # 1. Process dynamic new test cases from test_cases_data (JSON string)
    test_cases_json = request.form.get('test_cases_data')
    if test_cases_json:
        try:
            test_cases_list = json.loads(test_cases_json)
        except Exception as e:
            flash(f"Error parsing test cases data: {str(e)}", "error")
            test_cases_list = []
        for tc_data in test_cases_list:
            prompt = tc_data.get("prompt", "").strip()
            if not prompt:
                continue  # Skip empty test cases.
            # Decide which transformations to use:
            # If the test case is flagged to inherit suite-level transformations, use the suite defaults.
            # Otherwise, use the custom transformations provided in the test case.
            inherit = tc_data.get("inheritSuiteTransformations", True)
            if inherit:
                transformations = suite_transformations
            else:
                transformations = tc_data.get("transformations", [])
            test_case = TestCase(prompt=prompt, transformations=transformations)
            db.session.add(test_case)
            db.session.flush()  # Ensure test_case.id is assigned.
            new_suite.test_cases.append(test_case)
        db.session.commit()
    else:
        # Fallback: if no dynamic test cases data was provided, process from the plain text import field.
        new_test_cases_data = request.form.get('new_test_cases')
        if new_test_cases_data:
            lines = [line.strip() for line in new_test_cases_data.split('\n') if line.strip()]
            for line in lines:
                # By default, assign suite-level transformations.
                test_case = TestCase(prompt=line, transformations=suite_transformations)
                db.session.add(test_case)
                db.session.flush()
                new_suite.test_cases.append(test_case)
            db.session.commit()

    # 2. Associate existing test cases (if any)
    selected_test_case_ids = request.form.getlist('selected_test_cases')
    for tc_id in selected_test_case_ids:
        existing_tc = TestCase.query.get(tc_id)
        if existing_tc:
            # If the existing test case doesn't already have transformations, assign suite-level ones.
            if not existing_tc.transformations:
                existing_tc.transformations = suite_transformations
            new_suite.test_cases.append(existing_tc)
    db.session.commit()

    flash('New test suite created successfully!', 'success')
    return redirect(url_for('test_suites_bp.list_test_suites'))



# If the suite has already been used in a test run we block deletion, we could cascade and backfill entries but not today
@test_suites_bp.route("/<int:suite_id>/delete", methods=["POST"])
@login_required 
def delete_test_suite(suite_id):
    """
    POST /test_suites/<suite_id>/delete -> Deletes a test suite if allowed.
    """
    suite_to_delete = TestSuite.query.get_or_404(suite_id)

    # Option A) If you want to block deletion if it's used in a run:
    if suite_to_delete.test_runs:
        flash("Cannot delete this suite because it's used by one or more test runs.", "error")
        return redirect(url_for('test_suites_bp.list_test_suites'))

    # Find potentially orphaned test cases BEFORE deleting the suite's associations
    potential_orphans = list(suite_to_delete.test_cases) 

    # 
    try:
        # Delete the suite (this removes entries from test_suite_cases)
        db.session.delete(suite_to_delete)
        db.session.commit() # Commit the suite deletion
        flash(f"Test Suite #{suite_id} deleted.", "success")
        
        # Now check potential orphans
        deleted_orphan_count = 0
        for case in potential_orphans:
            # Refresh the case or query its associations count
            # Using count() might be efficient
            # Now test_suite_cases should be recognized
            assoc_count = db.session.query(test_suite_cases).filter_by(test_case_id=case.id).count() 
            if assoc_count == 0:
                print(f"Deleting orphaned TestCase {case.id} after deleting suite {suite_id}")
                db.session.delete(case)
                deleted_orphan_count += 1
        
        # Commit the deletion of orphaned cases (if any)
        if deleted_orphan_count > 0:
            db.session.commit() 
            flash(f"Removed {deleted_orphan_count} orphaned test case(s).", "info")

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting Test Suite #{suite_id}: {str(e)}", "error")

    # Redirect back to your list of suites
    return redirect(url_for('test_suites_bp.list_test_suites'))

# Used to make AJAX calls for demo purposes on create_suite.html
@test_suites_bp.route('/preview_transform', methods=['POST'])
def preview_transform():
    """
    Expects JSON like:
    {
      "lines": ["Test case #1", "Test case #2"],
      "transformations": ["base64_encode", "prepend_text"],
      "params": {
        "prepend_text_value": "...",
        "postpend_text_value": "..."
      }
    }
    Returns JSON with {"transformed_lines": [...]}.
    """
    data = request.get_json() or {}
    lines = data.get('lines', [])
    selected_transforms = data.get('transformations', [])
    params = data.get('params', {})

    # Call the new function
    transformed_lines = apply_transformations_to_lines(
        t_ids=selected_transforms,
        lines=lines,
        all_params=params
    )

    return jsonify({"transformed_lines": transformed_lines})

@test_suites_bp.route('/<int:suite_id>/update', methods=['PUT'])
@login_required 
def update_test_suite(suite_id):
    suite = TestSuite.query.get_or_404(suite_id)
    data = request.get_json(force=True)
    updated_fields = []

    if "description" in data:
        suite.description = data["description"]
        updated_fields.append("description")

    if "behavior" in data:
        suite.behavior = data["behavior"]
        updated_fields.append("behavior")

    if "objective" in data:
        suite.objective = data["objective"]
        updated_fields.append("objective")

    db.session.commit()
    return jsonify({"message": "Updated fields: " + ", ".join(updated_fields)}), 200

@test_suites_bp.route('/<int:suite_id>/remove_test_case/<int:case_id>', methods=['POST'])
@login_required 
def remove_test_case_from_suite(suite_id, case_id):
    from models.model_TestCase import TestCase  # Ensure import if not already present
    from models.model_TestSuite import TestSuite
    suite = TestSuite.query.get_or_404(suite_id)
    case = TestCase.query.get_or_404(case_id)
    if case in suite.test_cases:
        suite.test_cases.remove(case)
        db.session.commit()
        return jsonify({"message": "Test case removed from suite."}), 200
    else:
        return jsonify({"message": "Test case was not associated with this suite."}), 404

# let users create new test cases and add them to a test suite when viewing the details of said suite
@test_suites_bp.route('/<int:suite_id>/add_test_case', methods=['POST'])
@login_required 
def add_test_case_to_suite(suite_id):
    data = request.get_json(force=True) or {}
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({"success": False, "error": "Prompt cannot be empty"}), 400

    # Fetch suite
    suite = TestSuite.query.get_or_404(suite_id)

    # Decide on transformations (here: inherit suite's defaults)
    transformations = suite_transformations = suite_transformations = suite_transformations = process_transformations(request.form) if False else (suite_transformations := [])

    # Create & associate
    new_tc = TestCase(prompt=prompt, transformations=transformations)
    db.session.add(new_tc)
    suite.test_cases.append(new_tc)
    db.session.commit()

    return jsonify({
      "success": True,
      "case": {
        "id": new_tc.id,
        "prompt": new_tc.prompt,
        "created_at": new_tc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        "source": new_tc.source or "",
        "attack_type": new_tc.attack_type or "",
        "data_type": new_tc.data_type or "",
        "nist_risk": new_tc.nist_risk or "",
        "reviewed": new_tc.reviewed,
        "transformations": new_tc.transformations or []
      }
    })


# Helper function to load datasets from YAML (same as discussed before)
def load_available_datasets():
    config_path = os.path.join(current_app.instance_path, 'importable_datasets.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            datasets_list = yaml.safe_load(f)
            # Convert list to dict for easier lookup by name
            return {ds['name']: ds for ds in datasets_list if ds and 'name' in ds}
    except FileNotFoundError:
        current_app.logger.error(f"Dataset config file not found: {config_path}")
        return {}
    except yaml.YAMLError as e:
        current_app.logger.error(f"Error parsing dataset config {config_path}: {e}")
        return {}
    except Exception as e:
         current_app.logger.error(f"Unexpected error loading dataset config {config_path}: {e}")
         return {}

@test_suites_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_hf_datasets():
    # Load dataset configuration ONCE at the start of the request
    available_datasets_dict = load_available_datasets()

    if request.method == 'POST':
        selected_names = request.form.getlist('selected_datasets')
        hf_token = request.form.get('hf_token', None)
        if not hf_token: hf_token = None # Ensure empty string becomes None

        tasks_started_count = 0
        tasks_failed_to_start_count = 0

        if not selected_names:
            flash("Please select at least one dataset to import.", "warning")
        else:
            current_app.logger.info(f"Received request to import datasets: {selected_names}")
            for name in selected_names:
                # Use the loaded dictionary
                dataset_details = available_datasets_dict.get(name)

                # --- IMPROVEMENT: Validate details ---
                if not dataset_details:
                    flash(f"Configuration details not found for dataset: '{name}'. Skipping.", "warning")
                    current_app.logger.warning(f"Attempted import for '{name}' but details not found in config.")
                    tasks_failed_to_start_count += 1
                    continue # Skip to the next selected dataset

                prompt_field = dataset_details.get('prompt_field')
                attack_type = dataset_details.get('attack_type')

                if not prompt_field or not attack_type:
                    flash(f"Configuration incomplete (missing prompt_field or attack_type) for dataset: '{name}'. Skipping.", "error")
                    current_app.logger.error(f"Missing prompt_field or attack_type for {name} in config.")
                    tasks_failed_to_start_count += 1
                    continue # Skip to the next selected dataset
                # --- End Validation ---

                try:
                    # Ensure task name matches your structure (workers or tasks) and celery_app.py include
                    task_name = 'workers.import_tasks.import_dataset_task'
                    celery.send_task(task_name, args=[name, prompt_field, attack_type, hf_token, current_user.id])
                    current_app.logger.info(f"Dispatched Celery task '{task_name}' for dataset '{name}'")
                    tasks_started_count += 1
                except Exception as e:
                    # Catch potential errors during task dispatch itself
                    current_app.logger.error(f"Failed to dispatch Celery task for dataset '{name}': {e}", exc_info=True)
                    flash(f"Error starting import task for dataset: '{name}'. Check logs.", "danger")
                    tasks_failed_to_start_count += 1

            # Flash summary message
            if tasks_started_count > 0:
                flash(f"Successfully started import tasks for {tasks_started_count} dataset(s). Check Celery worker logs for progress.", "success")
            if tasks_failed_to_start_count > 0:
                 flash(f"Failed to start import tasks for {tasks_failed_to_start_count} dataset(s) due to configuration issues.", "warning")


        return redirect(url_for('test_suites_bp.import_hf_datasets')) # Redirect back to the import page

    # GET request: Pass the loaded dictionary to the template
    return render_template('test_suites/import_datasets.html',
                           available_datasets=available_datasets_dict)

@test_suites_bp.route('/<int:suite_id>/export', methods=['GET'])
@login_required
def export_test_suite(suite_id):
    """Export a test suite to a JSON file."""
    suite = TestSuite.query.get_or_404(suite_id)
    
    # Create export data
    export_data = {
        'version': '1.0',
        'test_suite': {
            'description': suite.description,
            'behavior': suite.behavior,
            'objective': suite.objective,
            'test_cases': []
        }
    }
    
    # Add test cases
    for tc in suite.test_cases:
        case_data = {
            'prompt': tc.prompt,
            'transformations': tc.transformations,
            'source': tc.source,
            'attack_type': tc.attack_type,
            'data_type': tc.data_type,
            'nist_risk': tc.nist_risk,
            'reviewed': tc.reviewed
        }
        export_data['test_suite']['test_cases'].append(case_data)
    
    # Create response with JSON file
    response = jsonify(export_data)
    response.headers['Content-Disposition'] = f'attachment; filename=test_suite_{suite_id}.json'
    return response

@test_suites_bp.route('/import_suite', methods=['POST'])
@login_required
def import_test_suite():
    """Import test suite(s) from a JSON file."""
    try:
        # Handle both JSON and form data
        if request.is_json:
            import_data = request.get_json()
        else:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            try:
                import_data = json.loads(file.read())
            except json.JSONDecodeError:
                return jsonify({'error': 'Invalid JSON file'}), 400
        
        # Validate version
        if import_data.get('version') != '1.0':
            return jsonify({'error': 'Unsupported file version'}), 400
        
        # Check if this is a bulk export file (contains multiple suites)
        if 'test_suites' in import_data:
            # First, check for duplicates
            duplicates = []
            for suite_data in import_data['test_suites']:
                existing_suite = TestSuite.query.filter_by(
                    description=suite_data['description'],
                    behavior=suite_data.get('behavior')
                ).first()
                
                if existing_suite:
                    duplicates.append({
                        'description': suite_data['description'],
                        'behavior': suite_data.get('behavior'),
                        'existing_id': existing_suite.id
                    })
            
            # If there are duplicates, return them for confirmation
            if duplicates:
                return jsonify({
                    'error': 'duplicates_found',
                    'message': 'Duplicate test suites found',
                    'duplicates': duplicates,
                    'total_suites': len(import_data['test_suites']),
                    'duplicate_count': len(duplicates)
                }), 409
            
            # If no duplicates or force_import is True, proceed with import
            suites_imported = 0
            for suite_data in import_data['test_suites']:
                new_suite = TestSuite(
                    description=suite_data['description'],
                    behavior=suite_data.get('behavior'),
                    objective=suite_data.get('objective'),
                    user_id=current_user.id
                )
                db.session.add(new_suite)
                
                # Create test cases
                for case_data in suite_data.get('test_cases', []):
                    test_case = TestCase(
                        prompt=case_data['prompt'],
                        transformations=case_data.get('transformations'),
                        source=case_data.get('source'),
                        attack_type=case_data.get('attack_type'),
                        data_type=case_data.get('data_type'),
                        nist_risk=case_data.get('nist_risk'),
                        reviewed=case_data.get('reviewed', False)
                    )
                    db.session.add(test_case)
                    new_suite.test_cases.append(test_case)
                
                suites_imported += 1
            
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Successfully imported {suites_imported} test suite(s)',
                'suites_imported': suites_imported
            })
            
        # Handle single suite import
        elif 'test_suite' in import_data:
            suite_data = import_data['test_suite']
            
            # Check for duplicates
            existing_suite = TestSuite.query.filter_by(
                description=suite_data['description'],
                behavior=suite_data.get('behavior')
            ).first()
            
            if existing_suite:
                return jsonify({
                    'error': 'Duplicate test suite',
                    'message': f'A test suite with description "{suite_data["description"]}" and behavior "{suite_data.get("behavior")}" already exists.',
                    'existing_suite_id': existing_suite.id
                }), 409
            
            new_suite = TestSuite(
                description=suite_data['description'],
                behavior=suite_data.get('behavior'),
                objective=suite_data.get('objective'),
                user_id=current_user.id
            )
            db.session.add(new_suite)
            
            # Create test cases
            for case_data in suite_data.get('test_cases', []):
                test_case = TestCase(
                    prompt=case_data['prompt'],
                    transformations=case_data.get('transformations'),
                    source=case_data.get('source'),
                    attack_type=case_data.get('attack_type'),
                    data_type=case_data.get('data_type'),
                    nist_risk=case_data.get('nist_risk'),
                    reviewed=case_data.get('reviewed', False)
                )
                db.session.add(test_case)
                new_suite.test_cases.append(test_case)
            
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Test suite imported successfully',
                'suite_id': new_suite.id
            })
        else:
            return jsonify({'error': 'Invalid file format'}), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error importing test suite: {str(e)}'}), 500

@test_suites_bp.route('/export_all', methods=['GET'])
@login_required
def export_all_test_suites():
    """Export all test suites to a JSON file."""
    # Query all test suites
    test_suites = TestSuite.query.all()
    
    # Create export data
    export_data = {
        'version': '1.0',
        'exported_at': datetime.utcnow().isoformat(),
        'test_suites': []
    }
    
    # Add each test suite
    for suite in test_suites:
        suite_data = {
            'description': suite.description,
            'behavior': suite.behavior,
            'objective': suite.objective,
            'test_cases': []
        }
        
        # Add test cases for this suite
        for tc in suite.test_cases:
            case_data = {
                'prompt': tc.prompt,
                'transformations': tc.transformations,
                'source': tc.source,
                'attack_type': tc.attack_type,
                'data_type': tc.data_type,
                'nist_risk': tc.nist_risk,
                'reviewed': tc.reviewed
            }
            suite_data['test_cases'].append(case_data)
        
        export_data['test_suites'].append(suite_data)
    
    # Create response with JSON file
    response = jsonify(export_data)
    response.headers['Content-Disposition'] = 'attachment; filename=all_test_suites.json'
    return response
