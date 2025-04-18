import json
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from extensions import db
from models.model_TestCase import TestCase
from models.model_TestSuite import TestSuite
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

@test_suites_bp.route('/create', methods=['GET'])
def create_test_suite_form():
    """
    GET /test_suites/create -> Display an HTML form to create a new test suite
    """
    # If you want to display existing test cases to add to the new suite, fetch them:
    existing_test_cases = TestCase.query.all()
    existing_test_suites = TestSuite.query.all()
    orphaned_test_cases = TestCase.query.filter(~TestCase.test_suites.any()).all()

    return render_template(
        'test_suites/create_suite.html', 
        existing_test_cases=existing_test_cases, 
        existing_suites=existing_test_suites,
        orphaned_test_cases=orphaned_test_cases
    )

@test_suites_bp.route('/<int:suite_id>/details', methods=["GET"])
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
def create_test_suite():
    """
    POST /test_suites/create -> Handle the form submission to create a new test suite.
    """
    description = request.form.get('description')
    behavior = request.form.get('behavior')

    # Process suite-level transformations (default for test cases that inherit)
    suite_transformations = process_transformations(request.form)

    # Create the test suite.
    new_suite = TestSuite(
        description=description,
        behavior=behavior
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
def delete_test_suite(suite_id):
    """
    POST /test_suites/<suite_id>/delete -> Deletes a test suite if allowed.
    """
    suite_to_delete = TestSuite.query.get_or_404(suite_id)

    # Option A) If you want to block deletion if it’s used in a run:
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
def add_test_case_to_suite(suite_id):
    data = request.get_json(force=True) or {}
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({"success": False, "error": "Prompt cannot be empty"}), 400

    # Fetch suite
    suite = TestSuite.query.get_or_404(suite_id)

    # Decide on transformations (here: inherit suite’s defaults)
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