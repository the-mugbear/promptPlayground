# routes/auth.py
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, current_app # Added current_app for logging
)
from flask_login import login_user, logout_user, login_required, current_user
# werkzeug.security.generate_password_hash is not directly used here;
# password hashing is handled by the User model's set_password method.
# from werkzeug.security import generate_password_hash
from extensions import db
from forms import LoginForm, RegistrationForm # Assuming these forms are defined in a 'forms.py' file
from models.model_User import User
from models.model_Invitation import Invitation

# Define the authentication blueprint
# All routes defined in this blueprint will be prefixed with '/auth'
auth_bp = Blueprint(
    'auth_bp',
    __name__,
    template_folder='../templates/auth', # Specifies the template folder relative to the blueprint file if not standard
    url_prefix='/auth'
)

# --- Login Route ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login requests.
    If the user is already authenticated, redirects to the main index page.
    Validates login credentials and logs the user in.
    Redirects to the 'next' page if specified, otherwise to the main index.
    """
    # If user is already authenticated, redirect them from the login page
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('core_bp.index')) # Assuming 'core_bp.index' is your main dashboard/index route

    form = LoginForm()
    if form.validate_on_submit():
        # Form has been submitted and validated
        username_or_email = form.username.data # Login can be via username or email
        password = form.password.data
        remember = form.remember_me.data

        # Attempt to find the user by username
        user = User.query.filter_by(username=username_or_email).first()
        # Optionally, if not found by username, try finding by email
        if not user:
            user = User.query.filter_by(email=username_or_email).first()

        # Validate user existence and password correctness
        if user is None or not user.check_password(password):
            flash('Invalid username/email or password. Please try again.', 'error')
            # Return to the login page; the form will retain the submitted username/email
            return redirect(url_for('auth_bp.login'))

        # User credentials are valid, log the user in
        login_user(user, remember=remember)
        flash(f'Welcome back, {user.username}!', 'success')

        # Redirect logic:
        # If the user was attempting to access a protected page before being prompted to log in,
        # Flask-Login stores the intended destination in the 'next' query parameter.
        next_page = request.args.get('next')
        # Basic security check: ensure 'next_page' is a relative path.
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('core_bp.index') # Default redirect to the main index page

        return redirect(next_page)

    # For a GET request or if form validation fails, render the login template
    return render_template('login.html', title='Sign In', form=form) # Assumes login.html is in templates/auth/


# --- Invitation-Based Registration Route ---
@auth_bp.route('/register/<code>', methods=['GET', 'POST'])
def register_with_code(code):
    """Handles new user registration based on an invitation code.
    Validates the invitation code. If valid, presents a registration form.
    Upon successful form submission, creates a new user, assigns the specified role,
    marks the invitation as used, and redirects to the login page.
    """
    # If user is already authenticated, redirect them from the registration page
    if current_user.is_authenticated:
        flash('You are already registered and logged in.', 'info')
        return redirect(url_for('core_bp.index'))

    # Attempt to find the invitation by its code
    invitation = Invitation.query.filter_by(code=code).first()
    current_app.logger.info(f"Registration attempt using code: {code}. Invitation found: {bool(invitation)}")

    # --- Validate Invitation ---
    # Check if the invitation exists and is still valid (not used, not expired)
    if not invitation or not invitation.is_valid():
        current_app.logger.warning(f"Invalid invitation code used: {code}. Exists: {bool(invitation)}, Valid: {invitation.is_valid() if invitation else 'N/A'}")
        flash('The invitation code is invalid, expired, or has already been used.', 'error')
        # Redirect to the login page or a dedicated "invalid code" page
        return redirect(url_for('auth_bp.login'))

    # --- Invitation is valid, proceed with registration form ---
    # Pass request.form to the form constructor to populate it with POST data
    form = RegistrationForm(request.form)

    # If the request is GET and the invitation is restricted to a specific email, pre-fill the email field
    if request.method == 'GET' and invitation.email:
        form.email.data = invitation.email
        current_app.logger.info(f"Prefilled email '{invitation.email}' for registration with code {code}.")

    if form.validate_on_submit(): # True only for valid POST requests
        current_app.logger.info(f"Registration form submitted and validated for code: {code}.")
        # --- Re-validate invitation on POST before creating user ---
        # This handles the rare case where the invitation might become invalid
        # (e.g., expired or used by someone else) between the GET request and form submission.
        invitation = Invitation.query.filter_by(code=code).first() # Re-fetch to get the latest state
        if not invitation or not invitation.is_valid():
            current_app.logger.warning(f"Invitation code {code} became invalid during the registration process.")
            flash('The invitation code became invalid during registration. Please request a new one.', 'error')
            return redirect(url_for('auth_bp.login'))

        # Optional but recommended: If the invitation was for a specific email,
        # ensure the submitted email matches the one in the invitation.
        if invitation.email and invitation.email.lower() != form.email.data.lower():
            current_app.logger.warning(f"Email mismatch for code {code}. Invite: '{invitation.email}', Form: '{form.email.data}'.")
            flash('Please register using the email address the invitation was sent to.', 'error')
            # Re-render the registration form, retaining the invitation code in the URL
            return render_template('register.html', title='Register', form=form, code=code)

        # --- Create the new user ---
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            role=invitation.role_to_assign # Assign the role specified in the invitation
            # is_active is True by default in the User model
        )
        new_user.set_password(form.password.data) # Hash the password

        try:
            db.session.add(new_user)
            # Important: Mark the invitation as used.
            # This should happen after successfully adding the user and before the final commit.
            invitation.is_used = True
            # If you have a 'used_by_id' field in your Invitation model to link it to the new user:
            # To get new_user.id before commit, you might need to flush the session.
            # db.session.flush()
            # invitation.used_by_id = new_user.id

            db.session.commit() # Atomically commit both the new user and the invitation update
            current_app.logger.info(f"User '{new_user.username}' created successfully with code {code}. Invitation marked as used.")
            flash(f'Account created successfully for {new_user.username}! You can now log in.', 'success')
            return redirect(url_for('auth_bp.login'))

        except Exception as e:
            db.session.rollback() # Rollback database changes in case of an error
            current_app.logger.error(f"Error during registration for code {code}: {e}", exc_info=True)
            flash(f'An error occurred during registration. Please try again or contact support.', 'error')
            # Re-render the registration form to allow the user to try again
            return render_template('register.html', title='Register', form=form, code=code)

    # For a GET request or if form validation fails on POST, render the registration template
    # The 'code' is passed to the template for constructing the form's action URL.
    # Assumes register.html is in templates/auth/
    return render_template('register.html', title='Register', form=form, code=code)


# --- Logout Route ---
@auth_bp.route('/logout')
def logout():
    """Handles user logout.
    Logs the user out and redirects to the login page.
    """
    logout_user() # Clears the user's session
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth_bp.login')) # Redirect to the login page