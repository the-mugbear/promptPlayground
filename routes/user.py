# routes/user.py
from flask import Blueprint, render_template

user_bp = Blueprint(
    'user_bp',
    __name__,
    template_folder='../templates/user',
    url_prefix='/user'
)

@user_bp.route('/profile')
def profile():
    """Displays the logged-in user's profile page.
    The 'current_user' object (provided by Flask-Login) is automatically
    available in the template context if the user is logged in.
    """
    return render_template('profile.html', title='My Profile') 