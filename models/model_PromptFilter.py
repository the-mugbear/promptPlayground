from datetime import datetime
from extensions import db

class PromptFilter(db.Model):
    __tablename__ = 'prompt_filters'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    # A comma-separated string of invalid characters (or you could store it as JSON)
    invalid_characters = db.Column(db.String, nullable=True)
    # List of words to be replaced, stored as JSON (or a comma-separated string)
    words_to_replace = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PromptFilter {self.name}>"
