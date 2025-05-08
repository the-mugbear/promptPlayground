# models/model_Reference.py
from datetime import datetime
from extensions import db

class Reference(db.Model):
    __tablename__ = 'references'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    excerpt = db.Column(db.Text, nullable=True)  # Summary of the article/research
    date_added = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    # This Boolean field determines whether the reference has been "added"
    added = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Reference {self.name} - {self.url}>"
