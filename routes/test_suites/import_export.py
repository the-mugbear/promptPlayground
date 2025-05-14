"""
Test suite import/export operations.
This module handles importing and exporting test suites.
"""

import json
import yaml
import os
from flask import request, render_template, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from extensions import db
from flask import current_app
from models.model_TestSuite import TestSuite
from models.model_TestCase import TestCase
from models.model_DatasetReference import DatasetReference
from celery_app import celery
from workers.import_tasks import import_dataset_task
from . import test_suites_bp

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

@test_suites_bp.route('/import/help', methods=['GET'])
def import_help():
    """Display help page for test suite import format."""
    return render_template('test_suites/import_help.html')

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