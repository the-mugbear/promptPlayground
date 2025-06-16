# app/endpoints/views_manual_test.py
from flask import render_template, request, redirect, url_for, jsonify 
from flask_login import login_required 

from extensions import db
from models.model_ManualTestRecord import ManualTestRecord
from services.endpoints.api_templates import PAYLOAD_TEMPLATES 
from services.transformers.registry import TRANSFORM_PARAM_CONFIG, apply_transformation 
from services.common.http_request_service import execute_api_request 
from services.common.header_parser_service import parse_raw_headers 
from . import endpoints_bp

@endpoints_bp.route('/manual_test', methods=['GET', 'POST'])
@login_required 
def manual_test():
    if request.method == 'GET':
        history = ManualTestRecord.query.order_by(ManualTestRecord.created_at.desc()).all()
        return render_template('endpoints/manual_test.html',
                               payload_templates=PAYLOAD_TEMPLATES, # Pass for selection
                               transform_params=TRANSFORM_PARAM_CONFIG,
                               history=history)

    # POST logic from original manual_test route
    host = request.form['hostname'].strip()
    path = request.form['endpoint_path'].strip()
    raw_hdrs = request.form.get('raw_headers', '').strip()
    tpl = request.form['http_payload'].strip() # This is the template with {{INJECT_PROMPT}}
    repl_value = request.form['replacement_value'].strip() # Value for {{INJECT_PROMPT}}

    hdrs_dict = parse_raw_headers(raw_hdrs) if raw_hdrs else {}
    assembled_hdrs = "\n".join(f"{k}: {v}" for k,v in hdrs_dict.items())

    # Apply transformations to `repl_value`
    transformed_repl_value = repl_value
    selected_transforms = request.form.getlist('transforms') # IDs of selected transforms
    for t_id in selected_transforms:
        # Assuming t_id corresponds to a key in TRANSFORM_PARAM_CONFIG or similar
        params_for_transform = {}
        # Example: if your form sends "transformId_paramName=value"
        if val := request.form.get(f"{t_id}_value"): # Generic way to get a param named 'value'
            params_for_transform['value'] = val
        # Add more specific param handling if transforms have different param names
        
        transformed_repl_value = apply_transformation(t_id, transformed_repl_value, params_for_transform)


    final_payload = tpl.replace("{{INJECT_PROMPT}}", transformed_repl_value)
    result = execute_api_request(
        method="POST",  # Default to POST for manual testing
        hostname_url=host,
        endpoint_path=path,
        raw_headers_or_dict=assembled_hdrs,
        http_payload_as_string=final_payload
    )

    rec = ManualTestRecord(
        hostname=host,
        endpoint=path,
        raw_headers=assembled_hdrs,
        payload_sent=final_payload,
        response_data=result.get("response_body"),
        # status_code=result.get("status_code") # Consider adding if model supports
    )
    db.session.add(rec)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True,
            "record": {
                "id": rec.id,
                "created_at": rec.created_at.strftime("%Y-%m-%d %H:%M:%S"), # Format for display
                "payload_sent": rec.payload_sent,
                "response_data": rec.response_data
                # "status_code": rec.status_code
            }
        })
    else:
        return redirect(url_for('manual_test')) # Redirect back to the GET view