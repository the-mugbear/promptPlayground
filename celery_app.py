# celery_app.py
from celery import Celery, Task
import os
import logging # Add logging

logger = logging.getLogger(__name__) # Get a logger for this module too

celery = Celery(
    'fuzzy_prompts',
    broker=os.getenv('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'rpc://'),
    include=['workers.execution_tasks', 'workers.import_tasks']
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=os.environ.get('CELERY_TIMEZONE', 'UTC'),
    enable_utc=True,
)

class ContextTask(Task):
    abstract = True
    _cached_flask_app = None

    @property
    def flask_app(self): # Renamed from 'app'
        if ContextTask._cached_flask_app is None:
            logger.info("ContextTask: Flask app instance not cached by worker, creating new...")
            from fuzzy_prompts import create_app
            app_instance = create_app()
            logger.info(f"ContextTask: create_app() returned type: {type(app_instance)}")
            if not hasattr(app_instance, 'app_context'):
                 logger.critical(f"CRITICAL ERROR in ContextTask: create_app() did not return Flask app. Got: {type(app_instance)}")
            ContextTask._cached_flask_app = app_instance
            logger.info("ContextTask: Flask app instance created and cached by worker.")
        return ContextTask._cached_flask_app
    
    # STUB FUNCTION TO FIX AN ISSUE, CERTAINLY WON'T BITE ME IN THE ASS LATER
    def is_revoked(self):
        """
        Stub to satisfy tasks calling self.is_revoked().
        Celery doesn’t expose an in-task revoke check by default;
        this always returns False unless you override it.
        """
        return getattr(self.request, 'revoked', False)

    def __call__(self, *args, **kwargs):
        # logger.info(f"ContextTask: Task {self.name} (ID: {self.request.id if self.request else 'N/A'}) entering __call__.")
        with self.flask_app.app_context(): # Use the renamed property
            # logger.info(f"ContextTask: Task {self.name} (ID: {self.request.id if self.request else 'N/A'}) has app context. Calling super().__call__...")
            return super().__call__(*args, **kwargs) # CRITICAL: Call parent's __call__

celery.Task = ContextTask