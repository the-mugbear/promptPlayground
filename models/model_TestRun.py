# models/model_test_run.py
from extensions import db
from datetime import datetime
from models.associations import test_run_suites

class TestRun(db.Model):
    __tablename__ = 'test_runs'
    
    id = db.Column(db.Integer, primary_key=True)

    # e.g., "Regression Run 2025-06-01"
    name = db.Column(db.String(255), nullable=False)
    # Could be "pending", "running", "paused", "completed", etc.
    status = db.Column(db.String(50), default="pending")
    # Timestamps for tracking
    created_at = db.Column(db.DateTime, default=datetime.now)
    finished_at = db.Column(db.DateTime, nullable=True)

    # Many-to-many: link TestRun <-> TestSuite via test_run_suites association table
    test_suites = db.relationship(
        "TestSuite",
        secondary="test_run_suites",
        backref="test_runs"
    )

    def __repr__(self):
        return f"<TestRun {self.id} {self.name}>"


