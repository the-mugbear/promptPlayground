from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Define roles (optional but good practice)
ROLE_ADMIN = 'admin'
ROLE_USER = 'user'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True) # Optional
    password_hash = db.Column(db.String(256)) # Increased length

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    role = db.Column(db.String(80), nullable=False, default=ROLE_USER)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
 
    # --- Helper property for checking admin role ---
    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN
    # ---------------------------------------------

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
    
    # --- Flask-Login Properties ---
    # These are provided by UserMixin, but is_active can be overridden if needed
    # is_authenticated is handled by Flask-Login
    # is_anonymous is handled by Flask-Login