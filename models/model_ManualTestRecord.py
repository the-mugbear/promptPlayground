# models/model_ManualTestRecord.py
from datetime import datetime
from extensions import db

class ManualTestRecord(db.Model):
    __tablename__ = 'manual_test_records'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255),   nullable=False)
    endpoint = db.Column(db.String(255),   nullable=False)
    raw_headers = db.Column(db.TEXT,   nullable=True)
    payload_sent = db.Column(db.TEXT,  nullable=False)
    response_data = db.Column(db.TEXT, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
