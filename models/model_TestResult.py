from extensions import db

class TestResult(db.Model):
    __tablename__ = 'test_results'

    id = db.Column(db.Integer, primary_key=True)
    test_run_id = db.Column(db.Integer, db.ForeignKey('test_runs.id'), nullable=False)
    test_case_id = db.Column(db.Integer, db.ForeignKey('test_cases.id'), nullable=False)

    # e.g., "pending", "running", "passed", "failed", "skipped"
    status = db.Column(db.String(50), default="pending")

    # The order in which the test case should be run within this test run
    sequence = db.Column(db.Integer, nullable=False)

    # System's response or logs, possibly JSON
    response_data = db.Column(db.Text, nullable=True)

    # Timestamps to track start/end
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    test_run = db.relationship("TestRun", backref="results")
    test_case = db.relationship("TestCase")

    def __repr__(self):
        return (
            f"<TestResult run={self.test_run_id}, "
            f"case={self.test_case_id}, seq={self.sequence}, status={self.status}>"
        )
