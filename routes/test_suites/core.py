from flask import request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.model_TestSuite import TestSuite
from . import test_suites_bp

@test_suites_bp.route('/list', methods=['GET'])
def list_test_suites():
    """GET /test_suites/list -> Display a page with all existing test suites"""
    test_suites = TestSuite.query.all()
    return render_template('test_suites/list_test_suites.html', test_suites=test_suites)

@test_suites_bp.route('/list3', methods=['GET'])
def list_three():
    """GET /test_suites/list3 -> Display a page with all existing test suites using three.js"""
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

@test_suites_bp.route('/<int:suite_id>/delete', methods=["POST"])
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

    try:
        # Get all test cases associated with this suite
        test_cases = list(suite_to_delete.test_cases)
        
        # Remove the association between suite and test cases
        suite_to_delete.test_cases = []
        db.session.flush()
        
        # Delete the test cases that are only associated with this suite
        for case in test_cases:
            if len(case.test_suites) == 0:  # If the case is not associated with any other suite
                db.session.delete(case)
        
        # Delete the suite
        db.session.delete(suite_to_delete)
        db.session.commit()
        
        flash(f"Test Suite #{suite_id} and its orphaned test cases deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting Test Suite #{suite_id}: {str(e)}", "error")

    return redirect(url_for('test_suites_bp.list_test_suites'))

@test_suites_bp.route('/<int:suite_id>/update', methods=['PUT'])
@login_required 
def update_test_suite(suite_id):
    """PUT /test_suites/<suite_id>/update -> Update a test suite's details"""
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

    if updated_fields:
        db.session.commit()
        return jsonify({
            "message": f"Updated fields: {', '.join(updated_fields)}",
            "suite": {
                "id": suite.id,
                "description": suite.description,
                "behavior": suite.behavior,
                "objective": suite.objective
            }
        })
    else:
        return jsonify({"message": "No fields were updated"}), 400 