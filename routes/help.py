from flask import Blueprint, render_template, send_from_directory, flash, redirect, url_for
from flask_login import login_required
from models.model_TestCase import TestCase
from extensions import db
from sqlalchemy import text 

help_bp = Blueprint('help_bp', __name__, url_prefix='/help')

# ********************************
# ROUTES
# ********************************
@help_bp.route('/index')
def index():
    return render_template('help/index.html')

# Plugin Support
@help_bp.route('/plugin')
def plugin():
    return render_template('help/post_inspector.html')

# Learn the steps to configure and execute a test run.
@help_bp.route('/create_test_run')
def create_test_run():
    return render_template('help/create_test_run.html')

# Instructions on creating, testing, and deleting endpoints.
@help_bp.route('/manage_endpoints')
def manage_endpoints():
    return render_template('help/manage_endpoints.html')

# Guide on adding new transformations and registering them for use in suite creation
@help_bp.route('/using_transformations')
def using_transformations():
    return render_template('help/using_transformations.html')

# Guide on importing test suites
@help_bp.route('/test_suite_import')
def test_suite_import():
    return render_template('help/test_suite_import.html')

# Guide on adding new transformations and registering them for use in suite creation
@help_bp.route('/adding_transformers')
def adding_transformers():
    return render_template('help/adding_transformers.html')

# Understand the execution status, response codes, and more.
@help_bp.route('/results')
def results():
    return render_template('help/results.html')

# Citations / Resource Links
@help_bp.route('/citations')
def citations():
    research_items = [
        {
            "title": "Best-of-N Jailbreaking",
            "url": "https://jplhughes.github.io/bon-jailbreaking/",
            "description": "...a simple black-box algorithm that jailbreaks frontier AI systems across modalities. BoN Jailbreaking works by repeatedly "
            "sampling variations of a prompt with a combination of augmentations - such as random shuffling or capitalization for textual prompts - until "
            "a harmful response is elicited..."
        },
        {
            "title": "JailbreakBench",
            "url": "https://github.com/JailbreakBench/jailbreakbench",
            "description": "Jailbreakbench is an open-source robustness benchmark for jailbreaking large language models (LLMs). The goal of this benchmark "
            "is to comprehensively track progress toward (1) generating successful jailbreaks and (2) defending against these jailbreaks."
        }
    ]
    return render_template('help/citations.html', research_items=research_items)



# ********************************
# SERVICES
# ********************************
@help_bp.route('/download_extension')
def download_extension():
    return send_from_directory('static', 'POSTInspector.xpi', as_attachment=True)

@help_bp.route('/purge')
@login_required
def purge():
    orphaned_test_cases = TestCase.query.filter(~TestCase.test_suites.any()).all()
    count = len(orphaned_test_cases)
    if count > 0:
        for test_case in orphaned_test_cases:
            db.session.delete(test_case)
        db.session.commit()
        flash(f"Purged {count} orphaned test case(s) from the database.", "success")
    else:
        flash("No orphaned test cases found.", "info")
    return redirect(url_for('help_bp.index'))

# --- NEW ROUTE for VACUUM ---
@help_bp.route('/vacuum', methods=['POST']) # Use POST to prevent accidental execution
@login_required
def vacuum_database():
    """
    Executes the VACUUM command on the SQLite database.
    """
    print("Attempting to VACUUM database...") # Add logging
    try:
        # Get the underlying SQLAlchemy engine
        engine = db.engine 
        # Execute the VACUUM command directly
        # Using 'with engine.connect()' ensures connection is closed
        with engine.connect() as connection:
             # Need transaction for VACUUM in some contexts
             with connection.begin():
                 connection.execute(text("VACUUM"))
        
        flash("Database VACUUM command executed successfully. Unused space has been reclaimed.", "success")
        print("VACUUM command completed.")
    except Exception as e:
        db.session.rollback() # Rollback any potential session state issues
        flash(f"Error executing VACUUM command: {str(e)}", "error")
        print(f"Error during VACUUM: {e}")
    
    return redirect(url_for('help_bp.index')) # Redirect back to the help index