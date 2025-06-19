# services/execution/strategies.py
"""
Execution strategies for different types of test execution patterns
"""

import logging
import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Optional, Iterator
from datetime import datetime

from .models import (
    ExecutionContext, TaskResult, BatchResult, ExecutionState, RateAdjustment
)
from .config import AdaptiveConfig

logger = logging.getLogger(__name__)


class ExecutionStrategy(ABC):
    """
    Abstract base class for execution strategies
    
    Each strategy implements a different approach to executing test cases
    against targets (endpoints or chains) with specific performance and
    reliability characteristics.
    """
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.is_paused = False
        self.is_cancelled = False
        self.controller = None
    
    @abstractmethod
    def can_handle(self, target_type: str, target, execution_config: Dict[str, Any]) -> bool:
        """
        Determine if this strategy can handle the given target and configuration
        
        Args:
            target_type: 'endpoint' or 'chain'
            target: The actual endpoint or chain object
            execution_config: Configuration dictionary
            
        Returns:
            True if this strategy can handle the execution
        """
        pass
    
    @abstractmethod
    def execute(self, test_cases: List, target: Union[Any, Any]) -> Iterator[BatchResult]:
        """
        Execute test cases against the target
        
        Args:
            test_cases: List of test cases to execute
            target: Target endpoint or chain
            
        Yields:
            BatchResult objects as batches complete
        """
        pass
    
    def execute_with_monitoring(self, test_cases: List, target: Union[Any, Any], controller) -> Iterator[BatchResult]:
        """
        Execute with monitoring integration
        
        This method wraps the main execute method to provide controller integration,
        pause/resume functionality, and monitoring hooks.
        """
        self.controller = controller
        
        try:
            logger.info(f"Starting {self.name} execution for {len(test_cases)} test cases")
            
            for batch_result in self.execute(test_cases, target):
                # Check for pause/cancel requests
                if self.is_cancelled:
                    logger.info(f"{self.name} execution cancelled")
                    break
                
                while self.is_paused:
                    time.sleep(0.1)  # Wait while paused
                    if self.is_cancelled:
                        break
                
                if self.is_cancelled:
                    break
                
                # Report batch result to controller
                if self.controller:
                    self.controller.record_batch_result(batch_result)
                
                yield batch_result
            
            if not self.is_cancelled:
                logger.info(f"{self.name} execution completed successfully")
                
        except Exception as e:
            logger.error(f"{self.name} execution failed: {e}")
            if self.controller:
                self.controller.complete_execution(ExecutionState.FAILED)
            raise
        finally:
            if self.controller and not self.is_cancelled:
                self.controller.complete_execution(ExecutionState.COMPLETED)
    
    def pause(self):
        """Pause execution after current batch completes"""
        self.is_paused = True
        logger.info(f"{self.name} strategy paused")
    
    def resume(self):
        """Resume paused execution"""
        self.is_paused = False
        logger.info(f"{self.name} strategy resumed")
    
    def cancel(self):
        """Cancel execution immediately"""
        self.is_cancelled = True
        logger.info(f"{self.name} strategy cancelled")
    
    def on_rate_adjustment(self, adjustment: RateAdjustment, new_config: Dict[str, Any]):
        """Handle rate adjustment notifications from controller"""
        logger.info(f"{self.name} strategy received rate adjustment: {adjustment.value}")
        # Base implementation does nothing, subclasses can override
    
    def _create_execution_context(self, test_case, sequence_num: int = 0, iteration_num: int = 1) -> ExecutionContext:
        """Create execution context for a test case"""
        return ExecutionContext(
            test_run_id=self.controller.test_run.id if self.controller else 0,
            test_case_id=test_case.id if hasattr(test_case, 'id') else 0,
            sequence_num=sequence_num,
            iteration_num=iteration_num,
            delay=self.controller.config.current_delay if self.controller else 0.0,
            strategy_name=self.name
        )
    
    def _create_batch_result(self, batch_id: str, test_cases: List) -> BatchResult:
        """Create a new batch result for tracking"""
        batch_result = BatchResult(
            batch_id=batch_id,
            batch_size=len(test_cases),
            started_at=datetime.utcnow()
        )
        
        # Register with controller for tracking
        if self.controller:
            self.controller.start_batch(batch_id, len(test_cases))
        
        return batch_result
    
    def _apply_delay(self, delay: float):
        """Apply delay with cancellation check"""
        if delay <= 0:
            return
        
        start_time = time.time()
        while time.time() - start_time < delay:
            if self.is_cancelled:
                break
            time.sleep(min(0.1, delay - (time.time() - start_time)))


class BurstExecutionStrategy(ExecutionStrategy):
    """
    High-throughput execution strategy for robust endpoints
    
    Characteristics:
    - Maximum concurrency and minimal delays
    - Aggressive batching
    - Optimized for high-capacity endpoints
    - Fast failure detection with immediate backoff
    """
    
    def __init__(self):
        super().__init__(
            name="Burst",
            description="Maximum throughput execution for high-capacity endpoints"
        )
    
    def can_handle(self, target_type: str, target, execution_config: Dict[str, Any]) -> bool:
        """Can handle endpoints marked as high-capacity or burst-capable"""
        if target_type != 'endpoint':
            return False
        
        # Check if endpoint supports burst traffic
        if hasattr(target, 'supports_burst_traffic') and target.supports_burst_traffic:
            return True
        
        # Check execution config preferences
        preferred_strategy = execution_config.get('preferred_strategy', '')
        return preferred_strategy.lower() in ['burst', 'high_throughput', 'aggressive']
    
    def execute(self, test_cases: List, target) -> Iterator[BatchResult]:
        """Execute with maximum throughput"""
        config = self.controller.config if self.controller else AdaptiveConfig()
        
        # Use larger batch sizes for burst execution
        batch_size = max(config.current_batch_size, 8)
        
        # Create batches
        batches = self._create_batches(test_cases, batch_size)
        
        for batch_index, batch in enumerate(batches):
            if self.is_cancelled:
                break
            
            batch_id = f"burst_batch_{batch_index}_{int(time.time())}"
            batch_result = self._create_batch_result(batch_id, batch)
            
            logger.info(f"Executing burst batch {batch_index + 1}/{len(batches)} with {len(batch)} cases")
            
            # Execute batch with high concurrency
            batch_results = self._execute_burst_batch(batch, target, batch_id)
            batch_result.results.extend(batch_results)
            batch_result.completed_at = datetime.utcnow()
            batch_result.calculate_metrics()
            
            # Apply minimal delay between batches
            if config.current_delay > 0 and not self.is_cancelled:
                # Use reduced delay for burst mode
                burst_delay = min(config.current_delay, 0.5)
                self._apply_delay(burst_delay)
            
            yield batch_result
    
    def _create_batches(self, test_cases: List, batch_size: int) -> List[List]:
        """Create optimized batches for burst execution"""
        return [test_cases[i:i + batch_size] for i in range(0, len(test_cases), batch_size)]
    
    def _execute_burst_batch(self, test_cases: List, target, batch_id: str) -> List[TaskResult]:
        """Execute a batch with maximum concurrency"""
        # This is a simplified implementation
        # In the actual implementation, this would use Celery tasks or async execution
        
        results = []
        for i, test_case in enumerate(test_cases):
            if self.is_cancelled:
                break
            
            # Create execution context
            context = self._create_execution_context(test_case, sequence_num=i)
            context.batch_id = batch_id
            
            # Simulate task execution (replace with actual task execution)
            result = self._simulate_task_execution(test_case, target, context)
            results.append(result)
            
            # Report to controller immediately
            if self.controller:
                self.controller.record_task_result(result)
        
        return results
    
    def _simulate_task_execution(self, test_case, target, context: ExecutionContext) -> TaskResult:
        """Simulate task execution (placeholder for actual implementation)"""
        start_time = datetime.utcnow()
        
        # This would be replaced with actual HTTP request execution
        # For now, simulate a successful response
        response_time = 0.5  # Simulated response time
        
        return TaskResult(
            execution_id=context.execution_id,
            test_case_id=context.test_case_id,
            sequence_num=context.sequence_num,
            iteration_num=context.iteration_num,
            status_code=200,
            response_body="Simulated response",
            response_time=response_time,
            success=True,
            started_at=start_time,
            completed_at=datetime.utcnow()
        )


class ConservativeExecutionStrategy(ExecutionStrategy):
    """
    Gentle execution strategy for fragile or rate-limited endpoints
    
    Characteristics:
    - Low concurrency with generous delays
    - Small batch sizes
    - Aggressive error detection and backoff
    - Optimized for fragile endpoints
    """
    
    def __init__(self):
        super().__init__(
            name="Conservative",
            description="Gentle execution for fragile or rate-limited endpoints"
        )
    
    def can_handle(self, target_type: str, target, execution_config: Dict[str, Any]) -> bool:
        """Can handle any target type, preferred for fragile endpoints"""
        if target_type == 'chain':
            return True  # Always suitable for chains
        
        # Check if endpoint is marked as fragile
        if hasattr(target, 'supports_burst_traffic') and not target.supports_burst_traffic:
            return True
        
        # Check execution config preferences
        preferred_strategy = execution_config.get('preferred_strategy', '')
        return preferred_strategy.lower() in ['conservative', 'gentle', 'fragile', 'safe']
    
    def execute(self, test_cases: List, target) -> Iterator[BatchResult]:
        """Execute with conservative approach"""
        config = self.controller.config if self.controller else AdaptiveConfig()
        
        # Use smaller batch sizes for conservative execution
        batch_size = min(config.current_batch_size, 3)
        
        # Create smaller batches
        batches = self._create_batches(test_cases, batch_size)
        
        for batch_index, batch in enumerate(batches):
            if self.is_cancelled:
                break
            
            batch_id = f"conservative_batch_{batch_index}_{int(time.time())}"
            batch_result = self._create_batch_result(batch_id, batch)
            
            logger.info(f"Executing conservative batch {batch_index + 1}/{len(batches)} with {len(batch)} cases")
            
            # Execute batch with low concurrency
            batch_results = self._execute_conservative_batch(batch, target, batch_id)
            batch_result.results.extend(batch_results)
            batch_result.completed_at = datetime.utcnow()
            batch_result.calculate_metrics()
            
            # Apply generous delay between batches
            if not self.is_cancelled:
                # Use extended delay for conservative mode
                conservative_delay = max(config.current_delay, 1.0)
                self._apply_delay(conservative_delay)
            
            yield batch_result
    
    def _create_batches(self, test_cases: List, batch_size: int) -> List[List]:
        """Create smaller batches for conservative execution"""
        return [test_cases[i:i + batch_size] for i in range(0, len(test_cases), batch_size)]
    
    def _execute_conservative_batch(self, test_cases: List, target, batch_id: str) -> List[TaskResult]:
        """Execute a batch with low concurrency and generous delays"""
        results = []
        
        for i, test_case in enumerate(test_cases):
            if self.is_cancelled:
                break
            
            # Create execution context
            context = self._create_execution_context(test_case, sequence_num=i)
            context.batch_id = batch_id
            
            # Apply delay before each request in conservative mode
            if i > 0 and self.controller:
                request_delay = max(self.controller.config.current_delay, 0.5)
                self._apply_delay(request_delay)
            
            # Simulate task execution
            result = self._simulate_task_execution(test_case, target, context)
            results.append(result)
            
            # Report to controller immediately
            if self.controller:
                self.controller.record_task_result(result)
        
        return results
    
    def _simulate_task_execution(self, test_case, target, context: ExecutionContext) -> TaskResult:
        """Simulate conservative task execution"""
        start_time = datetime.utcnow()
        
        # Simulate slightly longer response time for conservative execution
        response_time = 1.0  # Simulated response time
        
        return TaskResult(
            execution_id=context.execution_id,
            test_case_id=context.test_case_id,
            sequence_num=context.sequence_num,
            iteration_num=context.iteration_num,
            status_code=200,
            response_body="Simulated conservative response",
            response_time=response_time,
            success=True,
            started_at=start_time,
            completed_at=datetime.utcnow()
        )


class AdaptiveExecutionStrategy(ExecutionStrategy):
    """
    Smart execution strategy that adapts based on endpoint responses
    
    Characteristics:
    - Starts with moderate settings
    - Learns from endpoint responses
    - Automatically adjusts rate and concurrency
    - Balances throughput with reliability
    """
    
    def __init__(self):
        super().__init__(
            name="Adaptive",
            description="Smart execution that learns from endpoint responses"
        )
        self.learning_enabled = True
    
    def can_handle(self, target_type: str, target, execution_config: Dict[str, Any]) -> bool:
        """Default strategy, can handle any target type"""
        return True  # Adaptive strategy is the fallback for all cases
    
    def execute(self, test_cases: List, target) -> Iterator[BatchResult]:
        """Execute with adaptive learning"""
        config = self.controller.config if self.controller else AdaptiveConfig()
        
        # Start with moderate batch size
        current_batch_size = config.current_batch_size
        
        # Create initial batches
        batches = self._create_adaptive_batches(test_cases, current_batch_size)
        
        for batch_index, batch in enumerate(batches):
            if self.is_cancelled:
                break
            
            batch_id = f"adaptive_batch_{batch_index}_{int(time.time())}"
            batch_result = self._create_batch_result(batch_id, batch)
            
            logger.info(f"Executing adaptive batch {batch_index + 1}/{len(batches)} with {len(batch)} cases")
            
            # Execute batch with current settings
            batch_results = self._execute_adaptive_batch(batch, target, batch_id)
            batch_result.results.extend(batch_results)
            batch_result.completed_at = datetime.utcnow()
            batch_result.calculate_metrics()
            
            # Learn from batch results
            if self.learning_enabled and self.controller:
                self._learn_from_batch(batch_result)
                
                # Update batch size for next iteration if needed
                new_batch_size = self.controller.config.current_batch_size
                if new_batch_size != current_batch_size:
                    current_batch_size = new_batch_size
                    # Recreate remaining batches with new size
                    remaining_cases = test_cases[(batch_index + 1) * len(batch):]
                    if remaining_cases:
                        new_batches = self._create_adaptive_batches(remaining_cases, current_batch_size)
                        # Update batches list (this is simplified, actual implementation would be more sophisticated)
            
            # Apply adaptive delay
            if not self.is_cancelled and self.controller:
                adaptive_delay = self.controller.config.current_delay
                self._apply_delay(adaptive_delay)
            
            yield batch_result
    
    def _create_adaptive_batches(self, test_cases: List, batch_size: int) -> List[List]:
        """Create batches that can be adjusted during execution"""
        return [test_cases[i:i + batch_size] for i in range(0, len(test_cases), batch_size)]
    
    def _execute_adaptive_batch(self, test_cases: List, target, batch_id: str) -> List[TaskResult]:
        """Execute batch with adaptive monitoring"""
        results = []
        
        for i, test_case in enumerate(test_cases):
            if self.is_cancelled:
                break
            
            # Create execution context
            context = self._create_execution_context(test_case, sequence_num=i)
            context.batch_id = batch_id
            
            # Simulate task execution
            result = self._simulate_task_execution(test_case, target, context)
            results.append(result)
            
            # Report to controller for immediate learning
            if self.controller:
                self.controller.record_task_result(result)
            
            # Adaptive delay based on response
            if i < len(test_cases) - 1:  # Not the last request
                self._apply_adaptive_delay(result)
        
        return results
    
    def _learn_from_batch(self, batch_result: BatchResult):
        """Learn from batch performance and suggest adjustments"""
        if not self.controller:
            return
        
        # The controller's config will automatically adjust based on batch results
        # This method can add strategy-specific learning logic
        
        if batch_result.error_rate > 0.2:
            logger.warning(f"High error rate {batch_result.error_rate:.2%} in adaptive batch, "
                          f"controller should slow down")
        elif batch_result.error_rate < 0.05 and batch_result.avg_response_time < 1.0:
            logger.info(f"Excellent performance in adaptive batch (error rate: {batch_result.error_rate:.2%}, "
                       f"avg time: {batch_result.avg_response_time:.2f}s), controller should consider speedup")
    
    def _apply_adaptive_delay(self, last_result: TaskResult):
        """Apply delay based on last result"""
        if not self.controller:
            return
        
        base_delay = self.controller.config.current_delay
        
        # Adjust delay based on last response
        if last_result.status_code == 429:  # Rate limited
            delay = base_delay * 2  # Double delay immediately
        elif last_result.status_code and last_result.status_code >= 500:  # Server error
            delay = base_delay * 1.5  # Increase delay moderately
        elif last_result.response_time > 3.0:  # Slow response
            delay = base_delay * 1.2  # Slight increase
        else:
            delay = base_delay  # Use configured delay
        
        self._apply_delay(delay)
    
    def _simulate_task_execution(self, test_case, target, context: ExecutionContext) -> TaskResult:
        """Simulate adaptive task execution"""
        start_time = datetime.utcnow()
        
        # Simulate variable response time for adaptive learning
        import random
        response_time = random.uniform(0.3, 2.0)  # Variable response time
        success = random.random() > 0.05  # 95% success rate
        status_code = 200 if success else random.choice([429, 500, 503])
        
        return TaskResult(
            execution_id=context.execution_id,
            test_case_id=context.test_case_id,
            sequence_num=context.sequence_num,
            iteration_num=context.iteration_num,
            status_code=status_code,
            response_body="Simulated adaptive response",
            response_time=response_time,
            success=success,
            started_at=start_time,
            completed_at=datetime.utcnow()
        )


class ChainExecutionStrategy(ExecutionStrategy):
    """
    Specialized execution strategy for API chains
    
    Characteristics:
    - Sequential step execution within each chain
    - Context passing between steps
    - Optional parallel chain instances
    - Proper error handling and chain state management
    """
    
    def __init__(self):
        super().__init__(
            name="Chain",
            description="Specialized execution for API chains with step sequencing"
        )
    
    def can_handle(self, target_type: str, target, execution_config: Dict[str, Any]) -> bool:
        """Handles API chain execution"""
        return target_type == 'chain'
    
    def execute(self, test_cases: List, target) -> Iterator[BatchResult]:
        """Execute chains with proper step sequencing"""
        config = self.controller.config if self.controller else AdaptiveConfig()
        chain = target
        
        # Determine if parallel chain instances are allowed
        allow_parallel = getattr(chain, 'allow_parallel_instances', False)
        max_parallel = getattr(chain, 'max_parallel_instances', 1)
        
        if allow_parallel and max_parallel > 1:
            # Execute multiple chain instances in parallel
            yield from self._execute_parallel_chains(test_cases, chain, max_parallel)
        else:
            # Execute chains sequentially
            yield from self._execute_sequential_chains(test_cases, chain)
    
    def _execute_sequential_chains(self, test_cases: List, chain) -> Iterator[BatchResult]:
        """Execute chain instances one at a time"""
        for batch_index, test_case in enumerate(test_cases):
            if self.is_cancelled:
                break
            
            batch_id = f"chain_sequential_{batch_index}_{int(time.time())}"
            batch_result = self._create_batch_result(batch_id, [test_case])
            
            logger.info(f"Executing sequential chain {batch_index + 1}/{len(test_cases)}")
            
            # Execute single chain instance
            chain_result = self._execute_single_chain(test_case, chain, batch_id, 0)
            batch_result.results.append(chain_result)
            batch_result.completed_at = datetime.utcnow()
            batch_result.calculate_metrics()
            
            # Report to controller
            if self.controller:
                self.controller.record_task_result(chain_result)
            
            # Apply delay between chain instances
            if batch_index < len(test_cases) - 1 and not self.is_cancelled:
                chain_delay = getattr(chain, 'step_delay', 0.5)
                if self.controller:
                    chain_delay = max(chain_delay, self.controller.config.current_delay)
                self._apply_delay(chain_delay)
            
            yield batch_result
    
    def _execute_parallel_chains(self, test_cases: List, chain, max_parallel: int) -> Iterator[BatchResult]:
        """Execute multiple chain instances in parallel"""
        # Create batches for parallel execution
        batch_size = min(max_parallel, len(test_cases))
        batches = [test_cases[i:i + batch_size] for i in range(0, len(test_cases), batch_size)]
        
        for batch_index, batch in enumerate(batches):
            if self.is_cancelled:
                break
            
            batch_id = f"chain_parallel_{batch_index}_{int(time.time())}"
            batch_result = self._create_batch_result(batch_id, batch)
            
            logger.info(f"Executing parallel chain batch {batch_index + 1}/{len(batches)} "
                       f"with {len(batch)} instances")
            
            # Execute chain instances in parallel (simulated)
            batch_results = []
            for i, test_case in enumerate(batch):
                if self.is_cancelled:
                    break
                
                chain_result = self._execute_single_chain(test_case, chain, batch_id, i)
                batch_results.append(chain_result)
                
                # Report individual results
                if self.controller:
                    self.controller.record_task_result(chain_result)
            
            batch_result.results.extend(batch_results)
            batch_result.completed_at = datetime.utcnow()
            batch_result.calculate_metrics()
            
            # Apply delay between parallel batches
            if batch_index < len(batches) - 1 and not self.is_cancelled:
                chain_delay = getattr(chain, 'step_delay', 0.5)
                if self.controller:
                    chain_delay = max(chain_delay, self.controller.config.current_delay)
                self._apply_delay(chain_delay)
            
            yield batch_result
    
    def _execute_single_chain(self, test_case, chain, batch_id: str, sequence_num: int) -> TaskResult:
        """Execute a single chain instance with all steps"""
        context = self._create_execution_context(test_case, sequence_num)
        context.batch_id = batch_id
        
        start_time = datetime.utcnow()
        
        # Simulate chain execution with multiple steps
        # In actual implementation, this would execute each step in sequence
        # with proper context passing between steps
        
        try:
            # Simulate step execution
            steps = getattr(chain, 'steps', [])
            total_response_time = 0.0
            chain_context = {}  # Context passed between steps
            
            for step_index, step in enumerate(steps):
                if self.is_cancelled:
                    break
                
                # Apply step delay
                step_delay = getattr(chain, 'step_delay', 0.3)
                if step_index > 0:
                    self._apply_delay(step_delay)
                
                # Simulate step execution
                step_response_time = 0.8  # Simulated step response time
                total_response_time += step_response_time
                
                # Update chain context (simulated)
                chain_context[f'step_{step_index}_result'] = f"Step {step_index} result"
            
            # Create successful result
            return TaskResult(
                execution_id=context.execution_id,
                test_case_id=context.test_case_id,
                sequence_num=context.sequence_num,
                iteration_num=context.iteration_num,
                status_code=200,
                response_body=f"Chain execution completed with {len(steps)} steps",
                response_time=total_response_time,
                success=True,
                started_at=start_time,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Chain execution failed: {e}")
            return TaskResult(
                execution_id=context.execution_id,
                test_case_id=context.test_case_id,
                sequence_num=context.sequence_num,
                iteration_num=context.iteration_num,
                status_code=500,
                response_body=f"Chain execution error: {str(e)}",
                response_time=0.0,
                success=False,
                error_message=str(e),
                started_at=start_time,
                completed_at=datetime.utcnow()
            )