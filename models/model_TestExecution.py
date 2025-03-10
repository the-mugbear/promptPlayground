from extensions import db

# A TEST EXECUTION RECORD IS PRODUCED FOR EACH INDIVIDUAL TEST CASE THAT COMPRISES A TEST RUN
# THE STATUS BELOW IS INTENDED TO CAPTURE IT'S EXECUTION STATE AND BE REUSED AS IT'S DISPOSITION STATE
class TestExecution(db.Model):
    __tablename__ = 'test_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    # Reference to TestRunAttempt now
    test_run_attempt_id = db.Column(
        db.Integer, 
        db.ForeignKey('test_run_attempts.id', name='fk_test_execution_run_attempt_id'),
        nullable=False
    )
    test_case_id = db.Column(db.Integer, db.ForeignKey('test_cases.id'), nullable=False)
    
    status = db.Column(db.String(50), default="pending")
    sequence = db.Column(db.Integer, nullable=False)
    response_data = db.Column(db.Text, nullable=True)
    
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    attempt = db.relationship('TestRunAttempt', back_populates='executions')
    test_case = db.relationship('TestCase', back_populates='executions')
    
    def __repr__(self):
        return (
            f"<TestExecution attempt={self.test_run_attempt_id}, "
            f"case={self.test_case_id}, seq={self.sequence}, status={self.status}>"
        )

