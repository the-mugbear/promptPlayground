import json
from flask import request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from models.model_TestCase import TestCase
from models.model_TestSuite import TestSuite
from services.transformers.registry import apply_transformations_to_lines
from services.transformers.helpers import process_transformations
from . import test_suites_bp

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

@test_suites_bp.route('/preview_transform', methods=['POST'])
@login_required
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

@test_suites_bp.route('/<int:suite_id>/remove_test_case/<int:case_id>', methods=['POST'])
@login_required 
def remove_test_case_from_suite(suite_id, case_id):
    """POST /test_suites/<suite_id>/remove_test_case/<case_id> -> Remove a test case from a suite"""
    suite = TestSuite.query.get_or_404(suite_id)
    test_case = TestCase.query.get_or_404(case_id)
    
    if test_case in suite.test_cases:
        suite.test_cases.remove(test_case)
        db.session.commit()
        flash(f"Test case {case_id} removed from suite {suite_id}", "success")
    else:
        flash(f"Test case {case_id} is not in suite {suite_id}", "error")
    
    return redirect(url_for('test_suites_bp.test_suite_details', suite_id=suite_id))

@test_suites_bp.route('/<int:suite_id>/add_test_case', methods=['POST'])
@login_required 
def add_test_case_to_suite(suite_id):
    """POST /test_suites/<suite_id>/add_test_case -> Add a test case to a suite"""
    suite = TestSuite.query.get_or_404(suite_id)
    data = request.get_json()
    
    if not data or 'prompt' not in data:
        return jsonify({"error": "No prompt provided"}), 400
    
    prompt = data['prompt'].strip()
    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400
    
    # Create new test case
    test_case = TestCase(
        prompt=prompt,
        transformations=data.get('transformations', [])
    )
    db.session.add(test_case)
    db.session.flush()
    
    # Add to suite
    suite.test_cases.append(test_case)
    db.session.commit()
    
    return jsonify({
        "message": "Test case added successfully",
        "test_case": {
            "id": test_case.id,
            "prompt": test_case.prompt,
            "transformations": test_case.transformations
        }
    }) 