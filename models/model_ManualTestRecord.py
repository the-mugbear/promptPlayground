# models/model_ManualTestRecord.py
from datetime import datetime
from extensions import db

class ManualTestRecord(db.Model):
    __tablename__ = 'manual_test_records'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String,   nullable=False)
    endpoint = db.Column(db.String,   nullable=False)
    raw_headers = db.Column(db.Text,   nullable=True)
    payload_sent = db.Column(db.Text,  nullable=False)
    response_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
