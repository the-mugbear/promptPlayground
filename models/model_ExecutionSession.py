# models/model_ExecutionSession.py
"""
ExecutionSession model for the execution engine

Modern implementation optimized for the execution engine with 
real-time metrics and no legacy SQLAlchemy issues.
"""

from extensions import db
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import relationship


class ExecutionSession(db.Model):
    """
    Fresh execution session model managed by the execution engine
    
    Tracks complete execution lifecycle with real-time metrics,
    progress tracking, and adaptive configuration.
    """
    __tablename__ = 'execution_sessions'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to test run
    test_run_id = db.Column(db.Integer, db.ForeignKey('test_run.id'), nullable=False, index=True)
    
    # Execution engine tracking
    execution_id = db.Column(db.String(255), nullable=False, unique=True)
    strategy_name = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False, index=True)
    
    # Progress tracking
    total_test_cases = db.Column(db.Integer, default=0, nullable=False)
    completed_test_cases = db.Column(db.Integer, default=0, nullable=False)
    successful_test_cases = db.Column(db.Integer, default=0, nullable=False)
    failed_test_cases = db.Column(db.Integer, default=0, nullable=False)
    
    # Real-time performance metrics
    avg_response_time_ms = db.Column(db.Integer, nullable=True)
    current_error_rate = db.Column(db.Float, default=0.0)
    requests_per_second = db.Column(db.Float, default=0.0)
    peak_requests_per_second = db.Column(db.Float, default=0.0)
    
    # Adaptive configuration tracking
    initial_config = db.Column(db.JSON, nullable=True)
    current_config = db.Column(db.JSON, nullable=True)
    total_adjustments = db.Column(db.Integer, default=0)
    
    # Execution metadata
    batch_count = db.Column(db.Integer, default=0)
    last_adjustment_at = db.Column(db.DateTime, nullable=True)
    health_status = db.Column(db.String(20), default='unknown')
    
    # Timestamps
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    test_run = relationship('TestRun', back_populates='execution_sessions')
    results = relationship(
        'ExecutionResult',
        back_populates='session',
        cascade='all, delete-orphan',
        lazy='select'
    )
    
    # Properties
    @property
    def progress_percentage(self):
        """Calculate current progress percentage"""
        if self.total_test_cases > 0:
            return min(100, int((self.completed_test_cases / self.total_test_cases) * 100))
        return 0
    
    @property
    def success_rate(self):
        """Calculate current success rate"""
        if self.completed_test_cases > 0:
            return self.successful_test_cases / self.completed_test_cases
        return 0.0
    
    @property
    def error_rate(self):
        """Calculate current error rate"""
        return 1.0 - self.success_rate
    
    @property
    def is_active(self):
        """Check if execution session is currently active"""
        return self.state in ['pending', 'running', 'paused']
    
    @property
    def is_completed(self):
        """Check if execution session is completed"""
        return self.state in ['completed', 'failed', 'cancelled']
    
    @property
    def duration_seconds(self):
        """Calculate execution duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0
    
    @property
    def avg_response_time_seconds(self):
        """Get average response time in seconds"""
        return self.avg_response_time_ms / 1000.0 if self.avg_response_time_ms else 0.0
    
    @property
    def result_count(self):
        """Get number of execution results (modern SQLAlchemy)"""
        return db.session.query(func.count(ExecutionResult.id)).filter(
            ExecutionResult.session_id == self.id
        ).scalar()
    
    # Progress management
    def update_progress(self, completed: int, successful: int, failed: int):
        """Update execution progress"""
        self.completed_test_cases = completed
        self.successful_test_cases = successful
        self.failed_test_cases = failed
        self.updated_at = datetime.utcnow()
        
        # Update health status based on error rate
        if self.error_rate > 0.2:
            self.health_status = 'critical'
        elif self.error_rate > 0.1:
            self.health_status = 'warning'
        elif self.error_rate < 0.05:
            self.health_status = 'excellent'
        else:
            self.health_status = 'good'
    
    def update_metrics(self, avg_response_time_ms: int = None, requests_per_second: float = None):
        """Update real-time performance metrics"""
        if avg_response_time_ms is not None:
            self.avg_response_time_ms = avg_response_time_ms
        
        if requests_per_second is not None:
            self.requests_per_second = requests_per_second
            if requests_per_second > self.peak_requests_per_second:
                self.peak_requests_per_second = requests_per_second
        
        self.updated_at = datetime.utcnow()
    
    def update_config(self, config_dict: dict):
        """Update current adaptive configuration"""
        self.current_config = config_dict
        self.updated_at = datetime.utcnow()
    
    def record_adjustment(self):
        """Record that a rate adjustment was made"""
        self.total_adjustments += 1
        self.last_adjustment_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def complete_execution(self, final_state: str):
        """Mark execution as completed with final state"""
        self.state = final_state
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    # Statistics
    def get_real_time_stats(self):
        """Get comprehensive real-time statistics"""
        return {
            'session_id': self.id,
            'execution_id': self.execution_id,
            'test_run_id': self.test_run_id,
            'strategy_name': self.strategy_name,
            'state': self.state,
            'health_status': self.health_status,
            
            # Progress
            'progress': {
                'total_test_cases': self.total_test_cases,
                'completed_test_cases': self.completed_test_cases,
                'successful_test_cases': self.successful_test_cases,
                'failed_test_cases': self.failed_test_cases,
                'progress_percentage': self.progress_percentage,
                'success_rate': self.success_rate,
                'error_rate': self.error_rate
            },
            
            # Performance
            'performance': {
                'avg_response_time_ms': self.avg_response_time_ms,
                'avg_response_time_seconds': self.avg_response_time_seconds,
                'requests_per_second': self.requests_per_second,
                'peak_requests_per_second': self.peak_requests_per_second,
                'current_error_rate': self.current_error_rate
            },
            
            # Timing
            'timing': {
                'started_at': self.started_at.isoformat(),
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'duration_seconds': self.duration_seconds
            },
            
            # Configuration
            'configuration': {
                'initial_config': self.initial_config,
                'current_config': self.current_config,
                'total_adjustments': self.total_adjustments,
                'last_adjustment_at': self.last_adjustment_at.isoformat() if self.last_adjustment_at else None
            },
            
            # Metadata
            'metadata': {
                'batch_count': self.batch_count,
                'result_count': self.result_count,
                'is_active': self.is_active,
                'is_completed': self.is_completed
            }
        }
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'test_run_id': self.test_run_id,
            'execution_id': self.execution_id,
            'strategy_name': self.strategy_name,
            'state': self.state,
            'health_status': self.health_status,
            'total_test_cases': self.total_test_cases,
            'completed_test_cases': self.completed_test_cases,
            'successful_test_cases': self.successful_test_cases,
            'failed_test_cases': self.failed_test_cases,
            'progress_percentage': self.progress_percentage,
            'success_rate': self.success_rate,
            'error_rate': self.error_rate,
            'avg_response_time_ms': self.avg_response_time_ms,
            'requests_per_second': self.requests_per_second,
            'peak_requests_per_second': self.peak_requests_per_second,
            'current_config': self.current_config,
            'total_adjustments': self.total_adjustments,
            'started_at': self.started_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'is_active': self.is_active,
            'is_completed': self.is_completed,
            'result_count': self.result_count
        }
    
    @classmethod
    def create_from_controller(cls, test_run_id: int, execution_controller):
        """Create execution session from execution controller"""
        session = cls(
            test_run_id=test_run_id,
            execution_id=execution_controller.execution_id,
            strategy_name=execution_controller.strategy.name,
            state=execution_controller.state.value,
            total_test_cases=execution_controller.total_cases,
            initial_config=execution_controller.config.to_dict()
        )
        return session
    
    def __repr__(self):
        return (f"<ExecutionSession id={self.id}, execution_id='{self.execution_id}', "
                f"strategy='{self.strategy_name}', state='{self.state}', "
                f"progress={self.completed_test_cases}/{self.total_test_cases}>")


class ExecutionResult(db.Model):
    """
    Fresh execution result model for individual test case results
    
    Simplified model focused on essential execution data with
    optional detailed information for debugging.
    """
    __tablename__ = 'execution_results'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Session reference
    session_id = db.Column(db.Integer, db.ForeignKey('execution_sessions.id'), nullable=False, index=True)
    
    # Test case reference (optional)
    test_case_id = db.Column(db.Integer, db.ForeignKey('test_cases.id'), nullable=True, index=True)
    
    # Execution metadata
    sequence_number = db.Column(db.Integer, nullable=False, index=True)
    iteration_number = db.Column(db.Integer, default=1)
    batch_id = db.Column(db.String(255), nullable=True, index=True)
    
    # Core results
    success = db.Column(db.Boolean, nullable=False, index=True)
    status_code = db.Column(db.Integer, nullable=True)
    response_time_ms = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Optional detailed data
    request_data = db.Column(db.JSON, nullable=True)
    response_data = db.Column(db.JSON, nullable=True)
    
    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    session = relationship('ExecutionSession', back_populates='results')
    test_case = relationship('TestCase', back_populates='execution_results')
    
    # Properties
    @property
    def response_time_seconds(self):
        """Get response time in seconds"""
        return self.response_time_ms / 1000.0 if self.response_time_ms else 0.0
    
    @property
    def duration_seconds(self):
        """Get total execution duration in seconds"""
        if self.started_at and self.executed_at:
            return (self.executed_at - self.started_at).total_seconds()
        return 0.0
    
    def to_dict(self, include_detailed_data=False):
        """Convert to dictionary for API responses"""
        data = {
            'id': self.id,
            'session_id': self.session_id,
            'test_case_id': self.test_case_id,
            'sequence_number': self.sequence_number,
            'iteration_number': self.iteration_number,
            'batch_id': self.batch_id,
            'success': self.success,
            'status_code': self.status_code,
            'response_time_ms': self.response_time_ms,
            'response_time_seconds': self.response_time_seconds,
            'error_message': self.error_message,
            'executed_at': self.executed_at.isoformat(),
            'duration_seconds': self.duration_seconds
        }
        
        if include_detailed_data:
            data.update({
                'request_data': self.request_data,
                'response_data': self.response_data,
                'started_at': self.started_at.isoformat() if self.started_at else None
            })
        
        return data
    
    @classmethod
    def from_task_result(cls, task_result, session_id: int):
        """Create ExecutionResult from TaskResult"""
        return cls(
            session_id=session_id,
            test_case_id=task_result.test_case_id,
            sequence_number=task_result.sequence_num,
            iteration_number=task_result.iteration_num,
            success=task_result.success,
            status_code=task_result.status_code,
            response_time_ms=int(task_result.response_time * 1000) if task_result.response_time else None,
            error_message=task_result.error_message,
            started_at=task_result.started_at,
            executed_at=task_result.completed_at,
            request_data={
                'execution_id': task_result.execution_id,
                'retry_count': task_result.retry_count
            } if task_result.execution_id else None,
            response_data={
                'body': task_result.response_body,
                'headers': task_result.response_headers
            } if task_result.response_body or task_result.response_headers else None
        )
    
    def __repr__(self):
        return (f"<ExecutionResult id={self.id}, session={self.session_id}, "
                f"test_case={self.test_case_id}, seq={self.sequence_number}, "
                f"success={self.success}, status={self.status_code}>")


# Import at the end to avoid circular imports
from .model_TestCase import TestCase