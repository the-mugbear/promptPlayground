# models/model_TestRun.py
from extensions import db
from datetime import datetime

# TEST_RUN_STATUSES = [
# 'not_started', 'pending', 'running',
# 'pausing', 'paused', # New statuses for pause/resume
# 'cancelling', 'cancelled', # New statuses for cancellation
# 'completed', 'failed'
# ]


class TestRun(db.Model):
    __tablename__ = 'test_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    
    run_serially = db.Column(db.Boolean, default=False, nullable=False, server_default='false')

    # --- Status Field ---
    # Default to 'not_started'.
    # Documented possibilities: 'not_started', 'pending', 'running', 'pausing',
    # 'paused', 'cancelling', 'cancelled', 'completed', 'failed'
    status = db.Column(db.String(50), default='not_started', nullable=False)

    # ---> New fields for WebSocket-based progress and control <---
    progress_current = db.Column(db.Integer, default=0, nullable=False)
    progress_total = db.Column(db.Integer, default=0, nullable=False)
    celery_task_id = db.Column(db.String(255), nullable=True) # To store the Celery task ID (UUIDs are typically 36 chars)
    
    endpoint_id = db.Column(
        db.Integer,
        db.ForeignKey("endpoints.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', backref=db.backref('test_runs', lazy=True))

    endpoint = db.relationship("Endpoint", back_populates="test_runs", passive_deletes=True)
    test_suites = db.relationship('TestSuite', secondary='test_run_suites', back_populates='test_runs')
    
    # Relationship to execution attempts
    attempts = db.relationship('TestRunAttempt', back_populates='test_run', cascade='all, delete-orphan')
    filters = db.relationship('PromptFilter', secondary='test_run_filters', backref='test_runs')

    # --- Helper property for progress percentage ---
    @property
    def progress_percent(self):
        if self.status == 'completed':
            return 100
        if self.progress_total > 0 and self.progress_current is not None:
            # Ensure progress_current does not exceed progress_total for percentage calculation
            current_capped = min(self.progress_current, self.progress_total)
            percent = int((current_capped / self.progress_total) * 100)
            return min(percent, 100) # Cap at 100%
        return 0

    # --- Helper method to get data for SocketIO events ---
    def get_status_data(self):
        """
        Returns a dictionary of the current status and progress,
        suitable for emitting via SocketIO.
        """
        return {
            'run_id': self.id,
            'name': self.name, # Added for context on the client
            'status': self.status,
            'current': self.progress_current,
            'total': self.progress_total,
            'percent': self.progress_percent,
            'celery_task_id': self.celery_task_id, # Useful for debugging on client
            'start_time': self.start_time.isoformat() if self.start_time else None, # Added for client display
            'end_time': self.end_time.isoformat() if self.end_time else None,     # Added for client display
        }
    
    def __repr__(self):
        return f"<TestRun id={self.id}, status={self.status}, endpoint={self.endpoint_id}>"
