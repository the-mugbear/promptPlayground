import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash # Or your hashing function
from extensions import db
from flask import Blueprint
from models.model_User import User, ROLE_ADMIN, ROLE_USER

bp = Blueprint('cli', __name__, cli_group=None)

@click.command('create-admin')
@click.option('--username', prompt=True, help='The username for the admin user.') #
@click.option('--email', prompt=True, help='The email address for the admin user.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='The password for the admin user.')
@click.option('--is-admin', is_flag=True, default=True, help='Flag to mark user as admin.')

def create_admin_command(username, email, password, is_admin): # Added username parameter
    """Creates a new admin user."""
    # Check if user already exists by email OR username
    existing_user = User.query.filter(
        (User.email == email) | (User.username == username)
    ).first()
    if existing_user:
        print(f"Error: User with email '{email}' or username '{username}' already exists.")
        return

    try:
        # Create the user instance (without password initially)
        new_admin = User(
            username=username, # <-- Set username
            email=email
            # is_active defaults to True in model
        )

        # Set the password using the model's method
        new_admin.set_password(password)

        # Set the role based on the flag
        if is_admin:
            new_admin.role = ROLE_ADMIN
        else:
            new_admin.role = ROLE_USER

        db.session.add(new_admin)
        db.session.commit()
        print(f"User '{username}' ({new_admin.role}) created successfully.") # Modified print
    except Exception as e:
        db.session.rollback()
        print(f"Error creating admin user: {e}")

# Register the command using the blueprint method
# Ensure you import and register this blueprint in fuzzy_prompts.py create_app()
bp.cli.add_command(create_admin_command)