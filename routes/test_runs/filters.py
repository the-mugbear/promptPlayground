"""
Filter management operations for test runs.
This module handles adding and removing prompt filters from test runs.
"""

from flask import redirect, url_for, flash, request
from flask_login import login_required
from extensions import db
from models.model_TestRun import TestRun
from models.model_PromptFilter import PromptFilter
from . import test_runs_bp

@test_runs_bp.route('/<int:run_id>/add_filter', methods=['POST'])
@login_required
def add_filter(run_id):
    """
    Add a prompt filter to a test run.
    
    Args:
        run_id: The ID of the test run to add the filter to
        
    Returns:
        Redirect to test run view with success/error message
    """
    run = TestRun.query.get_or_404(run_id)
    filter_id = request.form.get('filter_id')
    pf = PromptFilter.query.get(filter_id)
    if pf and pf not in run.filters:
        run.filters.append(pf)
        db.session.commit()
        flash(f'Added filter "{pf.name}"', "success")
    return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id))

@test_runs_bp.route('/<int:run_id>/remove_filter/<int:filter_id>', methods=['POST'])
@login_required
def remove_filter(run_id, filter_id):
    """
    Remove a prompt filter from a test run.
    
    Args:
        run_id: The ID of the test run to remove the filter from
        filter_id: The ID of the filter to remove
        
    Returns:
        Redirect to test run view with success/error message
    """
    run = TestRun.query.get_or_404(run_id)
    pf = PromptFilter.query.get_or_404(filter_id)
    if pf in run.filters:
        run.filters.remove(pf)
        db.session.commit()
        flash(f'Removed filter "{pf.name}"', "warning")
    return redirect(url_for('test_runs_bp.view_test_run', run_id=run_id)) 