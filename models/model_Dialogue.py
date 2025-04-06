from datetime import datetime
from extensions import db

class Dialogue(db.Model):
    __tablename__ = 'dialogues'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation = db.Column(db.Text, nullable=False)  # Store the full dialogue as a JSON string
    source = db.Column(db.String(50), nullable=False, default="best_of_n")  # e.g., "best_of_n", "evil_agent"
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Dialogue {self.id} at {self.created_at}>"
