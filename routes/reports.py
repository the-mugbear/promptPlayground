# reports.py
from flask import Blueprint, render_template, jsonify, request, abort # Added request, abort
from collections import Counter, defaultdict # Added defaultdict
from sqlalchemy.orm import selectinload, joinedload # Added selectinload, joinedload

# --- Import ALL necessary models ---
from models.model_Endpoints import Endpoint  
from models.model_TestRun import TestRun     
from models.model_TestExecution import TestExecution 
from models.model_TestRunAttempt import TestRunAttempt # Needed for joining
from models.model_TestCase import TestCase     
from models.model_TestSuite import TestSuite # Assuming you have this model
from models.model_Dialogue import Dialogue
# Import db instance if not already imported
from extensions import db
report_bp = Blueprint('report_bp', __name__, url_prefix='/reports')

# ********************************
# ROUTES
# ********************************
@report_bp.route('/report', methods=['GET'])
def report():
    """
    Renders a page with a dropdown of endpoints.
    """
    endpoints = Endpoint.query.all()
    return render_template('reports/report.html', endpoints=endpoints)

# ********************************
# SERVICES
# ********************************
@report_bp.route('/report_ajax/<int:endpoint_id>', methods=['GET'])
def report_ajax(endpoint_id):
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    # Query test runs associated with the endpoint
    test_runs = TestRun.query.filter_by(endpoint_id=endpoint_id).order_by(TestRun.created_at.desc()).all()

    # --- Calculate Overall Metrics ---
    overall_total_executions = 0
    overall_passed_count = 0
    overall_failed_count = 0
    overall_skipped_count = 0
    overall_pending_review_count = 0
    overall_transformation_counter = Counter()

    runs_data = [] # To store data for each run, including its metrics

    for run in test_runs:
        # --- Calculate Per-Run Metrics ---
        run_total_executions = 0
        run_passed_count = 0
        run_failed_count = 0
        run_skipped_count = 0
        run_pending_review_count = 0
        # We could track per-run transformations if needed, but let's start simple
        
        for attempt in run.attempts:
            # Use joinedload or selectinload if performance becomes an issue here
            # Eager load executions and their test cases if needed for transformation counting
            executions = TestExecution.query.filter_by(test_run_attempt_id=attempt.id).options(
                # Add selectinload(TestExecution.test_case) if accessing transformations
            ).all()

            for execution in executions:
                # Increment overall counts
                overall_total_executions += 1
                # Increment per-run counts
                run_total_executions += 1

                status = execution.status.lower() if execution.status else ""
                
                # Update both overall and per-run metrics based on status
                if status == 'passed':
                    overall_passed_count += 1
                    run_passed_count += 1
                elif status == 'failed':
                    overall_failed_count += 1
                    run_failed_count += 1
                    # Count overall failed transformations
                    test_case = execution.test_case # Assumes test_case relationship is loaded if needed
                    if test_case and test_case.transformations:
                        for transformation in test_case.transformations:
                             t_type = transformation.get('type')
                             if t_type:
                                 overall_transformation_counter[t_type] += 1
                elif status == 'skipped':
                    overall_skipped_count += 1
                    run_skipped_count += 1
                elif status == 'pending_review':
                    overall_pending_review_count += 1
                    run_pending_review_count += 1
                # Add other status conditions if necessary

        # --- Store Per-Run Data ---
        runs_data.append({
            "id": run.id,
            "name": run.name,
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else "",
            "metrics": { # Add the calculated per-run metrics here
                "total": run_total_executions,
                "passed": run_passed_count,
                "failed": run_failed_count,
                "skipped": run_skipped_count,
                "pending_review": run_pending_review_count
            }
        })

    # --- Prepare Overall Metrics ---
    overall_metrics = {
        "total_executions": overall_total_executions,
        "passed": overall_passed_count,
        "failed": overall_failed_count,
        "skipped": overall_skipped_count,
        "pending_review": overall_pending_review_count,
        "failed_transformations": dict(overall_transformation_counter)
    }

    # --- Query Dialogues --- (Existing logic)
    dialogues = Dialogue.query.filter_by(endpoint_id=endpoint.id).all()
    dialogues_list = [{
            "id": d.id, "source": d.source,
            "created_at": d.created_at.isoformat() if d.created_at else "",
            "conversation": d.conversation
        } for d in dialogues]

    # --- Return Combined JSON ---
    return jsonify({
        "endpoint": {
            "id": endpoint.id, "name": endpoint.name,
            "base_url": endpoint.base_url, "path": endpoint.path
        },
        "overall_metrics": overall_metrics, # Renamed for clarity
        "test_runs": runs_data, # Now includes per-run metrics
        "dialogues": dialogues_list
    })


@report_bp.route('/disposition_view/<context_type>/<int:context_id>/<status>')
def disposition_view(context_type, context_id, status):
    """
    Displays TestExecutions filtered by context (endpoint/run) and status,
    grouped by TestSuite, allowing for disposition updates.
    """
    # Validate context_type
    if context_type not in ['endpoint', 'test_run']:
        abort(404, description="Invalid context type specified.")

    # --- Base Query ---
    query = TestExecution.query.filter(TestExecution.status == status)

    # --- Eager Loading ---
    # Load test_case -> test_suites relationship efficiently
    query = query.options(
        selectinload(TestExecution.test_case).selectinload(TestCase.test_suites),
        selectinload(TestExecution.attempt) # Load attempt data if needed later
    )

    # --- Context Filtering ---
    context_name = ""
    if context_type == 'test_run':
        run = TestRun.query.get_or_404(context_id)
        context_name = f"Test Run '{run.name}' (ID: {run.id})"
        # Filter by Test Run ID via the attempt relationship
        query = query.join(TestExecution.attempt).filter(TestRunAttempt.test_run_id == context_id)
        
    elif context_type == 'endpoint':
        endpoint = Endpoint.query.get_or_404(context_id)
        context_name = f"Endpoint '{endpoint.name}' (ID: {endpoint.id})"
         # Filter by Endpoint ID via joins: TestExecution -> TestRunAttempt -> TestRun
        query = query.join(TestExecution.attempt).join(TestRunAttempt.test_run).filter(TestRun.endpoint_id == context_id)

    # --- Optional: Transformation Filtering ---
    # Example: Handle transformation filter passed from the bar chart click
    transformation_type = request.args.get('transformation_type')
    if transformation_type:
        # This requires filtering based on JSON content, which can be tricky & DB specific.
        # Simple Python filtering after fetch (less efficient for large datasets):
        # executions_all = query.all()
        # executions_filtered = []
        # for ex in executions_all:
        #     if ex.test_case and isinstance(ex.test_case.transformations, list):
        #         for t in ex.test_case.transformations:
        #              if isinstance(t, dict) and t.get('type') == transformation_type:
        #                  executions_filtered.append(ex)
        #                  break # Found the type, add execution and move to next one
        # executions = executions_filtered # Use the python-filtered list
        
        # Or use database-specific JSON functions if available (e.g., PostgreSQL jsonb_array_elements)
        # For simplicity, we'll skip DB-level JSON filtering for now.
        # Add a note that this filter might need refinement.
        context_name += f" using transformation '{transformation_type}'" # Add to title
        # Implement filtering logic here if needed (Python or DB specific)
        executions = query.all() # Fetch all matching status/context first
        # Re-assign `executions` after python filtering if implemented above
    else:
       executions = query.all()

    # --- Grouping Logic ---
    # Group executions by TestSuite using a dictionary
    # Key: TestSuite object, Value: List of TestExecution objects
    grouped_executions = defaultdict(list) 
    
    for ex in executions:
        if ex.test_case and ex.test_case.test_suites:
            # Associate execution with ALL suites its test case belongs to
            for suite in ex.test_case.test_suites:
                 # Check if this specific execution is already added under this suite 
                 # (to prevent duplicates if relationship loading somehow caused extras, though unlikely here)
                 if ex not in grouped_executions[suite]:
                      grouped_executions[suite].append(ex)
        else:
             # Handle executions whose test case might not have suites (optional)
             if None not in grouped_executions: grouped_executions[None] = []
             if ex not in grouped_executions[None]: grouped_executions[None].append(ex)


    return render_template(
        'reports/disposition_view.html',
        grouped_executions=grouped_executions,
        context_name=context_name,
        status_filter=status, # Pass the status for display
        transformation_filter=transformation_type # Pass filter for display
    )
