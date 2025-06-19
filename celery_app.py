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
    include=[
        'tasks.orchestrator',  
        'tasks.case',           
        'tasks.helpers',
        'tasks.batch',
        'tasks.chain_tasks'       
    ]
)

celery.conf.update(
    task_serializer='json',
    result_serializer='json',
    timezone=os.environ.get('CELERY_TIMEZONE', 'UTC'),
    enable_utc=True,
    task_time_limit=600,  # 10 minutes hard limit
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_compression='gzip',
    accept_content=['json', 'application/x-gzip'],
    
    # RabbitMQ/broker configuration
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Message acknowledgment and timeout settings
    worker_prefetch_multiplier=1,  # Process one task at a time to avoid overload
    task_track_started=True,
    
    # Connection pool settings
    broker_pool_limit=10,
    broker_connection_max_retries=5,
    
    # Broker transport options for long-running tasks
    broker_transport_options={
        'visibility_timeout': 3600,  # 1 hour visibility timeout
        'fanout_prefix': True,
        'fanout_patterns': True,
    },
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