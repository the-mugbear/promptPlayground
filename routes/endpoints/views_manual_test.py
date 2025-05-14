# app/endpoints/views_manual_test.py
from flask import render_template, request, redirect, url_for, jsonify # Removed flash if not used here
from flask_login import login_required # If manual_test itself requires login

from extensions import db
from models.model_ManualTestRecord import ManualTestRecord
from services.endpoints.api_templates import PAYLOAD_TEMPLATES # Or another source for these
from services.transformers.registry import TRANSFORM_PARAM_CONFIG, apply_transformation # Adjust path
from services.common.http_request_service import replay_post_request # Adjust path
from services.common.header_parser_service import parse_raw_headers # Adjust path

from . import endpoints_bp

@endpoints_bp.route('/manual_test', methods=['GET', 'POST'])
# @login_required # Add if this page needs login
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
    result = replay_post_request(host, path, final_payload, assembled_hdrs)

    rec = ManualTestRecord(
        hostname=host,
        endpoint=path,
        raw_headers=assembled_hdrs,
        payload_sent=final_payload,
        response_data=result.get("response_text"),
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