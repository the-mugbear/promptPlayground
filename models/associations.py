from extensions import db
from flask_sqlalchemy import SQLAlchemy


# bridges between testsuite and testcase
test_suite_cases = db.Table(
    'test_suite_cases',
    db.Column('test_suite_id', db.Integer, db.ForeignKey('test_suites.id'), nullable=False),
    db.Column('test_case_id', db.Integer, db.ForeignKey('test_cases.id'), nullable=False),
    db.PrimaryKeyConstraint('test_suite_id', 'test_case_id', name='pk_test_suite_cases')
)

# bridges between testrun and testsuite
test_run_suites = db.Table(
    'test_run_suites',
    db.Column('test_run_id', db.Integer, db.ForeignKey('test_runs.id'), nullable=False),
    db.Column('test_suite_id', db.Integer, db.ForeignKey('test_suites.id'), nullable=False),
    db.PrimaryKeyConstraint('test_run_id', 'test_suite_id', name='pk_test_run_suites')
)