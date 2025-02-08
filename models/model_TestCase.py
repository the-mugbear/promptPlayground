from datetime import datetime
from extensions import db
from models.associations import test_suite_cases

class TestCase(db.Model):
    __tablename__ = 'test_cases'
    
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Relationships
    test_suites = db.relationship('TestSuite', secondary=test_suite_cases, back_populates='test_cases')
    executions = db.relationship('TestExecution', back_populates='test_case')

    def __repr__(self):
        return f"<TestCase {self.id} - {self.prompt[:50]}...>"  # Show first 50 chars of prompt