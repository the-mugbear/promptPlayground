# models/model_test_run.py
from extensions import db
from datetime import datetime
from models.associations import test_run_suites
from models.model_TestExecution import TestExecution

class TestRun(db.Model):
    __tablename__ = 'test_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    # e.g., "Regression Run 2025-06-01"
    name = db.Column(db.String(255), nullable=False)
    # Timestamps for tracking
    created_at = db.Column(db.DateTime, default=datetime.now)
    finished_at = db.Column(db.DateTime, nullable=True)
    # This is the overall status of a test run and not an individual test case
    # Could be "pending", "running", "paused", "completed", etc.
    status = db.Column(db.String(50), default="pending")
    current_sequence = db.Column(db.Integer, default=0)

    # Add endpoint relationship
    endpoint_id = db.Column(db.Integer, db.ForeignKey('endpoints.id'), nullable=False)
    endpoint = db.relationship('Endpoint', back_populates='test_runs')
    
    # Other relationships
    test_suites = db.relationship('TestSuite', secondary=test_run_suites, back_populates='test_runs')
    executions = db.relationship('TestExecution', back_populates='test_run', 
                               order_by='TestExecution.sequence',
                               cascade='all, delete-orphan')
    
    def get_next_test_case(self):
        return (TestExecution.query
                .filter_by(test_run_id=self.id)
                .filter_by(status='pending')
                .order_by(TestExecution.sequence)
                .first())

    def resume_from_sequence(self):
        last_executed = (TestExecution.query
                        .filter_by(test_run_id=self.id)
                        .filter(TestExecution.status.in_(['passed', 'failed', 'skipped']))
                        .order_by(TestExecution.sequence.desc())
                        .first())
        return (last_executed.sequence + 1) if last_executed else 0

    def __repr__(self):
        return f"<TestRun id={self.id}, status={self.status}, endpoint={self.endpoint_id}>"