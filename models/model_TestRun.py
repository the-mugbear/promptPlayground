# models/model_TestRun.py
from extensions import db
from datetime import datetime
from models.associations import test_run_suites, test_run_filters

class TestRun(db.Model):
    __tablename__ = 'test_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    status = db.Column(db.String(50), default="pending")
    run_serially = db.Column(db.Boolean, default=False, nullable=False, server_default='false')

    endpoint_id = db.Column(
        db.Integer,
        db.ForeignKey("endpoints.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', backref=db.backref('test_runs', lazy=True))

    endpoint = db.relationship("Endpoint", back_populates="test_runs", passive_deletes=True)
    test_suites = db.relationship('TestSuite', secondary=test_run_suites, back_populates='test_runs')
    
    # Relationship to execution attempts
    attempts = db.relationship('TestRunAttempt', back_populates='test_run', cascade='all, delete-orphan')
    filters = db.relationship('PromptFilter', secondary=test_run_filters, backref='test_runs')
    
    def __repr__(self):
        return f"<TestRun id={self.id}, status={self.status}, endpoint={self.endpoint_id}>"
