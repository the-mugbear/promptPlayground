# utils/decorators.py
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    """
    Decorator to ensure the current user is logged in AND is an admin.
    Redirects to login or shows forbidden error.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # If not logged in at all, redirect to login
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth_bp.login', next=request.url))
        if not current_user.is_admin:
            # If logged in but not admin, show forbidden error
            flash('You do not have permission to access this page.', 'error')
            # You could redirect somewhere else, like the index page:
            # return redirect(url_for('core_bp.index'))
            # Or abort with a 403 error:
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function