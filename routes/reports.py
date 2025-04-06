from flask import Blueprint, render_template, jsonify
from collections import Counter

from models.model_Endpoints import Endpoint  
from models.model_TestRun import TestRun     
from models.model_TestCase import TestCase     
from models.model_Dialogue import Dialogue

report_bp = Blueprint('report_bp', __name__, url_prefix='/reports')

@report_bp.route('/report', methods=['GET'])
def report():
    """
    Renders a page with a dropdown of endpoints.
    """
    endpoints = Endpoint.query.all()
    return render_template('reports/report.html', endpoints=endpoints)

from models.model_Dialogue import Dialogue

@report_bp.route('/report_ajax/<int:endpoint_id>', methods=['GET'])
def report_ajax(endpoint_id):
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    test_runs = TestRun.query.filter_by(endpoint_id=endpoint_id).order_by(TestRun.created_at.desc()).all()

    # Build metrics.
    total_executions = 0
    passed_count = 0
    failed_count = 0
    skipped_count = 0
    pending_review_count = 0
    transformation_counter = Counter()

    for run in test_runs:
        for attempt in run.attempts:
            for execution in attempt.executions:
                total_executions += 1
                status = execution.status.lower() if execution.status else ""
                if status == 'passed':
                    passed_count += 1
                elif status == 'failed':
                    failed_count += 1
                    test_case = execution.test_case
                    if test_case and test_case.transformations:
                        for transformation in test_case.transformations:
                            t_type = transformation.get('type')
                            if t_type:
                                transformation_counter[t_type] += 1
                elif status == 'skipped':
                    skipped_count += 1
                elif status == 'pending_review':
                    pending_review_count += 1

    metrics = {
        "total_executions": total_executions,
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "pending_review": pending_review_count,
        "failed_transformations": dict(transformation_counter)
    }

    runs_data = [{
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else ""
    } for run in test_runs]

    # Query dialogues with target matching the endpoint id (cast to string)
    dialogues = Dialogue.query.filter_by(endpoint_id=endpoint.id).all()
    dialogues_list = []
    for d in dialogues:
        dialogues_list.append({
            "id": d.id,
            "source": d.source,
            "created_at": d.created_at.isoformat() if d.created_at else "",
            "conversation": d.conversation  # you could truncate this if needed
        })

    return jsonify({
        "endpoint": {
            "id": endpoint.id,
            "name": endpoint.name,
            "hostname": endpoint.hostname,
            "endpoint": endpoint.endpoint
        },
        "metrics": metrics,
        "test_runs": runs_data,
        "dialogues": dialogues_list
    })