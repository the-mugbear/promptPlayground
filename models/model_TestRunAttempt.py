# models/model_TestRunAttempt.py
from extensions import db
from datetime import datetime

class TestRunAttempt(db.Model):
    __tablename__ = 'test_run_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    test_run_id = db.Column(
        db.Integer, 
        db.ForeignKey('test_runs.id', name='fk_test_run_attempt_test_run_id'),
        nullable=False,
        index=True
    )
    attempt_number = db.Column(db.Integer, nullable=False)
    
    # Timestamps for this attempt
    started_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    status = db.Column(db.String(50), default="pending")
    
    # New field: a sequence counter that resets per attempt
    current_sequence = db.Column(db.Integer, default=0)
    
    # Relationships
    test_run = db.relationship('TestRun', back_populates='attempts')
    executions = db.relationship(
        'TestExecution',
        back_populates='attempt',
        order_by='TestExecution.sequence',
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f"<TestRunAttempt id={self.id}, attempt={self.attempt_number}, status={self.status}, current_sequence={self.current_sequence}>"
