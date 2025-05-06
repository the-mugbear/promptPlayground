# celery_app.py
from celery import Celery
import os

# Define Celery instance here
# Use environment variables for broker/backend defaults if possible
celery = Celery(
    'fuzzy_prompts',
    broker=os.getenv('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//'), # Default to AMQP
    backend=os.getenv('CELERY_RESULT_BACKEND'), # Default to None - rely on .env
    include=[
        'workers.execution_tasks',
        'workers.import_tasks'
        ]
)

# Create a custom Task base class that pushes app context
class ContextTask(celery.Task):
    abstract = True # Prevent this from being registered as an independent task
    _flask_app = None # Optional: Cache the app instance per worker process

    # Use a property to create the app on first access within a worker process
    @property
    def flask_app(self):
        if self._flask_app is None:
            print("Flask app not cached in worker, creating context...")
            # Import the factory function *here* to avoid circular imports at module level
            from fuzzy_prompts import create_app
            self._flask_app = create_app()
            print("Flask app created for Celery context.")
        return self._flask_app

    # Override __call__ to wrap task execution in app context
    def __call__(self, *args, **kwargs):
        with self.flask_app.app_context():
            # print(f"Executing task {self.name} within Flask app context") # Optional debug print
            return self.run(*args, **kwargs)

# Set the custom class as the default Task base for this Celery instance
celery.Task = ContextTask
# -----------------------------------