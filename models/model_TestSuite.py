from datetime import datetime
from extensions import db
from models.associations import test_suite_cases

class TestSuite(db.Model):
    __tablename__ = 'test_suites'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    behavior = db.Column(db.String(255), nullable=True)

    objective = db.Column(db.TEXT, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now)

    # Relationships
    test_cases = db.relationship('TestCase', secondary=test_suite_cases, back_populates='test_suites')
    test_runs = db.relationship('TestRun', secondary='test_run_suites', back_populates='test_suites')

    
    def __repr__(self):
        return f"<TestSuite {self.id} - {self.description}>"
    
        # ---- ADD THIS METHOD ----
    def to_dict(self):
        """Converts the TestSuite object to a dictionary suitable for JSON serialization."""
        return {
            'id': self.id,
            'description': self.description,
            'behavior': self.behavior,
            'objective': self.objective,
            # Convert datetime to string if needed, or handle in JS
            'created_at': self.created_at.isoformat() if self.created_at else None, 
            # Add other simple fields if needed by your JavaScript
            # Avoid including complex related objects unless necessary and handled properly
            # e.g., 'test_case_ids': [tc.id for tc in self.test_cases]
        }
    # ---- END OF ADDED METHOD ----