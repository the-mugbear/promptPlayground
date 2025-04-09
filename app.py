from flask import Flask
from flask_migrate import Migrate
from extensions import db
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
import json

migrate = Migrate()  # Instantiate the Migrate object outside create_app

def create_app():
    app = Flask(__name__)

    def prettyjson_filter(value):
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, indent=2)
        except Exception:
            return value
        
    # Register the prettyjson filter with Jinja
    app.add_template_filter(prettyjson_filter, 'prettyjson')
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fuzzy.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'a_very_secret_key'  # Needed if using session/flash

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

    # The below is meant to be executed in a terminal/cmd window as is for my awful memory on performing a flask migration
    # flask db init         # creates a migrations folder
    # flask db migrate -m "Initial migration"
    # flask db upgrade      # applies the migration, creating the tables & database file

    # flask db stamp head when you modify the database manually and create an ouroboros of suck

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
