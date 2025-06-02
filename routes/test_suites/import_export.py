"""
Test suite import/export operations.
This module handles importing and exporting test suites.
"""

import json
from flask import request, render_template, jsonify
from flask_login import login_required, current_user
from extensions import db
from flask import current_app
from models.model_TestSuite import TestSuite
from models.model_TestCase import TestCase
from . import test_suites_bp
from datetime import datetime

@test_suites_bp.route('/import/help', methods=['GET'])
def import_help():
    """Display help page for test suite import format."""
    return render_template('test_suites/import_help.html')

@test_suites_bp.route('/<int:suite_id>/export', methods=['GET'])
@login_required
def export_test_suite(suite_id):
    """Export a test suite to a JSON file, using the array format."""
    suite = TestSuite.query.get_or_404(suite_id)
    
    suite_data = {
        'description': suite.description,
        'behavior': suite.behavior,
        'objective': suite.objective,
        'test_cases': []
    }
    
    for tc in suite.test_cases:
        case_data = {
            'prompt': tc.prompt,
            'source': tc.source,
            'attack_type': tc.attack_type,
            'data_type': tc.data_type,
            'nist_risk': tc.nist_risk,
            'reviewed': tc.reviewed
        }
        suite_data['test_cases'].append(case_data)
    
    # Export data now uses 'test_suites' as an array with a single element
    export_data = {
        'version': '1.0',
        'exported_at': datetime.utcnow().isoformat(), 
        'test_suites': [suite_data] 
    }
    
    response = jsonify(export_data)
    response.headers['Content-Disposition'] = f'attachment; filename={suite.description}_{suite_id}.json'
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