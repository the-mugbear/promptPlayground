# routes/reports_new.py
from flask import Blueprint, render_template, jsonify, request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import selectinload, joinedload

# Import models
from models.model_Endpoints import Endpoint
from models.model_TestRun import TestRun
from models.model_TestExecution import TestExecution
from models.model_TestRunAttempt import TestRunAttempt
from models.model_TestCase import TestCase
from models.model_APIChain import APIChain, APIChainStep
from extensions import db

reports_bp = Blueprint('reports_bp', __name__, url_prefix='/reports')

@reports_bp.route('/dashboard')
def dashboard():
    """Main dashboard view"""
    return render_template('reports/dashboard.html')

@reports_bp.route('/endpoint/<int:endpoint_id>')
def endpoint_report(endpoint_id):
    """Endpoint-specific report view"""
    endpoint = Endpoint.query.get_or_404(endpoint_id)
    return render_template('reports/endpoint_report.html', endpoint=endpoint)

@reports_bp.route('/api/overview')
def api_overview():
    """Get high-level dashboard metrics"""
    time_range = request.args.get('time_range', '30')  # days
    target_type = request.args.get('target_type', 'all')  # all, endpoint, chain
    
    # Base query with time filter
    if time_range != 'all':
        cutoff_date = datetime.utcnow() - timedelta(days=int(time_range))
        query = TestExecution.query.filter(TestExecution.started_at >= cutoff_date)
    else:
        query = TestExecution.query
    
    # Filter by target type
    if target_type == 'endpoint':
        query = query.filter(TestExecution.request_method != 'CHAIN')
    elif target_type == 'chain':
        query = query.filter(TestExecution.request_method == 'CHAIN')
    
    # Get all executions
    executions = query.all()
    
    # Calculate metrics
    total_tests = len(executions)
    passed_tests = len([e for e in executions if e.status == 'passed'])
    failed_tests = len([e for e in executions if e.status == 'failed'])
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    # Average duration
    durations = [e.request_duration_ms for e in executions if e.request_duration_ms]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Active endpoints/chains count
    if target_type == 'chain':
        active_count = len(set(e.request_payload.get('chain_id') for e in executions 
                              if e.request_payload and e.request_payload.get('chain_id')))
    elif target_type == 'endpoint':
        active_count = len(set(e.attempt.test_run.endpoint_id for e in executions 
                              if e.attempt and e.attempt.test_run and e.attempt.test_run.endpoint_id))
    else:
        endpoint_count = len(set(e.attempt.test_run.endpoint_id for e in executions 
                                if e.attempt and e.attempt.test_run and e.attempt.test_run.endpoint_id))
        chain_count = len(set(e.request_payload.get('chain_id') for e in executions 
                             if e.request_payload and e.request_payload.get('chain_id')))
        active_count = endpoint_count + chain_count
    
    # Calculate period comparison (previous period)
    if time_range != 'all':
        prev_cutoff = cutoff_date - timedelta(days=int(time_range))
        prev_query = TestExecution.query.filter(
            and_(TestExecution.started_at >= prev_cutoff, TestExecution.started_at < cutoff_date)
        )
        
        if target_type == 'endpoint':
            prev_query = prev_query.filter(TestExecution.request_method != 'CHAIN')
        elif target_type == 'chain':
            prev_query = prev_query.filter(TestExecution.request_method == 'CHAIN')
            
        prev_executions = prev_query.all()
        prev_total = len(prev_executions)
        prev_passed = len([e for e in prev_executions if e.status == 'passed'])
        prev_success_rate = (prev_passed / prev_total * 100) if prev_total > 0 else 0
        
        # Calculate changes
        tests_change = ((total_tests - prev_total) / prev_total * 100) if prev_total > 0 else 0
        success_rate_change = success_rate - prev_success_rate
    else:
        tests_change = 0
        success_rate_change = 0
    
    return jsonify({
        'total_tests': total_tests,
        'success_rate': round(success_rate, 1),
        'avg_duration': round(avg_duration, 0),
        'active_endpoints': active_count,
        'changes': {
            'tests': round(tests_change, 1),
            'success_rate': round(success_rate_change, 1),
            'duration': 0,  # TODO: Calculate duration change
            'endpoints': 0  # TODO: Calculate endpoint change
        }
    })

@reports_bp.route('/api/distribution')
def api_distribution():
    """Get test type and status distribution data"""
    time_range = request.args.get('time_range', '30')
    
    if time_range != 'all':
        cutoff_date = datetime.utcnow() - timedelta(days=int(time_range))
        executions = TestExecution.query.filter(TestExecution.started_at >= cutoff_date).all()
    else:
        executions = TestExecution.query.all()
    
    # Separate endpoint vs chain executions
    endpoint_executions = [e for e in executions if e.request_method != 'CHAIN']
    chain_executions = [e for e in executions if e.request_method == 'CHAIN']
    
    # Count by status for each type
    def count_by_status(exec_list):
        return {
            'passed': len([e for e in exec_list if e.status == 'passed']),
            'failed': len([e for e in exec_list if e.status == 'failed']),
            'skipped': len([e for e in exec_list if e.status == 'skipped']),
            'pending_review': len([e for e in exec_list if e.status == 'pending_review'])
        }
    
    return jsonify({
        'endpoint_tests': count_by_status(endpoint_executions),
        'chain_tests': count_by_status(chain_executions),
        'total_endpoints': len(endpoint_executions),
        'total_chains': len(chain_executions)
    })

@reports_bp.route('/api/timeline')
def api_timeline():
    """Get success rate timeline data"""
    time_range = request.args.get('time_range', '30')
    
    if time_range != 'all':
        days = int(time_range)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
    else:
        days = 90  # Default for all-time view
        cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Group executions by date
    timeline_data = []
    
    for i in range(days):
        date = cutoff_date + timedelta(days=i)
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        day_executions = TestExecution.query.filter(
            and_(TestExecution.started_at >= start_date, TestExecution.started_at < end_date)
        ).all()
        
        endpoint_executions = [e for e in day_executions if e.request_method != 'CHAIN']
        chain_executions = [e for e in day_executions if e.request_method == 'CHAIN']
        
        def calc_success_rate(exec_list):
            if not exec_list:
                return 0
            passed = len([e for e in exec_list if e.status == 'passed'])
            return (passed / len(exec_list)) * 100
        
        timeline_data.append({
            'date': start_date.isoformat(),
            'endpoint_success_rate': calc_success_rate(endpoint_executions),
            'chain_success_rate': calc_success_rate(chain_executions),
            'endpoint_count': len(endpoint_executions),
            'chain_count': len(chain_executions)
        })
    
    return jsonify(timeline_data)

@reports_bp.route('/api/top_performers')
def api_top_performers():
    """Get top performing endpoints/chains"""
    metric = request.args.get('metric', 'success_rate')
    time_range = request.args.get('time_range', '30')
    target_type = request.args.get('target_type', 'all')
    
    if time_range != 'all':
        cutoff_date = datetime.utcnow() - timedelta(days=int(time_range))
        executions = TestExecution.query.filter(TestExecution.started_at >= cutoff_date).all()
    else:
        executions = TestExecution.query.all()
    
    # Group by endpoint or chain
    grouped_data = defaultdict(list)
    
    for execution in executions:
        if execution.request_method == 'CHAIN':
            if target_type in ['all', 'chain']:
                chain_id = execution.request_payload.get('chain_id') if execution.request_payload else None
                if chain_id:
                    grouped_data[f'chain_{chain_id}'].append(execution)
        else:
            if target_type in ['all', 'endpoint']:
                endpoint_id = execution.attempt.test_run.endpoint_id if execution.attempt and execution.attempt.test_run else None
                if endpoint_id:
                    grouped_data[f'endpoint_{endpoint_id}'].append(execution)
    
    # Calculate metrics for each group
    results = []
    for key, exec_list in grouped_data.items():
        if len(exec_list) < 5:  # Skip items with too few tests
            continue
            
        total = len(exec_list)
        passed = len([e for e in exec_list if e.status == 'passed'])
        success_rate = (passed / total) * 100
        
        durations = [e.request_duration_ms for e in exec_list if e.request_duration_ms]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Get name
        if key.startswith('chain_'):
            chain_id = int(key.split('_')[1])
            chain = APIChain.query.get(chain_id)
            name = chain.name if chain else f'Chain {chain_id}'
            type_label = 'Chain'
        else:
            endpoint_id = int(key.split('_')[1])
            endpoint = Endpoint.query.get(endpoint_id)
            name = endpoint.name if endpoint else f'Endpoint {endpoint_id}'
            type_label = 'Endpoint'
        
        results.append({
            'id': key,
            'name': name,
            'type': type_label,
            'success_rate': success_rate,
            'execution_count': total,
            'avg_duration': avg_duration
        })
    
    # Sort by requested metric
    if metric == 'success_rate':
        results.sort(key=lambda x: x['success_rate'], reverse=True)
    elif metric == 'execution_count':
        results.sort(key=lambda x: x['execution_count'], reverse=True)
    elif metric == 'avg_duration':
        results.sort(key=lambda x: x['avg_duration'])
    
    return jsonify(results[:10])  # Top 10

@reports_bp.route('/api/problem_areas')
def api_problem_areas():
    """Get problem areas (worst performing endpoints/chains)"""
    metric = request.args.get('metric', 'failure_rate')
    time_range = request.args.get('time_range', '30')
    
    if time_range != 'all':
        cutoff_date = datetime.utcnow() - timedelta(days=int(time_range))
        executions = TestExecution.query.filter(TestExecution.started_at >= cutoff_date).all()
    else:
        executions = TestExecution.query.all()
    
    # Group by endpoint or chain
    grouped_data = defaultdict(list)
    
    for execution in executions:
        if execution.request_method == 'CHAIN':
            chain_id = execution.request_payload.get('chain_id') if execution.request_payload else None
            if chain_id:
                grouped_data[f'chain_{chain_id}'].append(execution)
        else:
            endpoint_id = execution.attempt.test_run.endpoint_id if execution.attempt and execution.attempt.test_run else None
            if endpoint_id:
                grouped_data[f'endpoint_{endpoint_id}'].append(execution)
    
    # Calculate problem metrics
    results = []
    for key, exec_list in grouped_data.items():
        if len(exec_list) < 3:  # Skip items with too few tests
            continue
            
        total = len(exec_list)
        failed = len([e for e in exec_list if e.status == 'failed'])
        errors = len([e for e in exec_list if e.error_message])
        timeouts = len([e for e in exec_list if 'timeout' in (e.error_message or '').lower()])
        
        failure_rate = (failed / total) * 100
        error_frequency = (errors / total) * 100
        timeout_rate = (timeouts / total) * 100
        
        # Get name
        if key.startswith('chain_'):
            chain_id = int(key.split('_')[1])
            chain = APIChain.query.get(chain_id)
            name = chain.name if chain else f'Chain {chain_id}'
            type_label = 'Chain'
        else:
            endpoint_id = int(key.split('_')[1])
            endpoint = Endpoint.query.get(endpoint_id)
            name = endpoint.name if endpoint else f'Endpoint {endpoint_id}'
            type_label = 'Endpoint'
        
        results.append({
            'id': key,
            'name': name,
            'type': type_label,
            'failure_rate': failure_rate,
            'error_frequency': error_frequency,
            'timeout_rate': timeout_rate,
            'total_executions': total
        })
    
    # Sort by requested metric
    if metric == 'failure_rate':
        results.sort(key=lambda x: x['failure_rate'], reverse=True)
    elif metric == 'error_frequency':
        results.sort(key=lambda x: x['error_frequency'], reverse=True)
    elif metric == 'timeout_rate':
        results.sort(key=lambda x: x['timeout_rate'], reverse=True)
    
    return jsonify(results[:10])  # Top 10 problems

@reports_bp.route('/api/status_codes')
def api_status_codes():
    """Get status code distribution"""
    time_range = request.args.get('time_range', '30')
    
    if time_range != 'all':
        cutoff_date = datetime.utcnow() - timedelta(days=int(time_range))
        executions = TestExecution.query.filter(TestExecution.started_at >= cutoff_date).all()
    else:
        executions = TestExecution.query.all()
    
    # Count status codes
    status_counts = Counter()
    for execution in executions:
        if execution.status_code:
            # Group status codes into ranges
            code = execution.status_code
            if 200 <= code < 300:
                status_counts['2xx Success'] += 1
            elif 300 <= code < 400:
                status_counts['3xx Redirect'] += 1
            elif 400 <= code < 500:
                status_counts['4xx Client Error'] += 1
            elif 500 <= code < 600:
                status_counts['5xx Server Error'] += 1
            else:
                status_counts['Other'] += 1
    
    return jsonify(dict(status_counts))

@reports_bp.route('/api/recent_activity')
def api_recent_activity():
    """Get recent test activity"""
    limit = request.args.get('limit', 20)
    
    recent_executions = TestExecution.query.order_by(
        desc(TestExecution.started_at)
    ).limit(int(limit)).all()
    
    activity = []
    for execution in recent_executions:
        if execution.request_method == 'CHAIN':
            title = f"Chain execution: {execution.request_payload.get('chain_name', 'Unknown')}"
            icon_class = 'fas fa-sitemap'
        else:
            endpoint_name = 'Unknown'
            if execution.attempt and execution.attempt.test_run and execution.attempt.test_run.endpoint:
                endpoint_name = execution.attempt.test_run.endpoint.name
            title = f"Endpoint test: {endpoint_name}"
            icon_class = 'fas fa-plug'
        
        activity.append({
            'title': title,
            'status': execution.status,
            'created_at': execution.started_at.isoformat() if execution.started_at else '',
            'duration': execution.request_duration_ms,
            'icon_class': icon_class
        })
    
    return jsonify(activity)

@reports_bp.route('/api/chains/analysis')
def api_chain_analysis():
    """Get detailed chain analysis"""
    chain_id = request.args.get('chain_id')
    time_range = request.args.get('time_range', '30')
    
    if time_range != 'all':
        cutoff_date = datetime.utcnow() - timedelta(days=int(time_range))
        query = TestExecution.query.filter(
            and_(TestExecution.started_at >= cutoff_date, TestExecution.request_method == 'CHAIN')
        )
    else:
        query = TestExecution.query.filter(TestExecution.request_method == 'CHAIN')
    
    if chain_id and chain_id != 'all':
        # Filter by specific chain
        executions = [e for e in query.all() 
                     if e.request_payload and e.request_payload.get('chain_id') == int(chain_id)]
    else:
        executions = query.all()
    
    # Analyze chain step performance
    step_analysis = defaultdict(lambda: {'success': 0, 'failure': 0, 'total': 0})
    
    for execution in executions:
        if execution.request_payload and execution.request_payload.get('step_results'):
            for step_result in execution.request_payload['step_results']:
                step_order = step_result.get('step_order', 0)
                step_name = step_result.get('step_name', f'Step {step_order}')
                step_success = step_result.get('success', False)
                
                step_analysis[step_name]['total'] += 1
                if step_success:
                    step_analysis[step_name]['success'] += 1
                else:
                    step_analysis[step_name]['failure'] += 1
    
    # Convert to list format for charting
    step_data = []
    for step_name, data in step_analysis.items():
        success_rate = (data['success'] / data['total'] * 100) if data['total'] > 0 else 0
        step_data.append({
            'step_name': step_name,
            'success_rate': success_rate,
            'total_executions': data['total'],
            'success_count': data['success'],
            'failure_count': data['failure']
        })
    
    # Sort by step order if possible
    step_data.sort(key=lambda x: x['step_name'])
    
    return jsonify({
        'step_analysis': step_data,
        'total_chain_executions': len(executions),
        'overall_success_rate': (len([e for e in executions if e.status == 'passed']) / len(executions) * 100) if executions else 0
    })

@reports_bp.route('/api/endpoint/<int:endpoint_id>/overview')
def api_endpoint_overview(endpoint_id):
    """Get endpoint-specific overview metrics"""
    time_range = request.args.get('time_range', '30')
    
    # Get executions for this endpoint (both direct and via chains)
    if time_range != 'all':
        cutoff_date = datetime.utcnow() - timedelta(days=int(time_range))
        direct_executions = TestExecution.query.join(TestRunAttempt).join(TestRun).filter(
            and_(TestRun.endpoint_id == endpoint_id, TestExecution.started_at >= cutoff_date, TestExecution.request_method != 'CHAIN')
        ).all()
        
        # Chain executions that use this endpoint
        chain_executions = TestExecution.query.filter(
            and_(TestExecution.started_at >= cutoff_date, TestExecution.request_method == 'CHAIN')
        ).all()
    else:
        direct_executions = TestExecution.query.join(TestRunAttempt).join(TestRun).filter(
            and_(TestRun.endpoint_id == endpoint_id, TestExecution.request_method != 'CHAIN')
        ).all()
        
        # Chain executions that use this endpoint
        chain_executions = TestExecution.query.filter(TestExecution.request_method == 'CHAIN').all()
    
    # Filter chain executions that used this endpoint
    endpoint_chain_executions = []
    for execution in chain_executions:
        if execution.request_payload and execution.request_payload.get('step_results'):
            for step in execution.request_payload['step_results']:
                if step.get('endpoint_id') == endpoint_id:
                    endpoint_chain_executions.append(execution)
                    break
    
    all_executions = direct_executions + endpoint_chain_executions
    
    # Calculate metrics
    total_tests = len(all_executions)
    passed_tests = len([e for e in all_executions if e.status == 'passed'])
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    # Average duration
    durations = [e.request_duration_ms for e in all_executions if e.request_duration_ms]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Test runs count
    test_runs = set()
    for execution in direct_executions:
        if execution.attempt and execution.attempt.test_run:
            test_runs.add(execution.attempt.test_run.id)
    
    return jsonify({
        'total_tests': total_tests,
        'direct_tests': len(direct_executions),
        'chain_tests': len(endpoint_chain_executions),
        'success_rate': round(success_rate, 1),
        'avg_duration': round(avg_duration, 0),
        'test_runs': len(test_runs)
    })

@reports_bp.route('/api/endpoint/<int:endpoint_id>/timeline')
def api_endpoint_timeline(endpoint_id):
    """Get endpoint-specific timeline data"""
    time_range = request.args.get('time_range', '30')
    
    if time_range != 'all':
        days = int(time_range)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
    else:
        days = 90
        cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    timeline_data = []
    
    for i in range(days):
        date = cutoff_date + timedelta(days=i)
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        # Direct endpoint executions
        direct_executions = TestExecution.query.join(TestRunAttempt).join(TestRun).filter(
            and_(
                TestRun.endpoint_id == endpoint_id,
                TestExecution.started_at >= start_date,
                TestExecution.started_at < end_date,
                TestExecution.request_method != 'CHAIN'
            )
        ).all()
        
        # Calculate success rate and average duration
        def calc_metrics(exec_list):
            if not exec_list:
                return {'success_rate': 0, 'avg_duration': 0, 'count': 0}
            
            passed = len([e for e in exec_list if e.status == 'passed'])
            success_rate = (passed / len(exec_list)) * 100
            
            durations = [e.request_duration_ms for e in exec_list if e.request_duration_ms]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            return {
                'success_rate': success_rate,
                'avg_duration': avg_duration,
                'count': len(exec_list)
            }
        
        metrics = calc_metrics(direct_executions)
        
        timeline_data.append({
            'date': start_date.isoformat(),
            'success_rate': metrics['success_rate'],
            'avg_duration': metrics['avg_duration'],
            'test_count': metrics['count']
        })
    
    return jsonify(timeline_data)

@reports_bp.route('/api/endpoint/<int:endpoint_id>/recent_runs')
def api_endpoint_recent_runs(endpoint_id):
    """Get recent test runs for an endpoint"""
    limit = request.args.get('limit', 10)
    
    recent_runs = TestRun.query.filter_by(endpoint_id=endpoint_id).order_by(
        desc(TestRun.created_at)
    ).limit(int(limit)).all()
    
    runs_data = []
    for run in recent_runs:
        # Calculate run metrics
        total_executions = 0
        passed_executions = 0
        
        for attempt in run.attempts:
            executions = TestExecution.query.filter_by(test_run_attempt_id=attempt.id).all()
            total_executions += len(executions)
            passed_executions += len([e for e in executions if e.status == 'passed'])
        
        success_rate = (passed_executions / total_executions * 100) if total_executions > 0 else 0
        
        runs_data.append({
            'id': run.id,
            'name': run.name,
            'status': run.status,
            'created_at': run.created_at.isoformat() if run.created_at else '',
            'total_tests': total_executions,
            'passed_tests': passed_executions,
            'success_rate': round(success_rate, 1)
        })
    
    return jsonify(runs_data)