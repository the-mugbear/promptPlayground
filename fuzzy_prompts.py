from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from celery_app import celery
from extensions import db
from dotenv import load_dotenv

from routes.test_suites import test_suites_bp
from routes.test_cases import test_cases_bp
from routes.endpoints import endpoints_bp
from routes.test_runs import test_runs_bp
from routes.core import core_bp
from routes.help import help_bp
from routes.reports import report_bp
from routes.evil_agent import evil_agent_bp
from routes.best_of_n import best_of_n_bp
from routes.testing_grounds import testing_grounds_bp
from routes.dialogues import dialogue_bp
from routes.prompt_filter import prompt_filter_bp

from workers import celery_tasks

import json
import os

# --- Load environment variables from .env file ---
load_dotenv() 
# -------------------------------------------------

migrate = Migrate()  # Instantiate the Migrate object outside create_app

def create_app():

    app = Flask(__name__)

    # TODO: refactor this out later
    def prettyjson_filter(value):
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, indent=2)
        except Exception:
            return value
        
    # Register the prettyjson filter with Jinja
    app.add_template_filter(prettyjson_filter, 'prettyjson')
    
    # --- Load Configuration from Environment Variables ---
    # Use os.getenv('VARIABLE_NAME', 'optional_default_value')
    db_user = os.getenv('DB_USER', 'fuzzy_user') 
    db_pass = os.getenv('DB_PASSWORD') # No default for password is safer
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'fuzzy_prompts_db')

    # ---- TEMPORARY DEBUG ----
    print(f"DEBUG: Connecting with User='{db_user}', Password='{db_pass}'") 
    # -------------------------

    # Check if password was loaded
    if not db_pass:
        raise ValueError("DB_PASSWORD environment variable not set.")
        
    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Load Secret Key (provide a default ONLY for development if necessary, error out otherwise)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') 
    if not app.config['SECRET_KEY']:
         raise ValueError("SECRET_KEY environment variable not set.")
    # Optional: Load Flask debug status
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    # -----------------------------------------------------

    # --- Load Celery Config from Flask Config ---
    # Ensure these are set in your .env or environment
    app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//') # Default to AMQP
    app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND') # Default to None
    # Optional: Add other Celery settings to Flask config

    # --- Update the IMPORTED celery instance's config ---
    celery.conf.update(broker_url=app.config['CELERY_BROKER_URL'],
                       result_backend=app.config['CELERY_RESULT_BACKEND'])
    celery.conf.update(app.config) # Also apply other Flask config settings if needed
    # -----------------------------------------------------

    # Initialize SQLAlchemy
    db.init_app(app)
    # Initialize Flask-Migrate
    migrate.init_app(app, db)

    # Register your blueprint(s)
    app.register_blueprint(core_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(test_suites_bp)
    app.register_blueprint(test_cases_bp)
    app.register_blueprint(endpoints_bp)
    app.register_blueprint(test_runs_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(evil_agent_bp)
    app.register_blueprint(best_of_n_bp)
    app.register_blueprint(testing_grounds_bp)
    app.register_blueprint(dialogue_bp)
    app.register_blueprint(prompt_filter_bp)

    # --- Define APPLICATION-LEVEL Error Handlers ---
    @app.errorhandler(500)
    def internal_server_error(error):
        # You *should* log the error in a real app! (no!)
        app.logger.error(f'Server Error: {error}', exc_info=True)
        return render_template('errors/500.html', error=error), 500

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('errors/404.html', error=error), 404

    # The below is meant to be executed in a terminal/cmd window as is for my awful memory on performing a flask migration
    # flask db init         # creates a migrations folder
    # flask db migrate -m "Initial migration"
    # flask db upgrade      # applies the migration, creating the tables & database file
    # flask db stamp head when you modify the database manually and create an ouroboros of suck

    return app

    # when troubleshooting flask 
    # PS
    # Get-ChildItem Env:FLASK_APP
    # $env:FLASK_APP = "fuzzy_prompts:create_app";

if __name__ == '__main__':
    app = create_app()
    # Use the loaded config value for debug mode
    app.run(debug=app.config.get('DEBUG', True)) 
