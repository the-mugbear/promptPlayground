# fuzzy_prompts.py

import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import current_user
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

# --- Load environment variables from .env file FIRST ---
load_dotenv()

# --- Import extensions (these should be instantiated in extensions.py) ---
from extensions import db, migrate, login_manager, csrf, cors, socketio 
from celery_app import celery # Celery application instance

# --- Import Models (only User needed for load_user here) ---
from models.model_User import User 

# --- Import Blueprints ---
from routes.core import core_bp
from routes.auth import auth_bp
from routes.user import user_bp
from routes.admin import admin_bp
from routes.endpoints import endpoints_bp
from routes.test_cases import test_cases_bp
from routes.test_suites import test_suites_bp
from routes.test_runs import test_runs_bp
from routes.prompt_filter import prompt_filter_bp
from routes.reports import report_bp 
from routes.help import help_bp
from routes.testing_grounds import testing_grounds_bp
from routes.dialogues import dialogue_bp
from routes.attacks.evil_agent import evil_agent_bp
from routes.attacks.best_of_n import best_of_n_bp
from routes.utilities.utils import utils_bp

# --- Import CLI commands blueprint/registration function ---
from commands import bp as commands_bp

# --- Import SocketIO event handlers (create this file next) ---
import socket_events

# === Configuration Class ===
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set for Flask application. Please set it in .env or environment.")

    # Database Configuration
    DATABASE_URL_ENV = os.environ.get('DATABASE_URL')
    if DATABASE_URL_ENV:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL_ENV.replace("postgresql://", "postgresql+psycopg2://", 1) \
            if DATABASE_URL_ENV.startswith("postgresql://") else DATABASE_URL_ENV
    else:
        DB_USER = os.environ.get('DB_USER', 'fuzzy_user')
        DB_PASSWORD = os.environ.get('DB_PASSWORD')
        DB_HOST = os.environ.get('DB_HOST', 'localhost')
        DB_PORT = os.environ.get('DB_PORT', '5432')
        DB_NAME = os.environ.get('DB_NAME', 'fuzzy_prompts_db')
        if not DB_PASSWORD:
            raise ValueError("DB_PASSWORD environment variable not set and DATABASE_URL not found.")
        SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size":      20,
        "max_overflow":   40,
        "pool_timeout":   30,
        "pool_recycle":   1800,
    }

    # Celery Configuration (pointing to RabbitMQ)
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'rpc://') # RabbitMQ RPC for results

    # SocketIO Message Queue using RabbitMQ
    SOCKETIO_MESSAGE_QUEUE_URL = os.environ.get('SOCKETIO_MESSAGE_QUEUE_URL', 'amqp://guest:guest@localhost:5672//')

    # Upload Folder Configuration
    # Correctly use app.instance_path later if instance_relative_config=True
    UPLOAD_FOLDER_NAME = 'uploads' # Relative to instance path
    ALLOWED_EXTENSIONS = {'txt', 'csv', 'json', 'yaml', 'yml'}

    # Flask Debug Mode
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')


# === User Loader for Flask-Login ===
# login_manager instance should be from extensions.py
@login_manager.user_loader
def load_user_callback(user_id): # Renamed to avoid conflict if 'load_user' is a common name
    """Loads the user object from the user ID stored in the session."""
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        # It's better to log to app.logger once app context is available
        print(f"Error loading user {user_id}: {e}")
        return None
    
# Define the formatting function outside the context processor
# so it can be used by both the context processor and for filter registration.
def _format_timedelta_helper(delta_obj): # Renamed slightly to avoid confusion
    if not isinstance(delta_obj, timedelta):
        return "N/A"
    total_seconds = int(delta_obj.total_seconds())
    
    if total_seconds < 0: # Handle negative timedeltas gracefully
        return "Invalid (negative)"
        
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    elif minutes > 0:
        return f"{minutes:02d}m {seconds:02d}s"
    return f"{seconds:02d}s"

# === Application Factory ===
def create_app(config_object=Config): # Pass the class itself
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object) # Load config from the class

    # Register your custom filter
    # The first argument is the function, the second is the name used in templates
    app.add_template_filter(_format_timedelta_helper, 'format_timedelta_custom')

    # --- Create instance folder and UPLOAD_FOLDER if they don't exist ---
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        upload_path = os.path.join(app.instance_path, app.config['UPLOAD_FOLDER_NAME'])
        os.makedirs(upload_path, exist_ok=True)
        app.config['UPLOAD_FOLDER'] = upload_path # Set absolute path for UPLOAD_FOLDER
    except OSError as e:
        app.logger.error(f"Error creating instance path or upload folder: {e}")


    # --- Initialize extensions with the app ---
    db.init_app(app)
    migrate.init_app(app, db) # migrate instance from extensions.py
    login_manager.init_app(app) # login_manager instance from extensions.py
    csrf.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}) # Your existing CORS setup

    # Initialize SocketIO
    # async_mode='eventlet' is recommended for performance with eventlet server
    socketio.init_app(app, message_queue=app.config['SOCKETIO_MESSAGE_QUEUE_URL'], async_mode='eventlet')

    # --- Configure Celery ---
    # Update the imported Celery instance's configuration
    celery.conf.update(
        broker_url=app.config['CELERY_BROKER_URL'],
        result_backend=app.config['CELERY_RESULT_BACKEND']
        # You can add other Celery-specific settings from app.config if needed:
        # task_always_eager=app.config.get('CELERY_TASK_ALWAYS_EAGER', False),
    )

    # --- Register Jinja Filters ---
    def prettyjson_filter(value):
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, indent=2, sort_keys=True)
        except (TypeError, json.JSONDecodeError):
            return value
    app.add_template_filter(prettyjson_filter, 'prettyjson')

    # --- Register Blueprints ---
    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(endpoints_bp)
    app.register_blueprint(test_cases_bp)
    app.register_blueprint(test_suites_bp)
    app.register_blueprint(test_runs_bp)
    app.register_blueprint(prompt_filter_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(testing_grounds_bp)
    app.register_blueprint(dialogue_bp) 
    app.register_blueprint(evil_agent_bp)
    app.register_blueprint(best_of_n_bp)
    app.register_blueprint(commands_bp) 
    app.register_blueprint(utils_bp)

    # --- Application-Level Error Handlers ---
    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f'Server Error: {error}', exc_info=True)
        db.session.rollback() # Rollback session in case of DB error during request
        return render_template('errors/500.html', error=error), 500

    @app.errorhandler(404)
    def page_not_found(error):
        app.logger.info(f'Page not found: {request.url}')
        return render_template('errors/404.html', error=error), 404
    
    # Defines a whitelist of public blueprints and endpoints
    @app.before_request
    def require_login_globally():
        
        public_blueprints = {
            'auth_bp',
            'utils_bp'
        }
        public_endpoints = {
            'static',
            'auth_bp.login',
            'auth_bp.register_with_code',
        }

        # Grab the current request’s blueprint and endpoint
        bp = request.blueprint   # e.g. 'auth_bp', 'test_runs_bp', or None
        endpoint  = request.endpoint    # e.g. 'auth_bp.login', 'test_runs_bp.view_test_run'

        # # Logging for every request
        # print(f"--- Request Start ---")
        # print(f"Path: {request.path}, Method: {request.method}")
        # print(f"Endpoint: {endpoint}, Blueprint: {bp}")
        # print(f"Content-Type: {request.content_type}, is_json: {request.is_json}")
        # print(f"X-Requested-With: {request.headers.get('X-Requested-With')}")
        # print(f"User Authenticated: {current_user.is_authenticated}")
        # # ------------------------

        is_public_route = (bp in public_blueprints) or (endpoint in public_endpoints)
        if endpoint == 'static': # Static files are always public
            is_public_route = True
        # print(f"Is Public Route? {is_public_route}")

        if not current_user.is_authenticated and not is_public_route:
            print(f"User NOT authenticated for PROTECTED endpoint: {endpoint}")

            is_ajax_request = (
                (request.content_type and 'application/json' in request.content_type.lower()) or
                request.is_json or
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                (request.accept_mimetypes.best and 'application/json' in request.accept_mimetypes.best.lower())
            )
            print(f"Determined is_ajax_request: {is_ajax_request}")

            if is_ajax_request:
                print("Returning 401 JSON for AJAX")
                return jsonify(message='Authentication required. Please log in.', error_code='AUTH_REQUIRED'), 401
            else:
                print(f"Redirecting to login for non-AJAX from: {request.url}")
                return redirect(url_for('auth_bp.login', next=request.url))

        # print(f"--- Request Allowed (User Auth: {current_user.is_authenticated}, Public: {is_public_route}) ---")
        # If we reach here, the request proceeds to the view function or next before_request handler.

    # --- User Loader configuration (moved login_manager.init_app above) ---
    # login_manager.login_view = 'auth_bp.login' # Set this on the login_manager instance in extensions.py
    # login_manager.login_message_category = 'info' # Set this on the login_manager instance in extensions.py

    return app

# --- Create the Flask app instance ---
app = create_app()

# --- Main execution block ---
if __name__ == '__main__':
    # Use socketio.run() for development, which uses eventlet due to async_mode
    print(f"Starting Flask-SocketIO server (debug={app.config['DEBUG']}) with eventlet...")
    socketio.run(app,
                 host='0.0.0.0',
                 port=int(os.environ.get('PORT', 5000)), # Use PORT env var or default to 5000
                 debug=app.config['DEBUG'],
                 use_reloader=app.config['DEBUG']) 