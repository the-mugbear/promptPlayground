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
    """
    __tablename__ = 'endpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # New name attribute
    hostname = db.Column(db.String, nullable=False)
    endpoint = db.Column(db.String, nullable=False)
    http_payload = db.Column(db.Text, nullable=True)   # HTTP payload sent with the request, should handle and store as JSON
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # <--- ADDED TIMESTAMP
    
    # Relationships
    headers = db.relationship('APIHeader', back_populates='endpoint', cascade='all, delete-orphan')
    test_runs = db.relationship('TestRun', back_populates='endpoint')
    dialogues = db.relationship("Dialogue", back_populates="endpoint", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert the endpoint log instance into a dictionary."""
        return {
            "id": self.id,
            "hostname": self.hostname,
            "endpoint": self.endpoint,
            "http_payload": self.http_payload,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "headers": [header.to_dict() for header in self.headers],
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
    key = db.Column(db.String, nullable=False)
    value = db.Column(db.String, nullable=False)

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