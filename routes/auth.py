# routes/auth.py
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash # Needed if hashing here, but model does it too
from extensions import db
from forms import LoginForm, RegistrationForm

from models.model_User import User
from models.model_Invitation import Invitation


# Define the blueprint
auth_bp = Blueprint(
    'auth_bp',
    __name__,
    url_prefix='/auth'
)

# --- Login Route ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect them away from login page
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('core_bp.index')) # Redirect to main index

    form = LoginForm()
    if form.validate_on_submit():
        # Form has been submitted and validated
        username_or_email = form.username.data # Assuming login via username for now
        password = form.password.data
        remember = form.remember_me.data

        # Find the user by username (or email if you prefer/allow)
        user = User.query.filter_by(username=username_or_email).first()
        # If not found by username, optionally check by email:
        # if not user:
        #    user = User.query.filter_by(email=username_or_email).first()

        # Validate user existence and password
        if user is None or not user.check_password(password):
            flash('Invalid username or password. Please try again.', 'error')
            # Return to the login page, the form will retain submitted username (but not password)
            return redirect(url_for('auth_bp.login'))

        # User is valid, log them in
        login_user(user, remember=remember)
        flash(f'Welcome back, {user.username}!', 'success')

        # Redirect logic:
        # If the user was trying to access a protected page before login,
        # Flask-Login stores it in 'next'. Redirect there if it exists.
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'): # Basic security check
            next_page = url_for('core_bp.index') # Default redirect to main index

        return redirect(next_page)

    # If GET request or form validation failed, render the login template
    return render_template('auth/login.html', title='Sign In', form=form)


# --- NEW Invitation-Based Registration Route ---
@auth_bp.route('/register/<code>', methods=['GET', 'POST'])
def register_with_code(code):
    if current_user.is_authenticated:
        flash('You are already registered and logged in.', 'info')
        return redirect(url_for('core_bp.index'))

    # Find the invitation code
    invitation = Invitation.query.filter_by(code=code).first()

    # --- Validate Invitation ---
    if not invitation or not invitation.is_valid():
         flash('The invitation code is invalid, expired, or has already been used.', 'error')
         # Redirect to login or a specific "invalid code" page
         return redirect(url_for('auth_bp.login'))

    # --- Invitation is valid, proceed with registration form ---
    form = RegistrationForm()

    # Optional: Pre-fill email if invite was specific
    if request.method == 'GET' and invitation.email:
         form.email.data = invitation.email

    if form.validate_on_submit():
        # --- Re-validate invitation on POST before creating user ---
        # (Handles case where code becomes invalid between GET and POST)
        invitation = Invitation.query.filter_by(code=code).first()
        if not invitation or not invitation.is_valid():
            flash('The invitation code became invalid during registration. Please request a new one.', 'error')
            return redirect(url_for('auth_bp.login'))

        # Optional: Check if email matches invite if invite had one
        if invitation.email and invitation.email.lower() != form.email.data.lower():
            flash('Please register using the email address the invitation was sent to.', 'error')
            # Re-render form, keeping code in URL
            return render_template('register.html', title='Register', form=form, code=code)


        # Create user
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            role=invitation.role_to_assign # Assign role from invitation
            # is_active=True # Defaulted in model, user is active immediately
        )
        new_user.set_password(form.password.data)

        try:
            db.session.add(new_user)
            # Important: Mark invitation as used *after* adding user, before commit
            invitation.is_used = True
            # invitation.used_by_id = new_user.id # Link user if relationship exists
            # Need to flush to get new_user.id if linking FK immediately
            # db.session.flush()
            # invitation.used_by_id = new_user.id

            db.session.commit() # Commit user and invitation update together

            flash(f'Account created successfully for {new_user.username}! You can now log in.', 'success')
            return redirect(url_for('auth_bp.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {e}', 'error')
            current_app.logger.error(f"Registration error with code {code}: {e}")


    # Render the same registration template, but the route includes the code
    # Pass code to template if needed (e.g., for form action URL, though url_for handles it)
    return render_template('register.html', title='Register', form=form, code=code)

# --- Logout Route ---
@auth_bp.route('/logout')
@login_required # User must be logged in to log out
def logout():
    logout_user() # Clears the user session
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth_bp.login')) # Redirect to login page