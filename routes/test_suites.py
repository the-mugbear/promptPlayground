from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from extensions import db
from models.model_TestCase import TestCase
from models.model_TestSuite import TestSuite
from datetime import datetime

test_suites_bp = Blueprint("test_suites_bp", __name__, url_prefix="/test_suites")

#
# ROUTES
# List test suites ('/')
# Get test suite ('<int:suiteID>') GET
# Update test suite ('<int:suiteID>') PUT
# Create test suite ('/create_test_suite') 
# GET /test_suites/list
# GET /test_suites/create
# POST /test_suites/create


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
    return render_template('test_suites/create_suite.html', existing_test_cases=existing_test_cases)

@test_suites_bp.route('/create', methods=['POST'])
def create_test_suite():
    """
    POST /test_suites/create -> Handle the form submission to create a new test suite
    """
    description = request.form.get('description')
    behavior = request.form.get('behavior')
    # attack = request.form.get('attack')

    # 1. Create the suite
    new_suite = TestSuite(description=description, behavior=behavior)
    db.session.add(new_suite)
    db.session.commit()

    # 2. Check for new test cases data
    new_test_cases_data = request.form.get('new_test_cases')
    if new_test_cases_data:
        lines = [line.strip() for line in new_test_cases_data.split('\n') if line.strip()]
        for line in lines:
            test_case = TestCase(prompt=line)
            db.session.add(test_case)
            # we could commit later, but let's flush first:
            db.session.flush()
            new_suite.test_cases.append(test_case)
        db.session.commit()

    # 3. Associate existing test cases
    selected_test_case_ids = request.form.getlist('selected_test_cases')
    for tc_id in selected_test_case_ids:
        existing_tc = TestCase.query.get(tc_id)
        if existing_tc:
            new_suite.test_cases.append(existing_tc)

    db.session.commit()

    flash('New test suite created successfully!', 'success')
    # Redirect to the list page (or somewhere else)
    return redirect(url_for('test_suites_bp.list_test_suites'))