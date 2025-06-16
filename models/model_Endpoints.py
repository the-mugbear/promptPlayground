from extensions import db
from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON  # For storing template data in SQLite

# ---------------------------------
# Endpoint 
# ---------------------------------
class Endpoint(db.Model):
    __tablename__ = 'endpoints'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # --- Renamed & Metadata Fields ---
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    base_url = db.Column(db.String(255), nullable=False)  # Renamed from 'hostname'
    path = db.Column(db.String(255), nullable=False, default='/') # Renamed from 'endpoint'
    method = db.Column(db.String(10), nullable=False, default='POST')
    
    # --- Decoupled Payload ---
    payload_template_id = db.Column(db.Integer, db.ForeignKey('payload_templates.id'), nullable=True)
    payload_template = db.relationship('PayloadTemplate', backref='endpoints')

    # --- Authentication Fields ---
    auth_method = db.Column(db.String(50), default='none', nullable=False) # e.g., 'none', 'bearer', 'api_key'
    credentials_encrypted = db.Column(db.Text, nullable=True) # For storing encrypted tokens/keys
    
    # --- Resiliency Fields ---
    timeout_seconds = db.Column(db.Integer, default=60, nullable=False)
    retry_attempts = db.Column(db.Integer, default=0, nullable=False)
        
    # --- Fields for Configurable Retry Delay ---
    retry_initial_delay_seconds = db.Column(db.Integer, default=2, nullable=False)
    retry_backoff_factor = db.Column(db.Float, default=2.0, nullable=False)
    
    # --- Other Existing Fields ---
    headers = db.relationship('EndpointHeader', back_populates='endpoint', lazy='dynamic', cascade="all, delete-orphan")
    
    # This creates the "many" side of a one-to-many relationship.
    # One Endpoint can be used in many TestRuns.
    test_runs = db.relationship('TestRun', back_populates='endpoint', lazy='dynamic')
    dialogues = db.relationship("Dialogue", back_populates="endpoint", cascade="all, delete-orphan")

    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert the Endpoint instance into a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "base_url": self.base_url,
            "path": self.path,
            "method": self.method,
            "payload_template_id": self.payload_template_id,
            "payload_template_name": self.payload_template.name if self.payload_template else None,
            "auth_method": self.auth_method,
            "timeout_seconds": self.timeout_seconds,
            "retry_attempts": self.retry_attempts,
            "headers": [header.to_dict() for header in self.headers],
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        """String representation of the Endpoint."""
        return f'<Endpoint {self.name} ({self.method} {self.base_url}{self.path})>'


# ---------------------------------
# Endpoint Header
# ---------------------------------
class EndpointHeader(db.Model):
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
        return f'<EndpointHeader {self.key}: {self.value}>'