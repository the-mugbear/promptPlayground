from datetime import datetime
from extensions import db
from models.associations import test_suite_cases

class TestSuite(db.Model):
    __tablename__ = 'test_suites'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    behavior = db.Column(db.String(255), nullable=True)
    # originally inspired by JPLHughes' Best of N dataset I believe the transformations will carry this data instead
    # attack = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Relationships
    test_cases = db.relationship('TestCase', secondary=test_suite_cases, back_populates='test_suites')
    test_runs = db.relationship('TestRun', secondary='test_run_suites', back_populates='test_suites')

    
    def __repr__(self):
        return f"<TestSuite {self.id} - {self.description}>"