from extensions import db 
from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON as DB_JSON 

class APIChain(db.Model):
    """
    Represents a chain or sequence of API calls.
    """
    __tablename__ = 'api_chains'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    
    # Foreign key to the User model
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('api_chains', lazy='dynamic'))

    # Relationship to steps, ordered by their execution order
    # 'dynamic' allows further querying on the steps collection if needed
    steps = db.relationship('APIChainStep', 
                            back_populates='chain', 
                            cascade='all, delete-orphan', 
                            order_by='APIChainStep.step_order',
                            lazy='dynamic')

    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert the API chain instance into a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "steps": [step.to_dict() for step in self.steps.all()] # .all() is needed if lazy='dynamic'
        }

    def __repr__(self):
        return f'<APIChain {self.name} (ID: {self.id})>'

class APIChainStep(db.Model):
    """
    Represents a single step within an APIChain.
    Each step executes an Endpoint and can extract data from its response.
    """
    __tablename__ = 'api_chain_steps'

    id = db.Column(db.Integer, primary_key=True)
    
    chain_id = db.Column(db.Integer, db.ForeignKey('api_chains.id'), nullable=False)
    chain = db.relationship('APIChain', back_populates='steps')

    # Reference to the actual Endpoint configuration to be executed for this step
    endpoint_id = db.Column(db.Integer, db.ForeignKey('endpoints.id'), nullable=False)
    # 'joined' eager loading ensures endpoint details are fetched with the step, useful for to_dict
    endpoint = db.relationship('Endpoint', lazy='joined') 
    step_order = db.Column(db.Integer, nullable=False)  # Defines execution sequence (e.g., 0, 1, 2...)

    headers = db.Column(db.Text, nullable=True)
    payload = db.Column(db.Text, nullable=True)

    # Rules for extracting data from *this* step's response.
    # This data will be added to a running context for use in *subsequent* steps.
    # Example Schema:
    # [
    #   {"variable_name": "session_id", "source_type": "header", "source_identifier": "X-Session-ID"},
    #   {"variable_name": "user_pk", "source_type": "json_body", "source_identifier": "data.user.id"},
    #   {"variable_name": "full_response_body", "source_type": "raw_body"},
    #   {"variable_name": "status", "source_type": "status_code"}
    # ]
    # 'source_identifier' is the header name, JSON path (e.g., using dot notation), or ignored for raw_body/status_code.
    data_extraction_rules = db.Column(DB_JSON, nullable=True)

    # Optional name/description for this specific step within the chain for clarity
    name = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)

    # Ensure step_order is unique per chain
    __table_args__ = (db.UniqueConstraint('chain_id', 'step_order', name='_chain_step_order_uc'),)

    def to_dict(self):
        """Convert the API chain step instance into a dictionary."""
        return {
            "id": self.id,
            "chain_id": self.chain_id,
            "endpoint_id": self.endpoint_id,
            "endpoint_name": self.endpoint.name if self.endpoint else "N/A", # Safely access endpoint name
            "step_order": self.step_order,
            "name": self.name,
            "description": self.description,
            "data_extraction_rules": self.data_extraction_rules
        }

    def __repr__(self):
        return f'<APIChainStep Order: {self.step_order} for Chain ID {self.chain_id} (Endpoint: {self.endpoint.name if self.endpoint else "N/A"})>'