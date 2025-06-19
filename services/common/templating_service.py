from jinja2 import Environment, FileSystemLoader, select_autoescape, meta
import json

def json_escape(value):
    """
    Custom Jinja2 filter to properly escape values for JSON strings.
    Handles newlines, quotes, and other control characters.
    """
    if value is None:
        return ""
    # Use json.dumps to properly escape the string, then remove the surrounding quotes
    escaped = json.dumps(str(value))
    return escaped[1:-1]  # Remove surrounding quotes from json.dumps

# Create a single, shared Jinja2 environment when the module is loaded.
_env = Environment(
    loader=FileSystemLoader('.'), # Not actually used since we load from strings
    autoescape=select_autoescape(['html', 'xml'])
)

# Add the custom JSON escape filter
_env.filters['json_escape'] = json_escape

def render_template_string(template_string: str, context: dict) -> str:
    """
    Renders a Jinja2 template string with the given context.
    """
    if not template_string:
        return ""
    template = _env.from_string(template_string)
    return template.render(context)

def get_template_variables(template_string: str) -> set:
    """
    Parses a Jinja2 template string to find all declared variables.
    """
    if not template_string:
        return set()
    
    parsed_content = _env.parse(template_string)
    return meta.find_undeclared_variables(parsed_content)