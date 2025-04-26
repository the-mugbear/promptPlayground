# celery_app.py
from celery import Celery
import os

# Define Celery instance here
# Use environment variables for broker/backend defaults if possible
celery = Celery(
    'fuzzy_prompts', # Or keep using __name__ if preferred, but main app name is common
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['workers.celery_tasks'] # Tell Celery where to auto-discover tasks
)

# Optional: Set some default configurations directly if needed
# celery.conf.update(
#     task_track_started=True,
#     # Add other default Celery settings here
# )

# Note: We don't configure it with Flask app config here.
# That happens inside create_app using this imported instance.