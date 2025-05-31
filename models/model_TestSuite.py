from datetime import datetime
from extensions import db
from models.associations import test_suite_cases, test_run_suites

class TestSuite(db.Model):
    __tablename__ = 'test_suites'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    behavior = db.Column(db.String(255), nullable=True)
    objective = db.Column(db.TEXT, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now)

    # FK relationship to user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Or False
    user = db.relationship('User', backref=db.backref('test_suites', lazy=True))

    # Relationships
    test_cases = db.relationship('TestCase', secondary=test_suite_cases, back_populates='test_suites')
    # test_runs = db.relationship('TestRun', secondary='test_run_suites', back_populates='test_suites')
    test_runs = db.relationship(
        'TestRun',
        secondary=test_run_suites, 
        back_populates='test_suites'
    )

    def __repr__(self):
        return f"<TestSuite {self.id} - {self.description}>"
    
    def to_dict(self):
        """Converts the TestSuite object to a dictionary suitable for JSON serialization."""
        return {
            'id': self.id,
            'description': self.description,
            'behavior': self.behavior,
            'objective': self.objective,
            'created_at': self.created_at.isoformat() if self.created_at else None, 
            'user_id': self.user_id
        }