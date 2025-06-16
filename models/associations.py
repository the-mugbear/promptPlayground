from extensions import db

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
    db.Column('test_run_id', db.Integer, db.ForeignKey('test_run.id'), nullable=False),
    db.Column('test_suite_id', db.Integer, db.ForeignKey('test_suites.id'), nullable=False),
    db.PrimaryKeyConstraint('test_run_id', 'test_suite_id', name='pk_test_run_suites')
)

# let a test run have multiple filter rules
test_run_filters = db.Table(
    'test_run_filters',
    db.Column('test_run_id', db.Integer, db.ForeignKey('test_run.id'), nullable=False),
    db.Column('prompt_filter_id', db.Integer, db.ForeignKey('prompt_filters.id'), nullable=False),
    db.PrimaryKeyConstraint('test_run_id', 'prompt_filter_id', name='pk_test_run_filters')
)
