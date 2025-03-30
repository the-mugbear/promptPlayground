from flask import Blueprint, render_template, jsonify
from collections import Counter

from models.model_Endpoints import Endpoint  # :contentReference[oaicite:0]{index=0}&#8203;:contentReference[oaicite:1]{index=1}
from models.model_TestRun import TestRun      # :contentReference[oaicite:2]{index=2}&#8203;:contentReference[oaicite:3]{index=3}
from models.model_TestCase import TestCase      # :contentReference[oaicite:4]{index=4}&#8203;:contentReference[oaicite:5]{index=5}

report_bp = Blueprint('report_bp', __name__, url_prefix='/reports')

@report_bp.route('/report', methods=['GET'])
def report():
    """
    Renders a page with a dropdown of endpoints.
    """
    endpoints = Endpoint.query.all()
    return render_template('reports/report.html', endpoints=endpoints)

@report_bp.route('/report_ajax/<int:endpoint_id>', methods=['GET'])
def report_ajax(endpoint_id):
    """
    Returns JSON report details for the selected endpoint.
    """
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
                        # Assume each transformation is a dict with a "type" key.
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

    # Return a simplified list of test runs.
    runs_data = [{
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else ""
    } for run in test_runs]

    return jsonify({
        "endpoint": {
            "id": endpoint.id,
            "name": endpoint.name,
            "hostname": endpoint.hostname,
            "endpoint": endpoint.endpoint
        },
        "metrics": metrics,
        "test_runs": runs_data
    })
