# app.py
from flask import Flask, render_template
from dbInit import createTables  
from routes.test_suites import test_suites_bp
# from routes.test_cases import test_cases_bp
# from routes.test_executions import test_executions_bp

def create_app():
    app = Flask(__name__)

    # Ensure database tables exist
    createTables("test_database.db")

    # Register Blueprints
    app.register_blueprint(test_suites_bp)
    # app.register_blueprint(test_cases_bp)
    # app.register_blueprint(test_executions_bp)

    # Example index route
    @app.route("/")
    def index():
        return render_template("index.html")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
