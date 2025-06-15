# ==============================================================================
# FORMS - Using Flask-WTF and WTForms
# ------------------------------------------------------------------------------
# This file defines the structure, validation, and field types for all web
# forms in the application. It acts as a bridge between the backend models
# and the frontend HTML templates.
# ==============================================================================

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, TextAreaField, RadioField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional, Length, URL, NumberRange
from wtforms_sqlalchemy.fields import QuerySelectField
from models.model_User import User 
from models.model_Endpoints import Endpoint
from models.model_PayloadTemplate import PayloadTemplate

# --- Authentication Forms ---

class LoginForm(FlaskForm):
    """Defines the fields and validation for the user login page."""
    username = StringField('Username', validators=[DataRequired(message="Username is required.")])
    password = PasswordField('Password', validators=[DataRequired(message="Password is required.")])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    """Defines the fields and validation for the new user registration page."""
    username = StringField('Username', validators=[DataRequired(message="Username is required.")])
    email = StringField('Email', validators=[DataRequired(message="Email is required."), Email(message="Please enter a valid email address.")])
    password = PasswordField('Password', validators=[DataRequired(message="Password is required.")])
    password2 = PasswordField(
        'Repeat Password', 
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo('password', message='Passwords must match.') # Validator to ensure this field matches the 'password' field.
        ]
    )
    submit = SubmitField('Register')

    # --- Custom Validators ---
    # These methods are automatically called by WTForms because they follow the `validate_<field_name>` pattern.
    
    def validate_username(self, username):
        """Checks the database to ensure the username is not already in use."""
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Username already taken. Please choose a different one.')

    def validate_email(self, email):
        """Checks the database to ensure the email is not already registered."""
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Email address already registered. Please use a different one.')

# --- Administration Forms ---

class InvitationForm(FlaskForm):
    """Form used by admins to generate new user invitation codes."""
    email = StringField('Email', validators=[Optional(), Email(message="Please enter a valid email address.")])
    role = SelectField('Role', validators=[DataRequired(message="Role is required.")])
    expires_days = IntegerField('Expires In (Days)', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Generate Invitation')


# --- API Chain & Step Forms ---

class ChainForm(FlaskForm):
    """Form for creating the main API Chain object."""
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
    """Form for adding or editing a single step within a chain."""
    # A standard dropdown. The 'choices' for this field will be populated dynamically in the view function.
    endpoint = SelectField('Endpoint', coerce=int, validators=[DataRequired()])
    name = StringField('Step Name (Optional)', validators=[Optional(), Length(max=100)])
    
    # Text areas for the step-specific template overrides.
    headers = TextAreaField('Headers Template', validators=[Optional()], description="Optional. Overrides the endpoint's default headers.")
    payload = TextAreaField('Payload Template', validators=[Optional()], description="Optional. Overrides the endpoint's default payload.")
    
    # Text area for the JSON that defines data extraction rules.
    data_extraction_rules = TextAreaField('Data Extraction Rules (JSON format)', validators=[Optional()])
    submit = SubmitField('Save Step')


# --- Endpoint & Payload Template Forms ---

class PayloadTemplateForm(FlaskForm):
    """Form for creating and managing reusable payload templates."""
    name = StringField('Template Name', validators=[DataRequired(), Length(max=255)], description="A unique name for this payload (e.g., 'OpenAI Chat Completion v1').")
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)], description="Explain what this payload is for and how to use its template variables.")
    template = TextAreaField('Payload Template Body', validators=[DataRequired()], description="The Jinja2 template for the JSON payload.", render_kw={"rows": 15})
    submit = SubmitField('Save Payload Template')

class EndpointForm(FlaskForm):
    """The refactored, powerful form for creating or editing an Endpoint."""
    name = StringField('Endpoint Name', validators=[DataRequired(), Length(max=255)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    
    # Renamed fields for better clarity, with a URL validator for the base URL.
    base_url = StringField('Base URL', validators=[DataRequired(), URL()], render_kw={"placeholder": "e.g., https://api.openai.com"})
    path = StringField('Path', validators=[DataRequired()], render_kw={"placeholder": "e.g., /v1/chat/completions"})
    
    method = SelectField('HTTP Method', choices=[('POST', 'POST'), ('GET', 'GET'), ('PUT', 'PUT'), ('DELETE', 'DELETE')], validators=[DataRequired()])
    
    # This special field dynamically creates a dropdown from a database query.
    # It will show a list of all existing PayloadTemplates.
    payload_template = QuerySelectField(
        'Default Payload Template',
        query_factory=lambda: PayloadTemplate.query.order_by(PayloadTemplate.name),
        get_label='name',
        allow_blank=True, # Allows an endpoint to have no default payload.
        description="Select a reusable payload template. This can be overridden at the chain step level."
    )
    
    # Fields for the new, structured authentication system.
    auth_method = SelectField('Authentication Method', choices=[('none', 'None'), ('bearer', 'Bearer Token'), ('api_key', 'Custom API Key Header')], default='none')
    credentials_encrypted = StringField('Credentials (Token or Key)', validators=[Optional()], description="Secret value will be encrypted upon saving.")
    
    raw_headers = TextAreaField(
        'Raw Headers (Optional)',
        description="One 'Key: Value' pair per line. These are used for non-sensitive headers like 'Accept'. Sensitive tokens should use the Authentication fields below.",
        render_kw={"rows": 5}
    )

    # Fields for resiliency, with range validators to ensure sensible values.
    timeout_seconds = IntegerField('Timeout (seconds)', default=60, validators=[DataRequired(), NumberRange(min=1, max=300)])
    retry_attempts = IntegerField('Retry Attempts on Failure', default=0, validators=[DataRequired(), NumberRange(min=0, max=5)])
    
    # The field for selecting the Endpoint's primary purpose, which drives client-side validation.
    purpose = RadioField(
        'Endpoint Purpose',
        choices=[
            ('test_run', 'For Test Run (requires {{INJECT_PROMPT}} token)'),
            ('chain', 'For API Chain (no token required)')
        ],
        default='test_run',
        validators=[DataRequired()]
    )
    
    submit = SubmitField('Save Endpoint')