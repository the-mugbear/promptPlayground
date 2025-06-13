# tasks/chain_tasks.py
import logging
from celery_app import celery
from tasks.base import ContextTask
from services.chain_execution_service import APIChainExecutor

logger = logging.getLogger(__name__)

@celery.task(bind=True, base=ContextTask, name='tasks.execute_full_chain_run')
def execute_full_chain_run(self, chain_id: int):
    """
    Executes a full API chain asynchronously.
    """
    logger.info(f"Starting full asynchronous run for Chain ID: {chain_id}")
    try:
        executor = APIChainExecutor()
        # Here you would eventually save the results to a new "ChainRunLog" model
        results = executor.execute_chain(chain_id)
        logger.info(f"Full chain run completed for Chain ID: {chain_id}. "
                    f"Final context keys: {list(results.get('final_context', {}).keys())}")
        return {'status': 'SUCCESS', 'chain_id': chain_id}
    except Exception as e:
        logger.error(f"Full chain run failed for Chain ID: {chain_id}", exc_info=True)
        # Handle failure, maybe update a status field on a tracking model
        return {'status': 'FAILURE', 'error': str(e)}