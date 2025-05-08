from extensions import db
from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON  # For storing template data in SQLite

# ---------------------------------
# Discovered Endpoint
# ---------------------------------
class DiscoveredEndpoint(db.Model):
    """
    Represents an endpoint discovered during enumeration.

    Attributes:
        endpoint_id (int): Foreign key referencing the parent endpoint.
        path (str): The discovered endpoint path.
        status_code (int): The HTTP status code received when testing the endpoint.
        method (str): The HTTP method used (GET, POST, etc.).
        discovered_at (datetime): When the endpoint was discovered.
        response_headers (JSON): The response headers received.
        response_body (str): The response body received (if any).
    """
    __tablename__ = 'discovered_endpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    endpoint_id = db.Column(db.Integer, db.ForeignKey('endpoints.id'), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(10), nullable=False, default='GET')
    discovered_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    response_headers = db.Column(JSON, nullable=True)
    response_body = db.Column(db.Text, nullable=True)
    
    # Relationship to parent endpoint
    endpoint = db.relationship('Endpoint', back_populates='discovered_endpoints')
    
    def to_dict(self):
        """Convert the discovered endpoint instance into a dictionary."""
        return {
            "id": self.id,
            "endpoint_id": self.endpoint_id,
            "path": self.path,
            "status_code": self.status_code,
            "method": self.method,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
            "response_headers": self.response_headers,
            "response_body": self.response_body
        }
    
    def __repr__(self):
        """String representation of the discovered endpoint."""
        return f'<DiscoveredEndpoint {self.path} -> {self.status_code} @ {self.discovered_at}>'

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
        discovered_endpoints (list[DiscoveredEndpoint]): List of endpoints discovered during enumeration.
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
    discovered_endpoints = db.relationship('DiscoveredEndpoint', back_populates='endpoint', cascade='all, delete-orphan')

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
            "discovered_endpoints": [ep.to_dict() for ep in self.discovered_endpoints]
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