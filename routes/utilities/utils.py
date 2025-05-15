# routes/utilities/utils.py (or routes/utils_bp.py as per your comment)
from flask import Blueprint, render_template, request, flash, jsonify, current_app 
from routes.utilities.forms import RiskCalculatorForm, aitc_choices_raw, aitc_data
utils_bp = Blueprint('utils_bp', __name__,
                     url_prefix='/utilities')

# It's good practice to have this helper function defined before it's used in the route.
def calculate_risk_score_logic(form_data, current_aitc_choices_map):
    """
    Performs the risk calculation.
    """
    # Using current_app.logger for more robust logging than print()
    current_app.logger.debug(f"Calculating risk score with form_data: {form_data}")

    # Example: Assign numerical values
    av_scores = {'IO': 0.62, 'IF': 0.85} 
    pr_scores = {'H': 0.27, 'L': 0.62, 'N': 0.85} 
    ac_scores = {'L': 0.77, 'M': 0.44, 'H': 0.20} # Assuming Low complexity = higher score component
    ui_scores = {'N': 0.85, 'R': 0.62} 
    
    impact_mapping = {'N': 0.0, 'L': 0.25, 'M': 0.5, 'H': 0.75}

    # Robustly get values, defaulting to 0 if a key is somehow missing (shouldn't happen with DataRequired)
    # Also, ensure form_data keys exist before accessing, though validators should ensure they do.
    base_score_component = round(
        av_scores.get(form_data.get('attack_vector'), 0) *
        pr_scores.get(form_data.get('privileges_required'), 0) *
        ac_scores.get(form_data.get('attack_complexity'), 0) *
        ui_scores.get(form_data.get('user_interaction'), 0) * 10, 1
    )
    base_score_component = min(base_score_component, 10.0)

    char_impact_score = impact_mapping.get(form_data.get('characteristic_impact'), 0)
    legal_impact_score = impact_mapping.get(form_data.get('legal_impact'), 0)
    impact_score_component = round(max(char_impact_score, legal_impact_score) * 10, 1)
    impact_score_component = min(impact_score_component, 10.0)

    final_score = round((base_score_component + impact_score_component) / 2, 1)
    final_score = min(final_score, 10.0)

    qualitative = "Informational"
    if final_score >= 9.0:
        qualitative = "Critical"
    elif final_score >= 7.0:
        qualitative = "High"
    elif final_score >= 4.0:
        qualitative = "Medium"
    elif final_score > 0.0:
        qualitative = "Low"
    # else: qualitative remains "Informational"

    vector_parts = [
        f"AV:{form_data.get('attack_vector', 'N/A')}",
        f"PR:{form_data.get('privileges_required', 'N/A')}",
        f"AC:{form_data.get('attack_complexity', 'N/A')}",
        f"UI:{form_data.get('user_interaction', 'N/A')}",
        f"AITC:{form_data.get('aitc', 'N/A')}",
        f"CI:{form_data.get('characteristic_impact', 'N/A')}",
        f"LI:{form_data.get('legal_impact', 'N/A')}"
    ]
    vector_string = "/".join(vector_parts)

    aitc_label = form_data.get('aitc', 'N/A') # Default to key
    for key, label_text in current_aitc_choices_map:
        if key == form_data.get('aitc'):
            aitc_label = label_text
            break
    
    enriched_selected_data = form_data.copy() # Make a copy to avoid modifying original dict if passed around
    enriched_selected_data['aitc_label'] = aitc_label

    results = {
        "selected_data": enriched_selected_data,
        "base_score_component": base_score_component,
        "impact_score_component": impact_score_component,
        "final_score": final_score,
        "qualitative_assessment": qualitative,
        "vector_string": vector_string,
        "notes": "Developed by Miguel Hernandez"
    }
    current_app.logger.debug(f"Calculation results: {results}")
    return results

@utils_bp.route('/risk_calculator', methods=['GET', 'POST'])
def risk_calculator():

    if request.method == 'POST':
        current_app.logger.debug(f"POST Request Headers: {request.headers}")
        current_app.logger.debug(f"POST Request Content-Type: {request.content_type}")
        current_app.logger.debug(f"POST Request is_json: {request.is_json}")
        current_app.logger.debug(f"POST Request X-Requested-With: {request.headers.get('X-Requested-With')}")

        is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        current_app.logger.debug(f"Determined is_ajax: {is_ajax}")

        if is_ajax:
            current_app.logger.info("AJAX POST request detected.")
            try:
                data = request.get_json()
                if not data:
                    current_app.logger.warning("AJAX Error: Invalid or empty JSON payload received.")
                    return jsonify(errors={"general": "Invalid JSON payload. No data received."}), 400
                
                current_app.logger.debug(f"AJAX Data received: {data}")

                # RiskCalculatorForm expects CSRF token usually as 'csrf_token'
                # If your JS sends it with a different key in the JSON, adjust here or in JS.
                # Or, if CSRFProtect is set up to check headers for AJAX, that's another way.
                form = RiskCalculatorForm(data=data) 
                
                if form.validate():
                    current_app.logger.info("AJAX Form validation successful.")
                    form_data_dict = {
                        'attack_vector': form.attack_vector.data,
                        'privileges_required': form.privileges_required.data,
                        'attack_complexity': form.attack_complexity.data,
                        'user_interaction': form.user_interaction.data,
                        'aitc': form.aitc.data,
                        'characteristic_impact': form.characteristic_impact.data,
                        'legal_impact': form.legal_impact.data
                    }
                    # aitc_choices_raw is available due to module-level import
                    calculation_results = calculate_risk_score_logic(form_data_dict, aitc_choices_raw)
                    return jsonify(results=calculation_results)
                else:
                    current_app.logger.warning(f"AJAX Form validation failed. Errors: {form.errors}")
                    return jsonify(errors=form.errors), 400 # 400 Bad Request for validation errors
            except Exception as e:
                current_app.logger.error(f"!!! EXCEPTION IN AJAX POST HANDLER: {e}", exc_info=True)
                # import traceback # Not needed if exc_info=True with logger
                # traceback.print_exc()
                return jsonify(errors={"general": "An unexpected server error occurred processing your request."}), 500

        else: # Standard Form POST (non-AJAX)
            current_app.logger.info("Standard POST request detected (non-AJAX).")
            form = RiskCalculatorForm() # Process from request.form internally by validate_on_submit
            if form.validate_on_submit():
                current_app.logger.info("Standard POST form validation successful.")
                form_data_dict = {
                    'attack_vector': form.attack_vector.data,
                    # ... (rest of form_data_dict) ...
                    'legal_impact': form.legal_impact.data
                }
                results = calculate_risk_score_logic(form_data_dict, aitc_choices_raw)
                flash('Risk calculation complete! (Full Page Reload)', 'success')
                # For a standard POST that succeeds, you might redirect or render with results
                return render_template('utils/risk_calculator.html', title='AI Risk Calculator', form=form, results=results) # Re-render with results
            else:
                current_app.logger.warning(f"Standard POST form validation failed. Errors: {form.errors}")
                flash('Please correct the errors below and resubmit. (Full Page Reload)', 'danger')
                # Re-render the form with errors
                return render_template('utils/risk_calculator.html', title='AI Risk Calculator', form=form, results=None), 400 # Send 400 for bad input

    # GET Request
    current_app.logger.info("GET request for risk_calculator page.")
    form = RiskCalculatorForm(request.form if request.method == 'POST' else None)
    results = None
    # Initial state: no results, just display the form
    return render_template('utils/risk_calculator.html', 
                           title='AI Risk Calculator', 
                           form=form, 
                           results=results,
                           aitc_descriptions_json=aitc_data)