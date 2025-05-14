# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
from flask_socketio import SocketIO # Make sure this is here
# --- Initialize extensions ---
db = SQLAlchemy()
migrate = Migrate() 
login_manager = LoginManager() 
csrf = CSRFProtect()
cors = CORS()
socketio = SocketIO() 

# It's good practice to set these here if they are static for the login_manager instance
# Ensure 'auth_bp.login' correctly resolves to your login route.
login_manager.login_view = 'auth_bp.login'
login_manager.login_message_category = 'info'
# The @login_manager.user_loader decorator will remain in fuzzy_prompts.py (or wherever User model is accessible)
# because it needs to be associated with the login_manager instance after it's created.