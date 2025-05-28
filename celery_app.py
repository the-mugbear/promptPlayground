# celery_app.py
from celery import Celery, Task
from celery.result import AsyncResult
from extensions import db
import os
import logging # Add logging

logger = logging.getLogger(__name__) # Get a logger for this module too

celery = Celery(
    'fuzzy_prompts',
    broker=os.getenv('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'rpc://'),
    include=['tasks.orchestrator', 'tasks.case', 'tasks.batch', 'tasks.helpers', 'workers.import_tasks', 'tasks.endpoint_tasks']
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
    def flask_app(self):
        if ContextTask._cached_flask_app is None:
            from fuzzy_prompts import create_app
            ContextTask._cached_flask_app = create_app()
        return ContextTask._cached_flask_app
    
    def is_revoked(self):
        """Check Celery’s backend for a revocation flag."""
        return AsyncResult(self.request.id).state == 'REVOKED'

    def __call__(self, *args, **kwargs):
        with self.flask_app.app_context():
            try:
                return super().__call__(*args, **kwargs)
            finally:
                # <— Release ALL connections back into the pool
                db.session.remove()

celery.Task = ContextTask