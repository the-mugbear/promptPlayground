# routes/admin.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from extensions import db
from models.model_Invitation import Invitation
from models.model_User import ROLE_ADMIN, ROLE_USER # Import roles
from utils.decorators import admin_required # Import our decorator
import datetime

admin_bp = Blueprint(
    'admin_bp',
    __name__,
    url_prefix='/admin', # All admin routes start with /admin
)

# --- Protect ALL routes in this blueprint ---
@admin_bp.before_request
@admin_required # Apply decorator to all requests in this blueprint
def before_request():
    """Protects all admin routes."""
    pass # Decorator handles the logic

# --- Invitation List Route ---
@admin_bp.route('/invitations')
def list_invitations():
    page = request.args.get('page', 1, type=int)
    # Show newest first, maybe filter by used/unused later
    pagination = Invitation.query.order_by(Invitation.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    invitations = pagination.items
    return render_template('admin/list_invitations.html', invitations=invitations, pagination=pagination)

# --- Create Invitation Route ---
@admin_bp.route('/invitations/create', methods=['GET', 'POST'])
def create_invitation():
    if request.method == 'POST':
        email = request.form.get('email', '').strip() or None # Optional email
        role = request.form.get('role', ROLE_USER)
        notes = request.form.get('notes', '').strip() or None
        expires_days = request.form.get('expires_days', type=int) # Optional expiry

        if role not in [ROLE_USER, ROLE_ADMIN]: # Basic validation
             flash(f"Invalid role specified: {role}", "error")
             return redirect(url_for('admin_bp.create_invitation'))

        expires_at = None
        if expires_days is not None and expires_days > 0:
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=expires_days)

        invitation = Invitation(
            email=email,
            role_to_assign=role,
            expires_at=expires_at,
            notes=notes
            # created_by_id=current_user.id # If you added created_by_id field
        )
        try:
            db.session.add(invitation)
            db.session.commit()
            # Generate the full URL (requires app context)
            invite_url = url_for('auth_bp.register_with_code', code=invitation.code, _external=True)
            flash(f"Invitation created successfully! Code: {invitation.code}", "success")
            flash(f"Shareable Link: {invite_url}", "info") # Display link
            return redirect(url_for('admin_bp.list_invitations'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating invitation: {e}", "error")
            current_app.logger.error(f"Invitation creation failed: {e}")


    # GET request: Show the form
    available_roles = [ROLE_USER, ROLE_ADMIN] # Define roles available in form
    return render_template('admin/create_invitation.html', available_roles=available_roles)

# --- TODO: Add routes to revoke/delete invitations if needed ---