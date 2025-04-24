# models/model_DatasetReference.py
from datetime import datetime
from extensions import db

class DatasetReference(db.Model):
    __tablename__ = 'dataset_references'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    date_added = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    # This Boolean field determines whether the dataset has been "added"
    added = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<DatasetReference {self.name} - {self.url}>"
