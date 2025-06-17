from extensions import db
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import Enum as SQLAlchemyEnum
from models.associations import test_run_suites
from enum import Enum as PythonEnum 
import datetime

class TestRun(db.Model):
    __tablename__ = 'test_run'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, default=lambda: f"Test Run - {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}") 
    description = db.Column(db.Text, nullable=True) 

    # Timestamps 
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Flag to assist application 
    run_serially = db.Column(db.Boolean, default=False, nullable=False) # server_default removed for broader DB compatibility unless specifically needed for PostgreSQL

    # Configuration for the run 
    iterations = db.Column(db.Integer, default=1, nullable=False)
    delay_between_requests = db.Column(db.Float, default=0.0, nullable=False)

    # --- NEW FIELDS FOR TRANSFORMATIONS AT RUN LEVEL ---
    # {
    #     "name": "reverse_string",
    #     "params": {}
    # },
    # {
    #     "name": "prepend_text",
    #     "params": {"text_to_prepend": "UserPrefix: "}
    # }
    run_transformations = db.Column(db.JSON, nullable=True)
    
    # --- HEADER OVERRIDES FOR RUN-SPECIFIC AUTHENTICATION ---
    # Allows users to override specific headers (especially Authorization) for this test run
    # Format: {"Authorization": "Bearer new-token", "X-API-Key": "updated-key"}
    header_overrides = db.Column(db.JSON, nullable=True) 

    # --- Status Field ---
    # Default to 'not_started'.
    # Documented possibilities: 'not_started', 'pending', 'running', 'pausing',
    # 'paused', 'cancelling', 'cancelled', 'completed', 'failed'
    status = db.Column(db.String(50), default='not_started', nullable=False)

    # --- New fields for WebSocket-based progress and control (from your version) ---
    progress_current = db.Column(db.Integer, default=0, nullable=False)
    progress_total = db.Column(db.Integer, default=0, nullable=False)
    celery_task_id = db.Column(db.String(255), nullable=True)

    # --- Target Configuration: Either endpoint OR chain ---
    target_type = db.Column(db.String(20), nullable=False, default='endpoint')  # 'endpoint' or 'chain'
    
    # --- Relationships ---
    endpoint = db.relationship('Endpoint', back_populates="test_runs") # Ensure Endpoint model has 'test_runs' relationship
    endpoint_id = db.Column(
        db.Integer,
        db.ForeignKey("endpoints.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Chain relationship
    chain = db.relationship('APIChain', back_populates="test_runs") 
    chain_id = db.Column(
        db.Integer,
        db.ForeignKey("api_chains.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    # TestRunAttempt is looking for via back_populates='attempts'
    attempts = db.relationship(
        'TestRunAttempt',
        back_populates='test_run',
        cascade='all, delete-orphan',
        lazy=True
    )
    test_suites = db.relationship(
        'TestSuite',
        secondary=test_run_suites, # <-- USE IMPORTED TABLE
        lazy='subquery',
        back_populates='test_runs' # This will populate 'test_runs' on TestSuite model
    )

    # User (from your version, slight modification for consistency)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Changed nullable to False as user is likely required
    user = db.relationship('User', backref=db.backref('test_runs_owned', lazy=True)) # Changed backref name to avoid conflict if 'test_runs' is used elsewhere on User

    # Prompt Filters relationship
    filters = db.relationship(
        'PromptFilter',
        secondary='test_run_filters',  # Uses the string name of the table from associations.py
        backref=db.backref('runs_with_this_filter', lazy=True)
    )

    # Optional notes or summary for the run (my addition)
    notes = db.Column(db.Text, nullable=True)

    # --- Helper property for progress percentage (from your version) ---
    @property
    def progress_percent(self):
        if self.status == 'completed':
            return 100
        if self.progress_total > 0 and self.progress_current is not None:
            current_capped = min(self.progress_current, self.progress_total)
            percent = int((current_capped / self.progress_total) * 100)
            return min(percent, 100)
        return 0

    # --- Helper method to get data for SocketIO events (from your version) ---
    def get_status_data(self):
        return {
            'run_id': self.id,
            'name': self.name,
            'status': self.status,
            'current': self.progress_current,
            'total': self.progress_total,
            'percent': self.progress_percent,
            'celery_task_id': self.celery_task_id,
            'start_time': self.started_at.isoformat() if self.started_at else None, # Changed from start_time to started_at to match column
            'end_time': self.completed_at.isoformat() if self.completed_at else None, # Changed from end_time to completed_at
        }

    def __repr__(self):
        # Using f-string for consistency
        return f"<TestRun id={self.id}, name='{self.name}', status={self.status.value if self.status else 'N/A'}>"

    def get_target_name(self):
        """Helper method to get the name of the target (endpoint or chain)"""
        if self.target_type == 'endpoint' and self.endpoint:
            return self.endpoint.name
        elif self.target_type == 'chain' and self.chain:
            return self.chain.name
        return 'N/A'
    
    def get_target_description(self):
        """Helper method to get a description of the target"""
        if self.target_type == 'endpoint' and self.endpoint:
            return f"{self.endpoint.method} {self.endpoint.base_url}{self.endpoint.path}"
        elif self.target_type == 'chain' and self.chain:
            return f"Chain with {len(self.chain.steps)} steps"
        return 'N/A'

    def to_dict(self): # Added from my previous version, expanded
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'user_id': self.user_id,
            'target_type': self.target_type,
            'endpoint_id': self.endpoint_id,
            'chain_id': self.chain_id,
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'run_serially': self.run_serially,
            'iterations': self.iterations,
            'delay_between_requests': self.delay_between_requests,
            'run_transformations': self.run_transformations,
            'progress_current': self.progress_current,
            'progress_total': self.progress_total,
            'progress_percent': self.progress_percent,
            'celery_task_id': self.celery_task_id,
            'test_suite_ids': [suite.id for suite in self.test_suites],
            'filter_ids': [f.id for f in self.filters], # Assuming PromptFilter has an id
            'target_name': self.get_target_name(),
            'target_description': self.get_target_description(),
            'user_name': self.user.username if self.user else None, # Assuming User has username
            'notes': self.notes
        }