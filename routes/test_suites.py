from flask import Blueprint, request, jsonify, render_template
import sqlite3
from datetime import datetime
from dbInit import get_db_connection  # or wherever your DB logic is

test_suites_bp = Blueprint(
    "test_suites_bp",  # Blueprint name
    __name__,
    url_prefix="/test_suites"  # All routes here will be prefixed with /test_suites
)

@test_suites_bp.route("/", methods=["GET", "POST"])
def handle_test_suites():
    """
    GET  /test_suites        -> Get a list of all test suites
    POST /test_suites        -> Create a new test suite
    """
    if request.method == "GET":
        conn = get_db_connection()
        rows = conn.execute("SELECT * FROM test_suites").fetchall()
        conn.close()
        suites = [dict(row) for row in rows]
        return jsonify(suites), 200

    if request.method == "POST":
        data = request.get_json()
        description = data.get("description")
        behavior = data.get("behavior")
        attack = data.get("attack")
        created_at = data.get("created_at", datetime.utcnow().isoformat())

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO test_suites (description, behavior, attack, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (description, behavior, attack, created_at)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()

        return jsonify({"id": new_id, "message": "Test suite created"}), 201

@test_suites_bp.route("/<int:suite_id>", methods=["GET", "PUT", "DELETE"])
def handle_single_test_suite(suite_id):
    """
    GET    /test_suites/<id> -> Get details of a specific test suite
    PUT    /test_suites/<id> -> Update an existing test suite
    DELETE /test_suites/<id> -> Delete a test suite
    """
    if request.method == "GET":
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM test_suites WHERE id = ?", (suite_id,)).fetchone()
        conn.close()

        if row is None:
            return jsonify({"error": "Test suite not found"}), 404
        return jsonify(dict(row)), 200

    elif request.method == "PUT":
        data = request.get_json()
        description = data.get("description")
        behavior = data.get("behavior")
        attack = data.get("attack")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE test_suites
            SET description = ?, behavior = ?, attack = ?
            WHERE id = ?
            """,
            (description, behavior, attack, suite_id)
        )
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()

        if rows_affected == 0:
            return jsonify({"error": "Test suite not found"}), 404
        return jsonify({"message": "Test suite updated"}), 200

    elif request.method == "DELETE":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM test_suites WHERE id = ?", (suite_id,))
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()

        if rows_affected == 0:
            return jsonify({"error": "Test suite not found"}), 404
        return jsonify({"message": "Test suite deleted"}), 200

@test_suites_bp.route("/create", methods=["GET", "POST"])
def create_test_suite():
    """
    GET  /test_suites/create  -> Show form to create a new test suite
    POST /test_suites/create  -> Handle form submission and insert new suite
    """
    if request.method == "GET":
        # Render an HTML form (e.g., templates/TestSuites/create_suite.html)
        return render_template("TestSuites/create_suite.html")

    elif request.method == "POST":
        # Parse form data
        description = request.form.get("description")
        behavior = request.form.get("behavior")
        attack = request.form.get("attack")
        created_at = datetime.utcnow().isoformat()

        # Insert into the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO test_suites (description, behavior, attack, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (description, behavior, attack, created_at)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()

        # You could redirect somewhere (e.g., /test_suites/<new_id>)
        return redirect(url_for('test_suites_bp.handle_single_test_suite', suite_id=new_id))