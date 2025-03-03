from flask import Flask
from flask_migrate import Migrate
from extensions import db
from models import model_TestSuite as TestSuite, model_TestCase as TestCase
from routes.test_suites import test_suites_bp
from routes.test_cases import test_cases_bp
from routes.endpoints import endpoints_bp
from routes.test_runs import test_runs_bp
from routes.core import core_bp
from routes.help import help_bp

migrate = Migrate()  # Instantiate the Migrate object outside create_app

def create_app():
    app = Flask(__name__)
    
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

    # The below is meant to be executed in a terminal/cmd window as is for my awful memory on performing a flask migration
    # flask db init         # creates a migrations folder
    # flask db migrate -m "Initial migration"
    # flask db upgrade      # applies the migration, creating the tables & database file

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
