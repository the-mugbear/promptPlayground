"""
Manual testing operations for endpoints.
This module handles manual testing of endpoints and recording test results.
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from extensions import db
from models.model_ManualTestRecord import ManualTestRecord
from services.endpoints.api_templates import PAYLOAD_TEMPLATES
from services.transformers.registry import apply_transformations_to_lines, TRANSFORM_PARAM_CONFIG, apply_transformation
from services.common.http_request_service import replay_post_request
from services.common.header_parser_service import parse_raw_headers
from . import endpoints_bp

@endpoints_bp.route('/manual_test', methods=['GET', 'POST'])
def manual_test():
    """
    Handle manual testing of endpoints.
    
    GET: Display the manual test form and test history
    POST: Execute a manual test and record the results
    
    Returns:
        GET: Rendered template with form and history
        POST: Redirect to form or JSON response for AJAX requests
    """
    # Handle GET request - show form and history
    if request.method == 'GET':
        history = ManualTestRecord.query.order_by(ManualTestRecord.created_at.desc()).all()
        return render_template('endpoints/manual_test.html',
                             payload_templates=PAYLOAD_TEMPLATES,
                             transform_params=TRANSFORM_PARAM_CONFIG,
                             history=history)

    # Handle POST request - execute test
    host = request.form['hostname'].strip()
    path = request.form['endpoint_path'].strip()
    raw_hdrs = request.form.get('raw_headers', '').strip()
    tpl = request.form['http_payload'].strip()
    repl = request.form['replacement_value'].strip()

    # Parse headers
    hdrs_dict = parse_raw_headers(raw_hdrs) if raw_hdrs else {}
    assembled_hdrs = "\n".join(f"{k}: {v}" for k,v in hdrs_dict.items())

    # Apply requested transformations
    transforms = []
    for t_id in request.form.getlist('transforms'):
        params = {}
        if val := request.form.get(f"{t_id}_value"):
            params['value'] = val
        transforms.append({'type': t_id, **params})

    # Apply transformations in order
    for tinfo in transforms:
        repl = apply_transformation(tinfo['type'], repl, {'value': tinfo.get('value')})

    # Build final payload
    payload = tpl.replace("{{INJECT_PROMPT}}", repl)

    # Execute request
    result = replay_post_request(host, path, payload, assembled_hdrs)

    # Record test result
    rec = ManualTestRecord(
        hostname=host,
        endpoint=path,
        raw_headers=assembled_hdrs,
        payload_sent=payload,
        response_data=result.get("response_text"),
    )
    db.session.add(rec)
    db.session.commit()

    # Handle response based on request type
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "success": True,
            "record": {
                "id": rec.id,
                "created_at": rec.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "payload_sent": rec.payload_sent,
                "response_data": rec.response_data
            }
        })
    else:
        return redirect(url_for('endpoints_bp.manual_test')) 