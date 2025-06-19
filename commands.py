"""
Flask CLI commands for FuzzyPrompts

This module contains custom Flask CLI commands for administrative tasks.
Only includes essential commands for the fresh execution engine implementation.
"""

import click
from flask.cli import with_appcontext
from flask import Blueprint
from extensions import db
from models.model_User import User, ROLE_ADMIN, ROLE_USER

# CLI Blueprint
bp = Blueprint('cli', __name__, cli_group=None)


@click.command('create-admin')
@click.option('--username', prompt=True, help='The username for the admin user.')
@click.option('--email', prompt=True, help='The email address for the admin user.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, 
              help='The password for the admin user.')
@click.option('--is-admin', is_flag=True, default=True, 
              help='Set this user as an admin (default: True).')
@with_appcontext
def create_admin_command(username, email, password, is_admin):
    """Creates a new admin user for the FuzzyPrompts application."""
    
    click.echo("=== FuzzyPrompts Admin User Creation ===")
    click.echo(f"Username: {username}")
    click.echo(f"Email: {email}")
    click.echo(f"Admin privileges: {'Yes' if is_admin else 'No'}")
    click.echo()

    # Check for existing user
    existing_user = User.query.filter(
        (User.email == email) | (User.username == username)
    ).first()
    
    if existing_user:
        click.secho(f"❌ Error: User with email '{email}' or username '{username}' already exists.", 
                   fg="red")
        click.echo("Please choose a different username or email.")
        return

    try:
        # Create new user
        new_user = User(
            username=username,
            email=email,
            role=ROLE_ADMIN if is_admin else ROLE_USER
        )
        new_user.set_password(password)

        # Save to database
        db.session.add(new_user)
        db.session.commit()
        
        role_text = "Admin" if is_admin else "Regular user"
        click.secho(f"✅ {role_text} '{username}' created successfully!", fg="green")
        click.echo(f"   Email: {email}")
        click.echo(f"   Role: {new_user.role}")
        click.echo()
        click.echo("You can now log in to the FuzzyPrompts web interface with these credentials.")
        
    except Exception as e:
        db.session.rollback()
        click.secho(f"❌ Error creating user: {e}", fg="red")
        click.echo("Please check the database connection and try again.")


@click.command('list-users')
@with_appcontext 
def list_users_command():
    """Lists all users in the system."""
    
    click.echo("=== FuzzyPrompts Users ===")
    
    users = User.query.order_by(User.created_at.desc()).all()
    
    if not users:
        click.echo("No users found in the database.")
        click.echo("Use 'flask create-admin' to create the first admin user.")
        return
    
    click.echo(f"Found {len(users)} user(s):")
    click.echo()
    
    for user in users:
        role_color = "green" if user.role == ROLE_ADMIN else "blue"
        created = user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else 'Unknown'
        
        click.echo(f"• {user.username} ({user.email})")
        click.secho(f"  Role: {user.role}", fg=role_color)
        click.echo(f"  Created: {created}")
        click.echo()


@click.command('delete-user')
@click.option('--username', prompt=True, help='Username of the user to delete.')
@click.confirmation_option(prompt='Are you sure you want to delete this user?')
@with_appcontext
def delete_user_command(username):
    """Deletes a user from the system."""
    
    user = User.query.filter_by(username=username).first()
    
    if not user:
        click.secho(f"❌ Error: User '{username}' not found.", fg="red")
        return
    
    try:
        db.session.delete(user)
        db.session.commit()
        click.secho(f"✅ User '{username}' deleted successfully.", fg="green")
        
    except Exception as e:
        db.session.rollback()
        click.secho(f"❌ Error deleting user: {e}", fg="red")


# Register commands with the blueprint
bp.cli.add_command(create_admin_command)
bp.cli.add_command(list_users_command)
bp.cli.add_command(delete_user_command)