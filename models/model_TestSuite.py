from datetime import datetime
from extensions import db

class TestSuite(db.Model):
    __tablename__ = 'test_suites'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    behavior = db.Column(db.String(255), nullable=True)
    attack = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to TestCase
    test_cases = db.relationship(
        'TestCase',
        backref='suite',    # Each TestCase gets a "suite" attribute
        lazy='dynamic',     # Or 'select', or 'subquery', depending on your needs
        cascade='all, delete-orphan'  # If you delete a suite, also delete its test_cases if you want
    )
    
    def __repr__(self):
        return f"<TestSuite {self.id} - {self.description}>"