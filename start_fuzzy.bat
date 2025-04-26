@echo off
echo Starting Development Environment...

REM Activate virtual environment (adjust path)
call venv\Scripts\activate

REM Set environment variables
set FLASK_APP=fuzzy_prompts:create_app
set FLASK_DEBUG=True

REM Start Redis (Assumes redis-server.exe is in PATH or provide full path)
REM Starting Redis reliably in the background is trickier on Windows batch
REM Might require running redis-server in a separate cmd window or as a service
echo Starting Redis (Please ensure it's running or start manually)...

REM Start Celery worker - often run in a separate window on Windows without extra tools
echo Starting Celery Worker (Please run in separate terminal)...
REM start "Celery Worker" cmd /c "celery -A celery_app.celery worker --loglevel=info -c 4 -P eventlet" 
REM Using eventlet pool often works better on Windows

REM Start Flask development server
echo Starting Flask App...
flask run --host=0.0.0.0 

echo Flask app stopped. Please stop Celery worker manually if needed.
pause