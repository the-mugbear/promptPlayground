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
@click.option('--is-admin', is_flag=True, help='Set this user as an admin.')

def create_admin_command(username, email, password, is_admin):
    """Creates a new admin user."""
    print(f"--- Create Admin Command ---")
    print(f"Received --username: {username}")
    print(f"Received --email: {email}")
    print(f"Received --is-admin flag: {is_admin} (Type: {type(is_admin)})") # Crucial debug

    existing_user = User.query.filter(
        (User.email == email) | (User.username == username)
    ).first()
    if existing_user:
        print(f"Error: User with email '{email}' or username '{username}' already exists.")
        return

    try:
        new_admin = User(
            username=username,
            email=email
        )
        new_admin.set_password(password)

        print(f"Value of is_admin before setting role: {is_admin}") # Another check
        if is_admin:
            print(f"Setting role to ROLE_ADMIN ('{ROLE_ADMIN}')")
            new_admin.role = ROLE_ADMIN
        else:
            print(f"Setting role to ROLE_USER ('{ROLE_USER}')")
            new_admin.role = ROLE_USER

        print(f"User object before commit: username='{new_admin.username}', email='{new_admin.email}', role='{new_admin.role}'")

        db.session.add(new_admin)
        db.session.commit()
        print(f"User '{new_admin.username}' (role: {new_admin.role}) created successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating admin user: {e}")

# Register the command using the blueprint method
# Ensure you import and register this blueprint in fuzzy_prompts.py create_app()
bp.cli.add_command(create_admin_command)