from sqlalchemy.dialects.postgresql import JSONB
from extensions import db


# A TEST EXECUTION RECORD IS PRODUCED FOR EACH INDIVIDUAL TEST CASE THAT COMPRISES A TEST RUN
# THE STATUS BELOW IS INTENDED TO CAPTURE IT'S EXECUTION STATE AND BE REUSED AS IT'S DISPOSITION STATE
class TestExecution(db.Model):
    __tablename__ = 'test_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    # Reference to TestRunAttempt now
    test_run_attempt_id = db.Column(
        db.Integer, 
        db.ForeignKey('test_run_attempts.id', name='fk_test_execution_run_attempt_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    test_case_id = db.Column(db.Integer, db.ForeignKey('test_cases.id', ondelete='SET NULL'), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    iteration = db.Column(db.Integer, nullable=True, default=1)

    # What was sent
    processed_prompt = db.Column(db.Text, nullable=True)
    request_payload = db.Column(db.JSON, nullable=True)

    # What was received
    response_data = db.Column(db.Text, nullable=True)
    status_code = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.Text, nullable=True) # Specific errors during request/response handling

    # Outcome
    status = db.Column(db.String(50), default="pending") # 'pass', 'fail', 'error', 'pending'

    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Relationships
    attempt = db.relationship('TestRunAttempt', back_populates='executions')
    test_case = db.relationship('TestCase', back_populates='executions')
    
    def __repr__(self):
        return (
            f"<TestExecution attempt={self.test_run_attempt_id}, "
            f"case={self.test_case_id}, seq={self.sequence}, iter={self.iteration}, status={self.status}>"
        )

