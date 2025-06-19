import json
from flask import request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from models.model_TestCase import TestCase
from models.model_TestSuite import TestSuite
from services.transformers.registry import apply_transformations_to_lines

from . import test_suites_bp

@test_suites_bp.route('/create', methods=['POST'])
@login_required 
def create_test_suite():
    """
    POST /test_suites/create -> Handle the form submission to create a new test suite.
    Test cases are now taken from 'test_case_prompts' which is a JSON string array.
    Transformations are no longer handled at the suite or test case creation level.
    """
    description = request.form.get('description')
    behavior = request.form.get('behavior')
    objective = request.form.get('objective')

    if not description: # Basic validation
        flash('Test suite description is required.', 'error')
        return redirect(url_for('test_suites_bp.create_test_suite_form')) # Make sure this route exists or adjust

    new_suite = TestSuite(
        description=description,
        behavior=behavior,
        objective=objective,
        user_id=current_user.id
    )
    db.session.add(new_suite)
    
    try:
        # Process test cases from the 'test_case_prompts' JSON string
        test_case_prompts_json_string = request.form.get('test_case_prompts', '')
        
        prompts_added_count = 0
        if test_case_prompts_json_string:
            try:
                list_of_prompts = json.loads(test_case_prompts_json_string)

                if not isinstance(list_of_prompts, list):
                    flash('Test case prompts are not in the expected list format.', 'warning')
                elif not list_of_prompts:
                    # This case means the JSON was "[]" or contained only empty/whitespace strings
                    flash('No valid test case prompts were provided.', 'info')
                else:
                    for prompt_text in list_of_prompts:
                        # Ensure each item in the list is a string and not empty after stripping
                        if isinstance(prompt_text, str) and prompt_text.strip():
                            test_case = TestCase(
                                prompt=prompt_text.strip(),
                                # Add other TestCase fields if necessary, e.g., user_id
                                # source='manual_entry', # Example default
                            )
                            # db.session.add(test_case) # Adding here is fine if not auto-added by relationship
                            new_suite.test_cases.append(test_case) # This associates the test case with the suite
                            prompts_added_count += 1
                        else:
                            # Optionally log or flash a message about invalid/empty entries in the list
                            print(f"Skipping invalid or empty prompt entry: '{prompt_text}'")
                    
                    if prompts_added_count > 0:
                        flash(f'{prompts_added_count} test case(s) prepared for the new suite.', 'success')
                
            except json.JSONDecodeError:
                flash('Error decoding test case prompts. Please ensure they are correctly formatted.', 'error')
                # Log the error and the problematic string for debugging
                print(f"JSONDecodeError for input: {test_case_prompts_json_string}")
        else:
            # This means the 'test_case_prompts' field was empty or not sent
            flash('No test case prompts were provided with the suite.', 'info')

        # Now commit everything: the new suite and all associated test cases
        db.session.commit() 
        
        if prompts_added_count > 0:
             flash('New test suite and associated test cases created successfully!', 'success')
        else:
            flash('New test suite created. No test cases were added based on input.', 'info')

        return redirect(url_for('test_suites_bp.test_suite_details', suite_id=new_suite.id)) # Make sure this route exists

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating test suite: {str(e)}', 'error')
        return redirect(url_for('test_suites_bp.create_test_suite_form')) # 

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

@test_suites_bp.route('/<int:suite_id>/remove_case/<int:case_id>', methods=['POST'])
@login_required 
def remove_test_case_from_suite(suite_id, case_id):
    """POST /test_suites/<suite_id>/remove_case/<case_id> -> Remove a test case from a suite"""
    suite = TestSuite.query.get_or_404(suite_id)
    test_case = TestCase.query.get_or_404(case_id)
    
    # Check ownership
    if suite.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        if test_case in suite.test_cases:
            suite.test_cases.remove(test_case)
            db.session.commit()
            return jsonify({"message": "Test case removed from suite"})
        else:
            return jsonify({"error": "Test case not found in this suite"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@test_suites_bp.route('/<int:suite_id>/add_case', methods=['POST'])
@login_required 
def add_test_case_to_suite(suite_id):
    """POST /test_suites/<suite_id>/add_case -> Add a test case to a suite"""
    suite = TestSuite.query.get_or_404(suite_id)
    
    # Check ownership
    if suite.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    
    if not data or 'prompt' not in data:
        return jsonify({"error": "No prompt provided"}), 400
    
    prompt = data['prompt'].strip()
    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400
    
    try:
        # Create new test case
        test_case = TestCase(
            prompt=prompt,
            user_id=current_user.id,
            source='manual_input',
            reviewed=False,
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
                "source": test_case.source,
                "transformations": test_case.transformations
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 