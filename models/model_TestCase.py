from datetime import datetime
from extensions import db
from models.associations import test_suite_cases

# Working on the taxonomy of a prompt
class TestCase(db.Model):
    __tablename__ = 'test_cases'
    
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.String(255), nullable=False)
    transformations = db.Column(db.JSON, nullable=True)
    source = db.Column(db.String(255), nullable=True)
    attack_type = db.Column(db.String(50), nullable=True) # jailbreak / prompt_injection / other
    data_type = db.Column(db.String(50), nullable=True) # text / image / audio
    nist_risk = db.Column(db.String(50), nullable=True)
    reviewed = db.Column(db.Boolean, default=False, nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Relationships
    test_suites = db.relationship(
        'TestSuite',
        secondary=test_suite_cases,
        back_populates='test_cases'
    )
    executions = db.relationship(
        'TestExecution',
        back_populates='test_case',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<TestCase {self.id} - {self.prompt[:50]}...>"  # Show first 50 chars of prompt