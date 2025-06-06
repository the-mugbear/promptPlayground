# services/common/templating_service.py
from jinja2 import Environment, select_autoescape, StrictUndefined, UndefinedError

jinja_env = Environment(
    loader=None,  # We're loading strings, not files
    autoescape=select_autoescape(default_for_string=False, default=False),
    undefined=StrictUndefined  # Makes it an error if a variable is undefined
)

class TemplateRenderingError(ValueError):
    """Custom error for template rendering issues."""
    pass

def render_string_with_context(template_string: str, context: dict) -> str:
    """
    Renders a Jinja2 template string with the given context.
    Returns the original string if it's None or empty.
    Raises TemplateRenderingError if rendering fails.
    """
    if not template_string: # Handles None or empty string gracefully
        return template_string

    try:
        template = jinja_env.from_string(template_string)
        return template.render(context)
    except UndefinedError as e:
        raise TemplateRenderingError(f"Templating error: Variable '{e.message}' is undefined.") from e
    except Exception as e: # Catch other potential Jinja errors
        raise TemplateRenderingError(f"An unexpected templating error occurred: {e}") from e
