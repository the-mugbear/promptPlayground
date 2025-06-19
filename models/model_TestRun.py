# models/model_TestRun.py
"""
TestRun model optimized for the execution engine

This model is designed from the ground up for the new execution engine
with no legacy baggage and modern SQLAlchemy patterns.
"""

from extensions import db
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import relationship


class TestRun(db.Model):
    """
    Modern TestRun model - pure configuration with execution engine integration
    
    This model focuses solely on configuration and delegates all execution
    state to the ExecutionSession model managed by the execution engine.
    """
    __tablename__ = 'test_run'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic information
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Target configuration (either endpoint OR chain)
    target_type = db.Column(db.String(20), nullable=False, index=True)  # 'endpoint' or 'chain'
    endpoint_id = db.Column(db.Integer, db.ForeignKey('endpoints.id'), nullable=True, index=True)
    chain_id = db.Column(db.Integer, db.ForeignKey('api_chains.id'), nullable=True, index=True)

    # Execution configuration (JSON for flexibility)
    execution_config = db.Column(db.JSON, nullable=True)

    # Simple status tracking
    status = db.Column(db.String(50), default='not_started', nullable=False)
    # Possible values: 'not_started', 'running', 'paused', 'completed', 'failed', 'cancelled'

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships (using modern SQLAlchemy patterns)
    user = relationship('User', backref='test_runs')
    endpoint = relationship('Endpoint', back_populates='test_runs')
    chain = relationship('APIChain', back_populates='test_runs')
    
    # Test suites (many-to-many)
    test_suites = relationship(
        'TestSuite',
        secondary='test_run_suites',
        back_populates='test_runs',
        lazy='select'
    )
    
    # Execution sessions (one-to-many, managed by execution engine)
    execution_sessions = relationship(
        'ExecutionSession',
        back_populates='test_run',
        cascade='all, delete-orphan',
        lazy='select'
    )

    # Properties for execution engine integration
    @property
    def current_execution_session(self):
        """Get the currently active execution session"""
        return db.session.query(ExecutionSession).filter(
            ExecutionSession.test_run_id == self.id,
            ExecutionSession.state.in_(['pending', 'running', 'paused'])
        ).first()

    @property
    def latest_execution_session(self):
        """Get the most recent execution session"""
        return db.session.query(ExecutionSession).filter(
            ExecutionSession.test_run_id == self.id
        ).order_by(ExecutionSession.started_at.desc()).first()

    @property
    def execution_count(self):
        """Get total number of execution sessions"""
        return db.session.query(func.count(ExecutionSession.id)).filter(
            ExecutionSession.test_run_id == self.id
        ).scalar()

    @property
    def successful_execution_count(self):
        """Get number of successful execution sessions"""
        return db.session.query(func.count(ExecutionSession.id)).filter(
            ExecutionSession.test_run_id == self.id,
            ExecutionSession.state == 'completed'
        ).scalar()

    @property
    def progress_percentage(self):
        """Get current progress percentage from active session"""
        session = self.current_execution_session
        return session.progress_percentage if session else 0

    @property
    def is_active(self):
        """Check if test run has an active execution session"""
        return self.current_execution_session is not None

    @property
    def total_executions(self):
        """Get total number of execution sessions (alias for execution_count)"""
        return self.execution_count


    # Configuration management
    def get_execution_config(self):
        """Get unified execution configuration with defaults"""
        config = self.execution_config.copy() if self.execution_config else {}
        
        # Set modern defaults optimized for execution engine
        config.setdefault('strategy', 'adaptive')
        config.setdefault('batch_size', 4)
        config.setdefault('concurrency', 2)
        config.setdefault('delay_between_requests', 0.5)
        config.setdefault('auto_adjust', True)
        config.setdefault('error_threshold', 0.1)
        config.setdefault('execution_mode', 'production')
        config.setdefault('max_retries', 2)
        config.setdefault('timeout', 30)
        config.setdefault('iterations', 1)
        
        return config

    def update_execution_config(self, updates: dict):
        """Update execution configuration"""
        current_config = self.get_execution_config()
        current_config.update(updates)
        self.execution_config = current_config
        self.updated_at = datetime.utcnow()

    def uses_execution_engine(self):
        """Always use execution engine in fresh implementation"""
        return True


    # Target information helpers
    def get_target(self):
        """Get the target object (endpoint or chain)"""
        if self.target_type == 'endpoint':
            return self.endpoint
        elif self.target_type == 'chain':
            return self.chain
        return None

    def get_target_name(self):
        """Get a display name for the target"""
        target = self.get_target()
        if target:
            return getattr(target, 'name', f'{self.target_type.title()} #{target.id}')
        return 'Unknown Target'

    def get_target_description(self):
        """Get a description of the target"""
        if self.target_type == 'endpoint' and self.endpoint:
            return f"{self.endpoint.method} {self.endpoint.base_url}{self.endpoint.path}"
        elif self.target_type == 'chain' and self.chain:
            # Use scalar count to avoid SQLAlchemy issues
            step_count = db.session.query(func.count('*')).select_from(
                db.session.query(APIChainStep).filter(APIChainStep.chain_id == self.chain.id).subquery()
            ).scalar()
            return f"Chain with {step_count} steps"
        return 'No target configured'

    def get_test_case_count(self):
        """Get total number of test cases from all suites (avoiding duplicates)"""
        if not self.test_suites:
            return 0
        
        suite_ids = [suite.id for suite in self.test_suites]
        print(f"DEBUG TestRun {self.id}: Counting test cases for suites: {suite_ids}")
        
        # Debug: count per suite using the relationship
        total_from_relationships = 0
        for suite in self.test_suites:
            count = len(suite.test_cases)
            total_from_relationships += count
            print(f"DEBUG TestRun {self.id}: Suite {suite.id} ({suite.description}) has {count} test cases")
        
        print(f"DEBUG TestRun {self.id}: Total from relationships (with potential duplicates): {total_from_relationships}")
        
        # Use a simpler approach: collect unique test case IDs from the loaded relationships
        unique_test_case_ids = set()
        for suite in self.test_suites:
            for test_case in suite.test_cases:
                unique_test_case_ids.add(test_case.id)
        
        unique_count = len(unique_test_case_ids)
        print(f"DEBUG TestRun {self.id}: Unique test case IDs: {sorted(unique_test_case_ids)}")
        print(f"DEBUG TestRun {self.id}: Unique test case count: {unique_count}")
        
        return unique_count
    
    def get_total_execution_count(self):
        """Get total number of executions (test cases × iterations)"""
        base_count = self.get_test_case_count()
        if base_count == 0:
            return 0
            
        # Multiply by iterations from execution config
        exec_config = self.get_execution_config()
        iterations = exec_config.get('iterations', 1)
        
        total = base_count * iterations
        print(f"DEBUG TestRun {self.id}: {base_count} test cases × {iterations} iterations = {total} total executions")
        
        return total

    # Status management
    def start_execution(self):
        """Mark test run as started"""
        self.status = 'running'
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def complete_execution(self, final_status='completed'):
        """Mark test run as completed"""
        self.status = final_status
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def pause_execution(self):
        """Mark test run as paused"""
        self.status = 'paused'
        self.updated_at = datetime.utcnow()

    def resume_execution(self):
        """Mark test run as resumed"""
        self.status = 'running'
        self.updated_at = datetime.utcnow()

    # Validation
    def validate_configuration(self):
        """Validate test run configuration"""
        errors = []
        
        # Must have target
        if not self.target_type:
            errors.append("Target type is required")
        elif self.target_type not in ['endpoint', 'chain']:
            errors.append("Target type must be 'endpoint' or 'chain'")
        elif self.target_type == 'endpoint' and not self.endpoint_id:
            errors.append("Endpoint is required when target type is 'endpoint'")
        elif self.target_type == 'chain' and not self.chain_id:
            errors.append("Chain is required when target type is 'chain'")
        
        # Validate mutually exclusive targets
        if self.endpoint_id and self.chain_id:
            errors.append("Cannot specify both endpoint and chain")
        
        # Must have test suites
        if not self.test_suites:
            errors.append("At least one test suite is required")
        elif self.get_test_case_count() == 0:
            errors.append("Test suites must contain test cases")
        
        # Validate execution configuration
        config = self.get_execution_config()
        if config.get('batch_size', 0) <= 0:
            errors.append("Batch size must be greater than 0")
        if config.get('concurrency', 0) <= 0:
            errors.append("Concurrency must be greater than 0")
        if config.get('delay_between_requests', 0) < 0:
            errors.append("Delay between requests cannot be negative")
        
        return errors

    # Serialization
    def get_status_data(self):
        """Get status data for real-time WebSocket updates"""
        active_session = self.current_execution_session
        
        return {
            'run_id': self.id,
            'status': self.status,
            'progress_percentage': self.progress_percentage,
            'is_active': self.is_active,
            'target_name': self.get_target_name(),
            'execution_count': self.execution_count,
            'current_session': {
                'id': active_session.id,
                'state': active_session.state,
                'strategy_name': active_session.strategy_name,
                'progress_percentage': active_session.progress_percentage,
                'health_status': active_session.health_status,
                'completed_test_cases': active_session.completed_test_cases,
                'total_test_cases': active_session.total_test_cases,
                'success_rate': active_session.success_rate
            } if active_session else None,
            'timestamp': datetime.utcnow().isoformat()
        }

    def to_dict(self, include_sessions=False):
        """Convert to dictionary for API responses"""
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'user_id': self.user_id,
            'target_type': self.target_type,
            'endpoint_id': self.endpoint_id,
            'chain_id': self.chain_id,
            'execution_config': self.execution_config,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'target_name': self.get_target_name(),
            'target_description': self.get_target_description(),
            'test_case_count': self.get_test_case_count(),
            'total_execution_count': self.get_total_execution_count(),
            'progress_percentage': self.progress_percentage,
            'is_active': self.is_active,
            'execution_count': self.execution_count,
            'successful_execution_count': self.successful_execution_count,
            'uses_execution_engine': True  # Always true in fresh implementation
        }

        if include_sessions:
            data['execution_sessions'] = [
                session.to_dict() for session in self.execution_sessions
            ]

        return data

    def __repr__(self):
        return f"<TestRun id={self.id}, name='{self.name}', status='{self.status}', target_type='{self.target_type}'>"


# Import other models at the end to avoid circular imports
from .model_ExecutionSession import ExecutionSession
from .model_TestSuite import TestSuite
from .model_TestCase import TestCase
from .model_APIChain import APIChain, APIChainStep