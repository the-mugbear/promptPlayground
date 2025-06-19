# services/execution/tasks.py
"""
Lightweight task executors for the new execution engine

These tasks replace the heavy orchestration logic with simple, focused execution tasks
that work with the strategy-based execution system.
"""

import logging
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

import celery
from celery import Task

from ..chain_execution_service import ChainExecutionService
from ..http_request_service import HTTPRequestService  
from .models import ExecutionContext, TaskResult

logger = logging.getLogger(__name__)


class ExecutionTask(Task):
    """Base task class for execution tasks with context handling"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failures"""
        logger.error(f"Task {task_id} failed: {exc}")
        
        # Try to extract execution context and report failure
        try:
            if args and isinstance(args[0], dict):
                context_dict = args[0]
                execution_id = context_dict.get('execution_id', 'unknown')
                test_case_id = context_dict.get('test_case_id', 0)
                
                # Create failure result
                failure_result = TaskResult(
                    execution_id=execution_id,
                    test_case_id=test_case_id,
                    sequence_num=context_dict.get('sequence_num', 0),
                    iteration_num=context_dict.get('iteration_num', 1),
                    success=False,
                    error_message=str(exc),
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow()
                )
                
                # Notify execution engine of failure (simplified)
                logger.error(f"Task failure recorded for execution {execution_id}")
                
        except Exception as e:
            logger.error(f"Failed to handle task failure: {e}")


@celery.task(bind=True, base=ExecutionTask, name='execution.execute_single_request')
def execute_single_request(self, context_dict: Dict[str, Any], endpoint_dict: Dict[str, Any], 
                          test_case_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single HTTP request with the new execution system
    
    Args:
        context_dict: ExecutionContext as dictionary
        endpoint_dict: Endpoint configuration
        test_case_dict: Test case data
        
    Returns:
        TaskResult as dictionary
    """
    started_at = datetime.utcnow()
    execution_id = context_dict.get('execution_id', 'unknown')
    test_case_id = context_dict.get('test_case_id', 0)
    
    logger.info(f"Executing single request for test case {test_case_id} (execution: {execution_id})")
    
    try:
        # Apply pre-request delay from execution context
        delay = context_dict.get('delay', 0.0)
        if delay > 0:
            logger.debug(f"Applying delay of {delay}s before request")
            time.sleep(delay)
        
        # Extract request configuration
        request_config = context_dict.get('request_config', {})
        
        # Build request parameters
        url = endpoint_dict.get('url', '')
        method = endpoint_dict.get('method', 'GET')
        headers = request_config.get('headers', {})
        payload = request_config.get('payload', {})
        timeout = context_dict.get('timeout', 30)
        
        # Apply test case specific data
        if test_case_dict.get('headers'):
            headers.update(test_case_dict['headers'])
        if test_case_dict.get('payload'):
            if isinstance(payload, dict) and isinstance(test_case_dict['payload'], dict):
                payload.update(test_case_dict['payload'])
            else:
                payload = test_case_dict['payload']
        
        # Execute HTTP request
        http_service = HTTPRequestService()
        response = http_service.make_request(
            url=url,
            method=method,
            headers=headers,
            payload=payload,
            timeout=timeout
        )
        
        # Extract response data
        status_code = getattr(response, 'status_code', None)
        response_text = getattr(response, 'text', '')
        response_headers = dict(getattr(response, 'headers', {}))
        
        # Calculate response time (simplified)
        completed_at = datetime.utcnow()
        response_time = (completed_at - started_at).total_seconds()
        
        # Determine success
        success = status_code is not None and 200 <= status_code < 400
        
        # Create result
        result = TaskResult(
            execution_id=execution_id,
            test_case_id=test_case_id,
            sequence_num=context_dict.get('sequence_num', 0),
            iteration_num=context_dict.get('iteration_num', 1),
            status_code=status_code,
            response_body=response_text,
            response_headers=response_headers,
            response_time=response_time,
            success=success,
            started_at=started_at,
            completed_at=completed_at
        )
        
        logger.info(f"Request completed for test case {test_case_id}: "
                   f"status={status_code}, time={response_time:.2f}s, success={success}")
        
        # Return as dictionary for Celery serialization
        return {
            'execution_id': result.execution_id,
            'test_case_id': result.test_case_id,
            'sequence_num': result.sequence_num,
            'iteration_num': result.iteration_num,
            'status_code': result.status_code,
            'response_body': result.response_body,
            'response_headers': result.response_headers,
            'response_time': result.response_time,
            'success': result.success,
            'error_message': result.error_message,
            'started_at': result.started_at.isoformat(),
            'completed_at': result.completed_at.isoformat(),
            'retry_count': result.retry_count
        }
        
    except Exception as e:
        logger.error(f"Request execution failed for test case {test_case_id}: {e}")
        logger.debug(traceback.format_exc())
        
        completed_at = datetime.utcnow()
        response_time = (completed_at - started_at).total_seconds()
        
        # Create failure result
        failure_result = TaskResult(
            execution_id=execution_id,
            test_case_id=test_case_id,
            sequence_num=context_dict.get('sequence_num', 0),
            iteration_num=context_dict.get('iteration_num', 1),
            success=False,
            error_message=str(e),
            response_time=response_time,
            started_at=started_at,
            completed_at=completed_at
        )
        
        return {
            'execution_id': failure_result.execution_id,
            'test_case_id': failure_result.test_case_id,
            'sequence_num': failure_result.sequence_num,
            'iteration_num': failure_result.iteration_num,
            'status_code': failure_result.status_code,
            'response_body': failure_result.response_body,
            'response_headers': failure_result.response_headers,
            'response_time': failure_result.response_time,
            'success': failure_result.success,
            'error_message': failure_result.error_message,
            'started_at': failure_result.started_at.isoformat(),
            'completed_at': failure_result.completed_at.isoformat(),
            'retry_count': failure_result.retry_count
        }


@celery.task(bind=True, base=ExecutionTask, name='execution.execute_chain_instance')
def execute_chain_instance(self, context_dict: Dict[str, Any], chain_dict: Dict[str, Any], 
                          test_case_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a complete chain instance with sequential step execution
    
    Args:
        context_dict: ExecutionContext as dictionary
        chain_dict: Chain configuration and steps
        test_case_dict: Test case data
        
    Returns:
        TaskResult as dictionary
    """
    started_at = datetime.utcnow()
    execution_id = context_dict.get('execution_id', 'unknown')
    test_case_id = context_dict.get('test_case_id', 0)
    
    logger.info(f"Executing chain instance for test case {test_case_id} (execution: {execution_id})")
    
    try:
        # Apply pre-chain delay
        delay = context_dict.get('delay', 0.0)
        if delay > 0:
            logger.debug(f"Applying delay of {delay}s before chain execution")
            time.sleep(delay)
        
        # Execute chain using existing chain execution service
        chain_service = ChainExecutionService()
        
        # Convert dictionaries back to objects (simplified)
        # In actual implementation, these would be proper model objects
        class MockChain:
            def __init__(self, chain_dict):
                self.id = chain_dict.get('id', 0)
                self.steps = chain_dict.get('steps', [])
                self.step_delay = chain_dict.get('step_delay', 0.3)
        
        class MockTestCase:
            def __init__(self, test_case_dict):
                self.id = test_case_dict.get('id', 0)
                self.payload = test_case_dict.get('payload', {})
                self.headers = test_case_dict.get('headers', {})
        
        chain = MockChain(chain_dict)
        test_case = MockTestCase(test_case_dict)
        
        # Execute the chain
        chain_result = chain_service.execute_chain(
            chain=chain,
            test_case=test_case,
            context=context_dict
        )
        
        # Extract chain execution results
        success = chain_result.get('success', False)
        status_code = chain_result.get('final_status_code', 200 if success else 500)
        response_body = chain_result.get('final_response', '')
        total_response_time = chain_result.get('total_execution_time', 0.0)
        error_message = chain_result.get('error_message')
        
        completed_at = datetime.utcnow()
        
        # Create result
        result = TaskResult(
            execution_id=execution_id,
            test_case_id=test_case_id,
            sequence_num=context_dict.get('sequence_num', 0),
            iteration_num=context_dict.get('iteration_num', 1),
            status_code=status_code,
            response_body=response_body,
            response_time=total_response_time,
            success=success,
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at
        )
        
        logger.info(f"Chain execution completed for test case {test_case_id}: "
                   f"success={success}, time={total_response_time:.2f}s, steps={len(chain.steps)}")
        
        return {
            'execution_id': result.execution_id,
            'test_case_id': result.test_case_id,
            'sequence_num': result.sequence_num,
            'iteration_num': result.iteration_num,
            'status_code': result.status_code,
            'response_body': result.response_body,
            'response_headers': result.response_headers,
            'response_time': result.response_time,
            'success': result.success,
            'error_message': result.error_message,
            'started_at': result.started_at.isoformat(),
            'completed_at': result.completed_at.isoformat(),
            'retry_count': result.retry_count
        }
        
    except Exception as e:
        logger.error(f"Chain execution failed for test case {test_case_id}: {e}")
        logger.debug(traceback.format_exc())
        
        completed_at = datetime.utcnow()
        response_time = (completed_at - started_at).total_seconds()
        
        failure_result = TaskResult(
            execution_id=execution_id,
            test_case_id=test_case_id,
            sequence_num=context_dict.get('sequence_num', 0),
            iteration_num=context_dict.get('iteration_num', 1),
            success=False,
            error_message=str(e),
            response_time=response_time,
            started_at=started_at,
            completed_at=completed_at
        )
        
        return {
            'execution_id': failure_result.execution_id,
            'test_case_id': failure_result.test_case_id,
            'sequence_num': failure_result.sequence_num,
            'iteration_num': failure_result.iteration_num,
            'status_code': failure_result.status_code,
            'response_body': failure_result.response_body,
            'response_headers': failure_result.response_headers,
            'response_time': failure_result.response_time,
            'success': failure_result.success,
            'error_message': failure_result.error_message,
            'started_at': failure_result.started_at.isoformat(),
            'completed_at': failure_result.completed_at.isoformat(),
            'retry_count': failure_result.retry_count
        }


@celery.task(bind=True, base=ExecutionTask, name='execution.execute_batch')
def execute_batch(self, batch_contexts: list, endpoint_dict: Dict[str, Any], 
                 test_cases: list) -> Dict[str, Any]:
    """
    Execute a batch of requests concurrently
    
    Args:
        batch_contexts: List of ExecutionContext dictionaries
        endpoint_dict: Endpoint configuration
        test_cases: List of test case dictionaries
        
    Returns:
        List of TaskResult dictionaries
    """
    batch_id = batch_contexts[0].get('batch_id', 'unknown') if batch_contexts else 'unknown'
    started_at = datetime.utcnow()
    
    logger.info(f"Executing batch {batch_id} with {len(batch_contexts)} requests")
    
    try:
        # Execute requests in parallel using Celery group
        from celery import group
        
        # Create individual request tasks
        job = group(
            execute_single_request.s(context, endpoint_dict, test_case)
            for context, test_case in zip(batch_contexts, test_cases)
        )
        
        # Execute batch
        result = job.apply_async()
        batch_results = result.get()  # Wait for all to complete
        
        completed_at = datetime.utcnow()
        total_time = (completed_at - started_at).total_seconds()
        
        logger.info(f"Batch {batch_id} completed in {total_time:.2f}s with {len(batch_results)} results")
        
        return {
            'batch_id': batch_id,
            'results': batch_results,
            'started_at': started_at.isoformat(),
            'completed_at': completed_at.isoformat(),
            'total_time': total_time
        }
        
    except Exception as e:
        logger.error(f"Batch execution failed for batch {batch_id}: {e}")
        logger.debug(traceback.format_exc())
        
        completed_at = datetime.utcnow()
        total_time = (completed_at - started_at).total_seconds()
        
        return {
            'batch_id': batch_id,
            'results': [],
            'error': str(e),
            'started_at': started_at.isoformat(),
            'completed_at': completed_at.isoformat(),
            'total_time': total_time
        }


# Task signature helpers for the execution strategies
def create_request_task_signature(context: ExecutionContext, endpoint, test_case):
    """Create a Celery signature for a single request task"""
    context_dict = {
        'execution_id': context.execution_id,
        'test_run_id': context.test_run_id,
        'test_case_id': context.test_case_id,
        'sequence_num': context.sequence_num,
        'iteration_num': context.iteration_num,
        'delay': context.delay,
        'timeout': context.timeout,
        'retry_count': context.retry_count,
        'max_retries': context.max_retries,
        'request_config': context.request_config,
        'batch_id': context.batch_id,
        'strategy_name': context.strategy_name
    }
    
    endpoint_dict = {
        'id': getattr(endpoint, 'id', 0),
        'url': getattr(endpoint, 'url', ''),
        'method': getattr(endpoint, 'method', 'GET'),
        'headers': getattr(endpoint, 'headers', {}),
        'timeout': getattr(endpoint, 'timeout', 30)
    }
    
    test_case_dict = {
        'id': getattr(test_case, 'id', 0),
        'payload': getattr(test_case, 'payload', {}),
        'headers': getattr(test_case, 'headers', {}),
        'expected_status': getattr(test_case, 'expected_status', 200)
    }
    
    return execute_single_request.s(context_dict, endpoint_dict, test_case_dict)


def create_chain_task_signature(context: ExecutionContext, chain, test_case):
    """Create a Celery signature for a chain execution task"""
    context_dict = {
        'execution_id': context.execution_id,
        'test_run_id': context.test_run_id,
        'test_case_id': context.test_case_id,
        'sequence_num': context.sequence_num,
        'iteration_num': context.iteration_num,
        'delay': context.delay,
        'timeout': context.timeout,
        'batch_id': context.batch_id,
        'strategy_name': context.strategy_name
    }
    
    chain_dict = {
        'id': getattr(chain, 'id', 0),
        'steps': getattr(chain, 'steps', []),
        'step_delay': getattr(chain, 'step_delay', 0.3),
        'allow_parallel_instances': getattr(chain, 'allow_parallel_instances', False),
        'max_parallel_instances': getattr(chain, 'max_parallel_instances', 1)
    }
    
    test_case_dict = {
        'id': getattr(test_case, 'id', 0),
        'payload': getattr(test_case, 'payload', {}),
        'headers': getattr(test_case, 'headers', {})
    }
    
    return execute_chain_instance.s(context_dict, chain_dict, test_case_dict)


def dict_to_task_result(result_dict: Dict[str, Any]) -> TaskResult:
    """Convert task result dictionary back to TaskResult object"""
    return TaskResult(
        execution_id=result_dict['execution_id'],
        test_case_id=result_dict['test_case_id'],
        sequence_num=result_dict['sequence_num'],
        iteration_num=result_dict['iteration_num'],
        status_code=result_dict.get('status_code'),
        response_body=result_dict.get('response_body', ''),
        response_headers=result_dict.get('response_headers', {}),
        response_time=result_dict.get('response_time', 0.0),
        success=result_dict.get('success', False),
        error_message=result_dict.get('error_message'),
        retry_count=result_dict.get('retry_count', 0),
        started_at=datetime.fromisoformat(result_dict['started_at']) if result_dict.get('started_at') else datetime.utcnow(),
        completed_at=datetime.fromisoformat(result_dict['completed_at']) if result_dict.get('completed_at') else datetime.utcnow()
    )