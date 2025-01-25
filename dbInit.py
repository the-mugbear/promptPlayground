import sqlite3

def createTables(db_name="test_database.db"):

    # Connect to the SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(db_name)
    # Enable foreign key support
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Create the test_suites table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_suites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT,
        behavior TEXT,
        attack TEXT,
        created_at DATETIME
    );
    """)

    # Create the test_cases table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt TEXT,
        created_at DATETIME
    );
    """)

    # Create the join table for TestSuites <-> TestCases (many-to-many)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_suites_test_cases (
        test_suite_id INTEGER NOT NULL,
        test_case_id INTEGER NOT NULL,
        PRIMARY KEY (test_suite_id, test_case_id),
        FOREIGN KEY (test_suite_id) REFERENCES test_suites(id) ON DELETE CASCADE,
        FOREIGN KEY (test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE
    );
    """)

    # Create the test_executions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT,
        created_at DATETIME,
        completed_at DATETIME
    );
    """)

    # Create the join table for TestExecutions <-> TestSuites
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_executions_test_suites (
        test_execution_id INTEGER NOT NULL,
        test_suite_id INTEGER NOT NULL,
        PRIMARY KEY (test_execution_id, test_suite_id),
        FOREIGN KEY (test_execution_id) REFERENCES test_executions(id) ON DELETE CASCADE,
        FOREIGN KEY (test_suite_id) REFERENCES test_suites(id) ON DELETE CASCADE
    );
    """)

    # Create the table for storing execution results for each test case
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_execution_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_execution_id INTEGER NOT NULL,
        test_case_id INTEGER NOT NULL,
        response TEXT,
        evaluation TEXT,
        response_received_at DATETIME,
        FOREIGN KEY (test_execution_id) REFERENCES test_executions(id) ON DELETE CASCADE,
        FOREIGN KEY (test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE
    );
    """)

    # Commit changes and close
    conn.commit()
    conn.close()
    
def get_db_connection(db_name="test_database.db"):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn
