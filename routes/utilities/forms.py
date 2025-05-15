# routes/utilities/forms.py
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, RadioField # Keep SubmitField
from wtforms.validators import DataRequired

# AI Trustworthy Characteristics with descriptions
aitc_data = {
    'cbrn': {
        'label': '1. CBRN Information or Capabilities',
        'description': 'Eased access to or synthesis of materially nefarious information or design capabilities, '
                       'related to chemical, biological, radiological, or nuclear (CBRN) weapons or other dangerous materials or agents.'
    },
    'confabulation': {
        'label': '2. Confabulation',
        'description': 'The production of confidently stated but erroneous or false content (known colloquially, ' 
                       'as “hallucinations” or “fabrications”) by which users may be misled or deceived.' # Corrected trailing comma if it was there
    },
    'dangerous_content': {
        'label': '3. Dangerous, Violent, or Hateful Content',
        'description': 'Eased production of and access to violent, inciting, radicalizing, or threatening content, '
                       'as well as recommendations to carry out self-harm or conduct illegal activities. Includes difficulty controlling, '
                       'public exposure to hateful and disparaging or stereotyping content.'
    },
    'data_privacy': {
        'label': '4. Data Privacy',
        'description': 'Impacts due to leakage and unauthorized use, disclosure, or de-anonymization of biometric, health, location, or other personally identifiable information or sensitive data.'
    },
    'environmental_impacts': {
        'label': '5. Environmental Impacts',
        'description': 'Impacts due to high compute resource utilization in training or operating GAI models, and related outcomes that may adversely impact ecosystems.'
    },
    'harmful_bias': {
        'label': '6. Harmful Bias or Homogenization',
        'description': ('Amplification and exacerbation of historical, societal, and ' # Using parentheses for cleaner multi-line
                        'systemic biases; performance disparities between sub-groups or languages, possibly due to '
                        'non-representative training data, that result in discrimination, amplification of biases, or '
                        'incorrect presumptions about performance; undesired homogeneity that skews system or model '
                        'outputs, which may be erroneous, lead to ill-founded decision-making, or amplify harmful biases.')
    },
    'human_ai_config': {
        'label': '7. Human-AI Configuration',
        'description': ('Arrangements of or interactions between a human and an AI system '
                        'which can result in the human inappropriately anthropomorphizing GAI systems or experiencing '
                        'algorithmic aversion, automation bias, over-reliance, or emotional entanglement with GAI systems.')
    },    
    'info_integrity': {
        'label': '8. Information Integrity',
        'description': ('Lowered barrier to entry to generate and support the exchange and '
                        'consumption of content which may not distinguish fact from opinion or fiction or acknowledge '
                        'uncertainties, or could be leveraged for large-scale dis- and mis-information campaigns.')
    },
    'info_security': {
        'label': '9. Information Security',
        'description': ('Lowered barriers for offensive cyber capabilities, including via automated '
                        'discovery and exploitation of vulnerabilities to ease hacking, malware, phishing, offensive cyber operations, or other cyberattacks; increased attack surface for targeted cyberattacks, which may '
                        'compromise a system’s availability or the confidentiality or integrity of training data, code, or model weights.')
    },
    'intellectual_property': {
        'label': '10. Intellectual Property',
        'description': ('Eased production or replication of alleged copyrighted, trademarked, or '
                        'licensed content without authorization (possibly in situations which do not fall under fair use); '
                        'eased exposure of trade secrets; or plagiarism or illegal replication.')
    },
    'obscene_content': {
        'label': '11. Obscene, Degrading, and/or Abusive Content',
        'description': ('Eased production of and access to obscene, '
                        'degrading, and/or abusive imagery which can cause harm, including synthetic child sexual abuse '
                        'material (CSAM), and nonconsensual intimate images (NCII) of adults.')
    },
    'value_chain': {
        'label': '12. Value Chain and Component Integration',
        'description': ('Non-transparent or untraceable integration of '
                        'upstream third-party components, including data that has been improperly obtained or not '
                        'processed and cleaned due to increased automation from GAI; improper supplier vetting across '
                        'the AI lifecycle; or other issues that diminish transparency or accountability for downstream users.')
    }
}

# --- Derive choices for the form directly from aitc_data ---
# This ensures consistency and makes aitc_data the single source of truth for AITC items.
aitc_choices_raw = sorted([(key, data['label']) for key, data in aitc_data.items()], key=lambda item: int(item[1].split('.')[0]))
aitc_choices_form = [('', '-- Select AITC --')] + aitc_choices_raw


# Helper for impact levels
impact_levels_raw = [
    ('N', 'None (N)'),
    ('L', 'Low (L)'),
    ('M', 'Medium (M)'),
    ('H', 'High (H)')
]
impact_levels_form = [('', '-- Select Impact Level --')] + impact_levels_raw


class RiskCalculatorForm(FlaskForm):
    # Base Metrics
    attack_vector = RadioField(
        'Attack Vector (AV)',
        choices=[('IO', 'Internal Only (IO)'), ('IF', 'Internet Facing (IF)')],
        validators=[DataRequired(message="Please select an Attack Vector.")] 
    )
    privileges_required = RadioField(
        'Privileges Required (PR)',
        choices=[('H', 'High (H)'), ('L', 'Low (L)'), ('N', 'None (N)')],
        validators=[DataRequired(message="Please select Privileges Required.")] 
    )
    attack_complexity = RadioField(
        'Attack Complexity (AC)',
        choices=[('L', 'Low (L)'), ('M', 'Medium (M)'), ('H', 'High (H)')],
        validators=[DataRequired(message="Please select Attack Complexity.")] 
    )
    user_interaction = RadioField(
        'User Interaction (UI)',
        choices=[('N', 'None (N)'), ('R', 'Required (R)')],
        validators=[DataRequired(message="Please select User Interaction.")] 
    )

    # Impact Metrics
    aitc = SelectField(
        'AI Trustworthy Characteristic (AITC)',
        choices=aitc_choices_form, # Use choices with placeholder
        validators=[DataRequired(message="Please select an AITC.")]
    )
    characteristic_impact = SelectField(
        'Characteristic Impact (CI)',
        choices=impact_levels_form, # Use choices with placeholder
        validators=[DataRequired(message="Please select Characteristic Impact.")]
    )
    legal_impact = SelectField(
        'Legal Impact (LI)',
        choices=impact_levels_form, # Use choices with placeholder
        validators=[DataRequired(message="Please select Legal Impact.")]
    )

    submit = SubmitField('Calculate Risk Score')