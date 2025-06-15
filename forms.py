# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional, Length
from models.model_User import User 

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

class InvitationForm(FlaskForm):
    """Form for creating new invitations."""
    email = StringField('Email', validators=[
        Optional(),
        Email(message="Please enter a valid email address.")
    ])
    role = SelectField('Role', validators=[
        DataRequired(message="Role is required.")
    ])
    expires_days = IntegerField('Expires In (Days)', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Generate Invitation')

class ChainForm(FlaskForm):
    """Form for creating or editing an API Chain."""
    name = StringField(
        'Chain Name', 
        validators=[DataRequired(), Length(min=3, max=100)],
        render_kw={"placeholder": "e.g., User Authentication Flow"}
    )
    description = TextAreaField(
        'Description', 
        validators=[Length(max=500)],
        render_kw={"placeholder": "A brief description of what this chain does.", "rows": 3}
    )
    submit = SubmitField('Create Chain')

class ChainStepForm(FlaskForm):
    """Form for adding or editing a step in an API Chain."""
    endpoint = SelectField('Endpoint', coerce=int, validators=[DataRequired()])
    name = StringField(
        'Step Name (Optional)', 
        validators=[Optional(), Length(max=100)]
    )
    
    # --- ADD THESE FIELDS BACK ---
    headers = TextAreaField(
        'Headers Template', 
        validators=[Optional()],
        description="Optional. Overrides the endpoint's default headers. Use Jinja2 for dynamic values."
    )
    payload = TextAreaField(
        'Payload Template', 
        validators=[Optional()], 
        description="Optional. Overrides the endpoint's default payload. Use Jinja2 for dynamic values."
    )

    data_extraction_rules = TextAreaField(
        'Data Extraction Rules (JSON format)',
        validators=[Optional()]
    )
    submit = SubmitField('Save Step')