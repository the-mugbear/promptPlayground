from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from extensions import db
from models.model_TestCase import TestCase
from datetime import datetime
from services.transformers.helpers import process_transformations

test_cases_bp = Blueprint('test_cases_bp', __name__, url_prefix='/test_cases')

# ********************************
# ROUTES
# ********************************
@test_cases_bp.route('/', methods=['GET'])
def list_test_cases():
    """
    GET /test_cases -> Display all test cases (could be a JSON or HTML page)
    """
    test_cases = TestCase.query.all()
    return render_template('test_cases/list_test_cases.html', test_cases=test_cases)

@test_cases_bp.route('/', methods=['POST'])
def create_test_case_api():
    """
    POST /test_cases -> For JSON API style creation
    """
    data = request.get_json(force=True)
    description = data.get('description')
    
    new_case = TestCase(description=description)
    db.session.add(new_case)
    db.session.commit()

    return jsonify({"id": new_case.id, "message": "Test case created"}), 201

# Routes for detail, update, delete
@test_cases_bp.route('/<int:case_id>', methods=['GET'])
def get_test_case(case_id):
    """
    GET /test_cases/<id> -> Show details of a specific test case
    """
    test_case = TestCase.query.get_or_404(case_id)
    return render_template('test_cases/view_test_case.html', test_case=test_case)

# ********************************
# SERVICES
# ********************************
@test_cases_bp.route('/<int:case_id>', methods=['PUT'])
def update_test_case(case_id):
    """
    PUT /test_cases/<id> -> Update an existing test case
    """
    test_case = TestCase.query.get_or_404(case_id)
    data = request.get_json(force=True)
    test_case.description = data.get('description', test_case.description)
    db.session.commit()
    return jsonify({"message": "Test case updated"}), 200

@test_cases_bp.route('/<int:case_id>', methods=['DELETE'])
def delete_test_case(case_id):
    """
    DELETE /test_cases/<id> -> Delete a specific test case
    """
    test_case = TestCase.query.get_or_404(case_id)
    db.session.delete(test_case)
    db.session.commit()
    return jsonify({"message": "Test case deleted"}), 200


# Now for a form-based approach:
@test_cases_bp.route('/create', methods=['GET'])
def create_test_case_form():
    """
    GET /test_cases/create -> Show an HTML form to create a test case
    """
    return render_template('test_cases/create_test_case.html')

@test_cases_bp.route('/create', methods=['POST'])
def handle_create_test_case_form():
    # Get the test case prompt (you might want to rename the form field to "prompt")
    prompt = request.form.get('prompt') or request.form.get('new_test_cases')
    
    # Process transformations using the shared helper
    final_transformations = process_transformations(request.form)
    
    new_case = TestCase(prompt=prompt, transformations=final_transformations)
    db.session.add(new_case)
    db.session.commit()

    flash('New test case created successfully!', 'success')
    return redirect(url_for('test_cases_bp.create_test_case_api'))
