# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from models.model_User import User # Import your User model

class LoginForm(FlaskForm):
    """Form for users to log in."""
    username = StringField('Username', validators=[DataRequired(message="Username is required.")])
    password = PasswordField('Password', validators=[DataRequired(message="Password is required.")])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    """Form for users to register new accounts."""
    username = StringField('Username', validators=[
        DataRequired(message="Username is required.")
    ])
    email = StringField('Email', validators=[
        DataRequired(message="Email is required."),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required.")
    ])
    password2 = PasswordField(
        'Repeat Password', validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo('password', message='Passwords must match.') # Ensures this matches the 'password' field
        ])
    submit = SubmitField('Register')

    # --- Custom Validators ---
    def validate_username(self, username):
        """Check if the username is already taken."""
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Username already taken. Please choose a different one.')

    def validate_email(self, email):
        """Check if the email is already registered."""
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Email address already registered. Please use a different one.')