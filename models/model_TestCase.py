from datetime import datetime
from extensions import db

class TestCase(db.Model):
    __tablename__ = 'test_cases'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    suite_id = db.Column(db.Integer, db.ForeignKey('test_suites.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TestCase {self.id} - {self.description}>"