#!/bin/bash
echo "Starting Development Environment..."

# Activate virtual environment (adjust path if needed)
source venv/bin/activate 

# Set FLASK_APP (using .flaskenv is usually better, but can be explicit)
export FLASK_APP=fuzzy_prompts:create_app
export FLASK_DEBUG=True 

# Start Redis server in the background (example, assumes redis-server is in PATH)
# You might need a better way to check if it's already running
echo "Starting Redis (if not running)..."
redis-server --daemonize yes --loglevel notice --logfile redis.log # Example background start

# Start Celery worker in the background
# Use -c 1 for SQLite or appropriate number for PostgreSQL
echo "Starting Celery Worker (check celery.log)..."
celery -A celery_app.celery worker --loglevel=info -c 4 --logfile=celery.log --pidfile=celery.pid & # Run in background
CELERY_PID=$! # Get Celery process ID

# Start Flask development server in the foreground
echo "Starting Flask App..."
flask run --host=0.0.0.0 # Use 0.0.0.0 if running in Docker/VM

# Cleanup when Flask server exits (Ctrl+C)
echo "Flask App stopped. Stopping Celery worker..."
kill $CELERY_PID
# Optionally stop Redis if started by script
# redis-cli shutdown
echo "Cleanup complete."