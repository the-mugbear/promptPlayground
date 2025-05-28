from extensions import db
from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON  # For storing template data in SQLite

# ---------------------------------
# Endpoint 
# ---------------------------------
class Endpoint(db.Model):
    """
    Represents a log of a successful API POST request.

    Attributes:
        hostname (str): The hostname of the API endpoint.
        endpoint (str): The path or name of the associated resource.
        http_payload (str): The HTTP payload sent with the request.
        timestamp (datetime): The time the log was created.
        headers (list[APIHeader]): A list of headers associated with the request.
        user_id (int): Foreign key referencing the user who created the endpoint.
    """
    __tablename__ = 'endpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # New name attribute
    hostname = db.Column(db.String(255), nullable=False)
    endpoint = db.Column(db.String(255), nullable=False)
    http_payload = db.Column(db.Text, nullable=True)   # HTTP payload sent with the request, should handle and store as JSON
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)  # <--- ADDED TIMESTAMP

    # Foreign key to the User model
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Or False if user is mandatory
    # Relationship to User (optional, for easier access to user object)
    user = db.relationship('User', backref=db.backref('endpoints', lazy=True))
    
    # Relationships
    headers = db.relationship('APIHeader', back_populates='endpoint', cascade='all, delete-orphan')
    test_runs = db.relationship('TestRun', back_populates='endpoint')
    dialogues = db.relationship("Dialogue", back_populates="endpoint", cascade="all, delete-orphan")

    identified_invalid_characters = db.Column(db.Text, nullable=True) # Stores a string of identified invalid characters

    # Fields for site crawl results
    last_crawl_timestamp = db.Column(db.DateTime, nullable=True)
    last_crawl_status = db.Column(db.String(50), nullable=True) # e.g., "in_progress", "completed", "failed"
    discovered_links_json = db.Column(db.Text, nullable=True) # JSON string of list of discovered links
    found_strings_summary_json = db.Column(db.Text, nullable=True) # JSON string of dict of found strings summary

    def to_dict(self):
        """Convert the endpoint log instance into a dictionary."""
        return {
            "id": self.id,
            "hostname": self.hostname,
            "endpoint": self.endpoint,
            "http_payload": self.http_payload,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "headers": [header.to_dict() for header in self.headers],
            "user_id": self.user_id,
            "identified_invalid_characters": self.identified_invalid_characters,
            "last_crawl_timestamp": self.last_crawl_timestamp.isoformat() if self.last_crawl_timestamp else None,
            "last_crawl_status": self.last_crawl_status,
            "discovered_links_json": self.discovered_links_json,
            "found_strings_summary_json": self.found_strings_summary_json
        }

    def __repr__(self):
        """String representation of the endpoint log."""
        return f'<EndpointLog {self.hostname} -> {self.endpoint} @ {self.timestamp}>'

# ---------------------------------
# API Header
# ---------------------------------
class APIHeader(db.Model):
    """
    Represents an HTTP header for an API request.

    Attributes:
        endpoint_id (int): Foreign key referencing the associated endpoint log.
        key (str): The header key (e.g., "Content-Type").
        value (str): The header value (e.g., "application/json").
    """
    __tablename__ = 'endpoint_headers'
    
    id = db.Column(db.Integer, primary_key=True)
    endpoint_id = db.Column(db.Integer, db.ForeignKey('endpoints.id'), nullable=False)
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(db.TEXT, nullable=False)

    # Relationship
    endpoint = db.relationship('Endpoint', back_populates='headers')

    def to_dict(self):
        """Convert the API header instance into a dictionary."""
        return {
            "id": self.id,
            "endpoint_id": self.endpoint_id,
            "key": self.key,
            "value": self.value
        }
    
    def __repr__(self):
        """String representation of the API header."""
        return f'<APIHeader {self.key}: {self.value}>'