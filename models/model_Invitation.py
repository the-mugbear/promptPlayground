# models/model_Invitation.py
import secrets
import datetime
from extensions import db
from models.model_User import ROLE_USER # Import default role

class Invitation(db.Model):
    __tablename__ = 'invitations'

    id = db.Column(db.Integer, primary_key=True)
    # Generate a secure random code
    code = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(16), index=True)
    # Optional: Restrict invite to a specific email
    email = db.Column(db.String(120), nullable=True, index=True)
    # Role the new user will get
    role_to_assign = db.Column(db.String(80), nullable=False, default=ROLE_USER)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

    # Optional: Set an expiry date (e.g., 7 days from creation)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_used = db.Column(db.Boolean, default=False, nullable=False, index=True)
    notes = db.Column(db.String(255), nullable=True) # Optional notes for admin

    # Link to admin who created it (requires User model import)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    # Link to user who used it
    used_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    used_by = db.relationship('User', foreign_keys=[used_by_id])

    def is_valid(self):
        """Checks if the invitation is still valid (not used, not expired)."""
        if self.is_used:
            return False
        if self.expires_at and datetime.datetime.utcnow() > self.expires_at:
            return False
        return True

    def __repr__(self):
        status = "Used" if self.is_used else ("Expired" if not self.is_valid() else "Valid")
        return f'<Invitation {self.code} ({status})>'