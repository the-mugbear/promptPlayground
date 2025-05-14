# forms.py
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, RadioField
from wtforms.validators import DataRequired

# AI Trustworthy Characteristics - these will be the choices for one of our SelectFields
# We'll use a shorter key for the value and the full text for the display
aitc_choices = [
    ('cbrn', '1. CBRN Information or Capabilities'),
    ('confabulation', '2. Confabulation'),
    ('dangerous_content', '3. Dangerous, Violent, or Hateful Content'),
    ('data_privacy', '4. Data Privacy'),
    ('environmental_impacts', '5. Environmental Impacts'),
    ('harmful_bias', '6. Harmful Bias or Homogenization'),
    ('human_ai_config', '7. Human-AI Configuration'),
    ('info_integrity', '8. Information Integrity'),
    ('info_security', '9. Information Security'),
    ('intellectual_property', '10. Intellectual Property'),
    ('obscene_content', '11. Obscene, Degrading, and/or Abusive Content'),
    ('value_chain', '12. Value Chain and Component Integration')
]

# Helper for impact levels
impact_levels = [
    ('N', 'None (N)'),
    ('L', 'Low (L)'),
    ('M', 'Medium (M)'),
    ('H', 'High (H)')
]

class RiskCalculatorForm(FlaskForm):
    # Base Metrics
    attack_vector = RadioField(
        'Attack Vector (AV)',
        choices=[('IO', 'Internal Only (IO)'), ('IF', 'Internet Facing (IF)')],
        validators=[DataRequired()]
    )
    privileges_required = RadioField(
        'Privileges Required (PR)',
        choices=[('H', 'High (H)'), ('L', 'Low (L)'), ('N', 'None (N)')],
        validators=[DataRequired()]
    )
    attack_complexity = RadioField(
        'Attack Complexity (AC)',
        choices=[('L', 'Low (L)'), ('M', 'Medium (M)'), ('H', 'High (H)')], # Reversed to Low, Med, High
        validators=[DataRequired()]
    )
    user_interaction = RadioField(
        'User Interaction (UI)',
        choices=[('N', 'None (N)'), ('R', 'Required (R)')], # Reversed to None, Required
        validators=[DataRequired()]
    )

    # Impact Metrics
    aitc = SelectField(
        'AI Trustworthy Characteristic (AITC)',
        choices=aitc_choices,
        validators=[DataRequired()]
    )
    characteristic_impact = SelectField(
        'Characteristic Impact (CI)',
        choices=impact_levels,
        validators=[DataRequired()]
    )
    legal_impact = SelectField(
        'Legal Impact (LI)',
        choices=impact_levels,
        validators=[DataRequired()]
    )

    submit = SubmitField('Calculate Risk Score')