from jinja2 import Environment, FileSystemLoader, select_autoescape, meta

# Create a single, shared Jinja2 environment when the module is loaded.
_env = Environment(
    loader=FileSystemLoader('.'), # Not actually used since we load from strings
    autoescape=select_autoescape(['html', 'xml'])
)

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