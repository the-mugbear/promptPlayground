from flask import Blueprint, render_template, abort

core_bp = Blueprint('core_bp', __name__)

# ********************************
# ROUTES
# ********************************
@core_bp.route('/')
def index():
    return render_template('index.html')

@core_bp.route('/visual/<effect>')
def visual(effect):
    # List of available visual effects
    valid_effects = ['matrix_rain', 'neon_grid_glitch', 'neon_circles', '8_bit_fire']
    if effect not in valid_effects:
        abort(404)
    # Render the corresponding template, e.g., matrix_rain.html
    return render_template(f"testing_grounds/{effect}.html")
