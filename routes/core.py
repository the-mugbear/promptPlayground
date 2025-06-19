from flask import Blueprint, render_template, abort, request, redirect, flash, url_for, send_from_directory
from flask_login import current_user
from extensions import db
from datetime import datetime, timezone

from models.model_TestRun import TestRun
from models.model_TestSuite import TestSuite
from models.model_ExecutionSession import ExecutionSession, ExecutionResult

from sqlalchemy import desc

core_bp = Blueprint('core_bp', __name__)

# ********************************
# ROUTES
# ********************************
@core_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':

        # --- PROTECT POST REQUEST ---
        if not current_user.is_authenticated: # Manual check as decorator applies to whole function
             flash('You must be logged in to add references.', 'warning')
             return redirect(url_for('auth_bp.login', next=request.url))
        # --- END PROTECTION ---


    # Get user's data if logged in
    user_test_runs = []
    active_test_runs = []
    stats = {}
    recent_activity = []
    
    if current_user.is_authenticated:
        from models.model_Endpoints import Endpoint
        from models.model_APIChain import APIChain
        from sqlalchemy import func, and_
        from datetime import datetime, timedelta
        
        # Get user's recent test runs
        user_test_runs = TestRun.query.filter_by(user_id=current_user.id).order_by(desc(TestRun.created_at)).limit(5).all()
        
        # Get active test runs (running, pending, paused)
        active_test_runs = TestRun.query.filter(
            TestRun.user_id == current_user.id,
            TestRun.status.in_(['running', 'pending', 'paused'])
        ).order_by(desc(TestRun.created_at)).limit(3).all()
        
        # Generate execution engine statistics
        total_executed = ExecutionResult.query.join(ExecutionSession).join(TestRun).filter(
            TestRun.user_id == current_user.id
        ).count()
        
        successful_executed = ExecutionResult.query.join(ExecutionSession).join(TestRun).filter(
            TestRun.user_id == current_user.id,
            ExecutionResult.success == True
        ).count()
        
        active_sessions = ExecutionSession.query.join(TestRun).filter(
            TestRun.user_id == current_user.id,
            ExecutionSession.state.in_(['pending', 'running', 'paused'])
        ).count()
        
        # Calculate average response time from recent executions (last 24h)
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        avg_response = db.session.query(func.avg(ExecutionResult.response_time_ms)).join(ExecutionSession).join(TestRun).filter(
            TestRun.user_id == current_user.id,
            ExecutionResult.executed_at >= recent_cutoff,
            ExecutionResult.response_time_ms.isnot(None)
        ).scalar()
        
        stats = {
            'total_test_runs': TestRun.query.filter_by(user_id=current_user.id).count(),
            'total_test_suites': TestSuite.query.filter_by(user_id=current_user.id).count(),
            'total_endpoints': Endpoint.query.filter_by(user_id=current_user.id).count(),
            'total_chains': APIChain.query.filter_by(user_id=current_user.id).count(),
            'total_test_cases_executed': total_executed,
            'successful_executions': successful_executed,
            'overall_success_rate': successful_executed / total_executed if total_executed > 0 else 0,
            'active_executions': active_sessions,
            'avg_response_time_ms': avg_response or 0
        }
        
        # Generate recent activity
        recent_activity = []
        
        # Recent test runs
        for run in user_test_runs[:3]:
            activity_type = 'success' if run.status == 'completed' else 'info' if run.status == 'running' else 'warning'
            icon = 'fas fa-check-circle' if run.status == 'completed' else 'fas fa-play' if run.status == 'running' else 'fas fa-clock'
            
            recent_activity.append({
                'type': activity_type,
                'icon': icon,
                'title': f"Test run {'completed' if run.status == 'completed' else 'started'}: {run.name or 'Unnamed'}",
                'time_ago': _time_ago(run.created_at)
            })
        
        # Recent test suites
        recent_suites = TestSuite.query.filter_by(user_id=current_user.id).order_by(desc(TestSuite.created_at)).limit(2).all()
        for suite in recent_suites:
            recent_activity.append({
                'type': 'success',
                'icon': 'fas fa-plus',
                'title': f"Created test suite: {suite.description[:50]}",
                'time_ago': _time_ago(suite.created_at)
            })
        
        # Sort activity by time
        recent_activity = sorted(recent_activity, key=lambda x: x['time_ago'], reverse=False)[:5]
        
        # Get execution overview data for the dashboard
        execution_overview = {
            'active_sessions': [],
            'recent_performance': None,
            'strategy_efficiency': {},
            'health_summary': {}
        }
        
        # Get active execution sessions
        active_execution_sessions = ExecutionSession.query.join(TestRun).filter(
            TestRun.user_id == current_user.id,
            ExecutionSession.state.in_(['pending', 'running', 'paused'])
        ).all()
        
        for session in active_execution_sessions:
            execution_overview['active_sessions'].append({
                'test_run_name': session.test_run.name or f'Test Run #{session.test_run.id}',
                'strategy_name': session.strategy_name,
                'health_status': session.health_status,
                'progress_percentage': session.progress_percentage,
                'duration_seconds': session.duration_seconds,
                'requests_per_second': session.requests_per_second or 0
            })
        
        # Get recent performance (24h)
        if total_executed > 0:
            recent_sessions = ExecutionSession.query.join(TestRun).filter(
                TestRun.user_id == current_user.id,
                ExecutionSession.started_at >= recent_cutoff
            ).all()
            
            if recent_sessions:
                execution_overview['recent_performance'] = {
                    'total_cases_executed': sum(s.completed_test_cases for s in recent_sessions),
                    'success_rate': sum(s.success_rate for s in recent_sessions) / len(recent_sessions),
                    'avg_response_time_ms': avg_response or 0,
                    'sessions_count': len(recent_sessions)
                }
        
        # Get health summary
        health_counts = {}
        for session in ExecutionSession.query.join(TestRun).filter(TestRun.user_id == current_user.id).all():
            health = session.health_status or 'unknown'
            health_counts[health] = health_counts.get(health, 0) + 1
        execution_overview['health_summary'] = health_counts

    else:
        execution_overview = {'active_sessions': [], 'recent_performance': None, 'strategy_efficiency': {}, 'health_summary': {}}

    # Get recent test suites for all users (or filter by user if needed)
    recent_test_suites = TestSuite.query.order_by(desc(TestSuite.created_at)).limit(5).all()

    return render_template('index.html', 
                         user_test_runs=user_test_runs,
                         active_test_runs=active_test_runs,
                         recent_test_suites=recent_test_suites,
                         stats=stats,
                         recent_activity=recent_activity,
                         execution_overview=execution_overview)

# Helper function updated to handle timezone-aware datetimes
def _time_ago(dt):
    """Helper function to generate human-readable time ago strings."""
    if not dt:
        return "Unknown"
    
    # Get a timezone-aware "now" in UTC
    now = datetime.now(timezone.utc)
    
    # Ensure the incoming datetime is also timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
        
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

# ********************************
# SERVICES
# ********************************
@core_bp.route('/visual/<effect>')
def visual(effect):
    # List of available visual effects
    valid_effects = ['matrix_rain', 'neon_grid_glitch', 'neon_circles', '8_bit_fire']
    if effect not in valid_effects:
        abort(404)
    # Render the corresponding template, e.g., matrix_rain.html
    return render_template(f"testing_grounds/{effect}.html")

@core_bp.route('/favicon.ico')
def favicon():
    """Simple favicon route to prevent 404 errors"""
    try:
        return send_from_directory('static', 'favicon.ico')
    except:
        # Return empty response if favicon doesn't exist
        return '', 204