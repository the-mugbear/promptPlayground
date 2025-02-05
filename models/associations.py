from extensions import db

test_run_suites = db.Table('test_run_suites',
    db.Column('test_run_id', db.Integer, db.ForeignKey('test_runs.id'), primary_key=True),
    db.Column('test_suite_id', db.Integer, db.ForeignKey('test_suites.id'), primary_key=True)
)
