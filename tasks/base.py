# tasks/base.py
import logging
from celery import Task
from celery.result import AsyncResult
from extensions import db

logger = logging.getLogger(__name__)

class ContextTask(Task):
    """
    A Celery Task base class that:
      1. Provides a Flask app context for each task execution.
      2. Allows revocation checks via self.is_revoked().
      3. Ensures SQLAlchemy sessions are cleaned up on task completion.
    """
    abstract = True
    _cached_flask_app = None

    @property
    def flask_app(self):
        if ContextTask._cached_flask_app is None:
            logger.info("ContextTask: Initializing Flask app for Celery worker.")
            # Import here to avoid circular dependencies
            from fuzzy_prompts import create_app
            ContextTask._cached_flask_app = create_app()
        return ContextTask._cached_flask_app

    def is_revoked(self):
        """
        Check Celery backend to see if the current task has been revoked.
        """
        return AsyncResult(self.request.id).state == 'REVOKED'

    def __call__(self, *args, **kwargs):
        with self.flask_app.app_context():
            try:
                return super().__call__(*args, **kwargs)
            finally:
                # Always remove the SQLAlchemy session to return connections to the pool
                db.session.remove()