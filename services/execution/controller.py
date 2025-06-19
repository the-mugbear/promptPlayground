# services/execution/controller.py
"""
Execution Controller for stateful management of test run executions
"""

import logging
import asyncio
from typing import Dict, List, Optional, Union, Any, Callable
from datetime import datetime
from dataclasses import asdict

from .models import (
    ExecutionState, ExecutionContext, ExecutionResult, ExecutionStats,
    TaskResult, BatchResult, RateAdjustment
)
from .config import AdaptiveConfig, ExecutionTemplate
from .monitor import ExecutionMonitor, RealTimeMetrics

logger = logging.getLogger(__name__)


class ExecutionController:
    """
    Stateful controller that manages execution lifecycle, coordination,
    and real-time adjustments for test runs
    """
    
    def __init__(self, test_run, strategy, config: Optional[AdaptiveConfig] = None):
        self.test_run = test_run
        self.strategy = strategy
        self.config = config or AdaptiveConfig.from_test_run(test_run)
        
        # Execution state
        self.state = ExecutionState.PENDING
        self.execution_id = f"exec_{test_run.id}_{int(datetime.utcnow().timestamp())}"
        
        # Progress tracking
        self.total_cases = 0
        self.completed_cases = 0
        self.successful_cases = 0
        self.failed_cases = 0
        
        # Results storage
        self.batch_results: List[BatchResult] = []
        self.current_batch_results: Dict[str, BatchResult] = {}
        
        # Monitoring and metrics
        self.monitor = ExecutionMonitor(self)
        self.metrics = RealTimeMetrics()
        self.stats = ExecutionStats(
            test_run_id=test_run.id,
            current_state=self.state
        )
        
        # Control mechanisms
        self._pause_requested = False
        self._cancel_requested = False
        self._adjustment_callbacks: List[Callable] = []
        
        # Timestamps
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
        logger.info(f"Initialized ExecutionController {self.execution_id} for test run {test_run.id}")
    
    def start(self) -> 'ExecutionController':
        """Start the execution process"""
        if self.state != ExecutionState.PENDING:
            raise ValueError(f"Cannot start execution in state {self.state}")
        
        self.state = ExecutionState.RUNNING
        self.started_at = datetime.utcnow()
        self.stats.started_at = self.started_at
        self.stats.current_state = self.state
        
        logger.info(f"Starting execution {self.execution_id}")
        
        # Initialize monitoring
        self.monitor.start_monitoring()
        
        # Delegate actual execution to the strategy
        try:
            self.strategy.execute_with_monitoring(
                test_cases=self._get_test_cases(),
                target=self._get_target(),
                controller=self
            )
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            self.state = ExecutionState.FAILED
            raise
        
        return self
    
    def pause(self):
        """Request execution pause after current batch completes"""
        if self.state != ExecutionState.RUNNING:
            logger.warning(f"Cannot pause execution in state {self.state}")
            return
        
        logger.info(f"Requesting pause for execution {self.execution_id}")
        self.state = ExecutionState.PAUSING
        self._pause_requested = True
        self.stats.current_state = self.state
        
        # Notify strategy to pause gracefully
        if hasattr(self.strategy, 'pause'):
            self.strategy.pause()
    
    def resume(self):
        """Resume paused execution"""
        if self.state != ExecutionState.PAUSED:
            logger.warning(f"Cannot resume execution in state {self.state}")
            return
        
        logger.info(f"Resuming execution {self.execution_id}")
        self.state = ExecutionState.RUNNING
        self._pause_requested = False
        self.stats.current_state = self.state
        
        # Notify strategy to resume
        if hasattr(self.strategy, 'resume'):
            self.strategy.resume()
    
    def cancel(self):
        """Cancel execution immediately"""
        logger.info(f"Cancelling execution {self.execution_id}")
        self.state = ExecutionState.CANCELLED
        self._cancel_requested = True
        self.completed_at = datetime.utcnow()
        self.stats.current_state = self.state
        
        # Notify strategy to cancel
        if hasattr(self.strategy, 'cancel'):
            self.strategy.cancel()
        
        # Stop monitoring
        self.monitor.stop_monitoring()
    
    def adjust_rate(self, adjustment: Union[RateAdjustment, str], value: Optional[float] = None):
        """Apply rate adjustment to execution"""
        if isinstance(adjustment, str):
            adjustment = RateAdjustment(adjustment)
        
        logger.info(f"Applying rate adjustment {adjustment.value} to execution {self.execution_id}")
        
        # Apply adjustment to configuration
        if adjustment == RateAdjustment.RESET_TO_DEFAULT:
            self.config.apply_adjustment(adjustment)
        elif value is not None:
            # Manual adjustment with specific value
            if adjustment == RateAdjustment.SLOW_DOWN:
                self.config.current_delay = max(value, self.config.min_delay)
            elif adjustment == RateAdjustment.SPEED_UP:
                self.config.current_delay = min(value, self.config.max_delay)
        else:
            # Apply automatic adjustment
            self.config.apply_adjustment(adjustment)
        
        # Update stats
        self.stats.current_delay = self.config.current_delay
        self.stats.current_batch_size = self.config.current_batch_size
        self.stats.current_concurrency = self.config.current_concurrency
        self.stats.last_adjustment = adjustment
        self.stats.last_adjustment_time = datetime.utcnow()
        self.stats.total_adjustments += 1
        
        # Notify callbacks
        for callback in self._adjustment_callbacks:
            try:
                callback(adjustment, self.config.get_current_settings())
            except Exception as e:
                logger.error(f"Error in adjustment callback: {e}")
        
        # Notify strategy of adjustment
        if hasattr(self.strategy, 'on_rate_adjustment'):
            self.strategy.on_rate_adjustment(adjustment, self.config)
    
    def record_task_result(self, task_result: TaskResult):
        """Record result from individual task execution"""
        logger.debug(f"Recording task result for case {task_result.test_case_id}")
        
        # Update progress counters
        self.completed_cases += 1
        if task_result.success:
            self.successful_cases += 1
        else:
            self.failed_cases += 1
        
        # Update batch result if it exists
        if task_result.execution_id in self.current_batch_results:
            batch_result = self.current_batch_results[task_result.execution_id]
            batch_result.results.append(task_result)
            batch_result.calculate_metrics()
        
        # Update real-time metrics
        self.metrics.record_task_result(task_result)
        
        # Update stats
        self._update_stats()
        
        # Check for automatic rate adjustment
        if task_result.needs_rate_adjustment():
            suggested_adjustment = task_result.suggested_adjustment()
            if suggested_adjustment and self.config.auto_adjust:
                self.adjust_rate(suggested_adjustment)
        
        # Notify monitor
        self.monitor.on_task_completed(task_result)
        
        # Check for pause/cancel requests
        if self._pause_requested and self.state == ExecutionState.PAUSING:
            self.state = ExecutionState.PAUSED
            self.stats.current_state = self.state
            logger.info(f"Execution {self.execution_id} paused")
        
        if self._cancel_requested:
            return  # Let cancellation proceed
    
    def record_batch_result(self, batch_result: BatchResult):
        """Record result from batch execution"""
        logger.info(f"Recording batch result {batch_result.batch_id} with {len(batch_result.results)} results")
        
        # Calculate batch metrics
        batch_result.calculate_metrics()
        
        # Store batch result
        self.batch_results.append(batch_result)
        
        # Remove from current tracking
        if batch_result.batch_id in self.current_batch_results:
            del self.current_batch_results[batch_result.batch_id]
        
        # Apply batch-level adaptive adjustments
        if self.config.auto_adjust:
            self.config.adjust_for_batch_result(batch_result)
            
            # Update stats with new config values
            self.stats.current_delay = self.config.current_delay
            self.stats.current_batch_size = self.config.current_batch_size
            self.stats.current_concurrency = self.config.current_concurrency
        
        # Update metrics
        self.metrics.record_batch_result(batch_result)
        
        # Notify monitor
        self.monitor.on_batch_completed(batch_result)
    
    def start_batch(self, batch_id: str, batch_size: int) -> BatchResult:
        """Start tracking a new batch"""
        batch_result = BatchResult(
            batch_id=batch_id,
            batch_size=batch_size,
            started_at=datetime.utcnow()
        )
        
        self.current_batch_results[batch_id] = batch_result
        logger.debug(f"Started tracking batch {batch_id} with size {batch_size}")
        
        return batch_result
    
    def complete_execution(self, final_state: ExecutionState = ExecutionState.COMPLETED):
        """Mark execution as completed"""
        if self.state in [ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED]:
            return  # Already completed
        
        self.state = final_state
        self.completed_at = datetime.utcnow()
        self.stats.current_state = self.state
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        
        # Create final execution result
        result = self._create_execution_result()
        
        logger.info(f"Execution {self.execution_id} completed with state {final_state}")
        logger.info(f"Final stats: {self.successful_cases}/{self.total_cases} successful, "
                   f"{len(self.batch_results)} batches, {self.config.total_adjustments} adjustments")
        
        return result
    
    def get_current_stats(self) -> ExecutionStats:
        """Get current execution statistics"""
        self._update_stats()
        return self.stats
    
    def add_adjustment_callback(self, callback: Callable):
        """Add callback to be notified of rate adjustments"""
        self._adjustment_callbacks.append(callback)
    
    def remove_adjustment_callback(self, callback: Callable):
        """Remove adjustment callback"""
        if callback in self._adjustment_callbacks:
            self._adjustment_callbacks.remove(callback)
    
    def _get_test_cases(self) -> List:
        """Get test cases for this execution"""
        # This will be implemented based on the test run type
        if hasattr(self.test_run, 'test_suite_ids') and self.test_run.test_suite_ids:
            # Load test cases from suites
            from ..models import TestSuite
            test_cases = []
            for suite_id in self.test_run.test_suite_ids:
                suite = TestSuite.query.get(suite_id)
                if suite:
                    test_cases.extend(suite.test_cases)
            self.total_cases = len(test_cases)
            return test_cases
        else:
            # Handle other test case sources
            self.total_cases = 0
            return []
    
    def _get_target(self):
        """Get execution target (endpoint or chain)"""
        if self.test_run.target_type == 'endpoint':
            return self.test_run.endpoint
        elif self.test_run.target_type == 'chain':
            return self.test_run.chain
        else:
            raise ValueError(f"Unknown target type: {self.test_run.target_type}")
    
    def _update_stats(self):
        """Update real-time statistics"""
        self.stats.total_cases = self.total_cases
        self.stats.completed_cases = self.completed_cases
        self.stats.successful_cases = self.successful_cases
        self.stats.failed_cases = self.failed_cases
        
        # Calculate progress percentage
        self.stats.update_progress()
        
        # Update metrics from real-time tracker
        self.stats.current_rate = self.metrics.get_current_rate()
        self.stats.avg_response_time = self.metrics.get_avg_response_time()
        self.stats.error_rate = self.metrics.get_error_rate()
        
        # Update adaptive settings
        self.stats.current_delay = self.config.current_delay
        self.stats.current_batch_size = self.config.current_batch_size
        self.stats.current_concurrency = self.config.current_concurrency
        
        self.stats.last_updated = datetime.utcnow()
    
    def _create_execution_result(self) -> ExecutionResult:
        """Create final execution result"""
        duration = 0.0
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()
        
        result = ExecutionResult(
            test_run_id=self.test_run.id,
            strategy_name=self.strategy.__class__.__name__,
            state=self.state,
            total_cases=self.total_cases,
            completed_cases=self.completed_cases,
            successful_cases=self.successful_cases,
            failed_cases=self.failed_cases,
            total_duration=duration,
            initial_delay=self.config.initial_delay,
            final_delay=self.config.current_delay,
            initial_batch_size=self.config.initial_batch_size,
            final_batch_size=self.config.current_batch_size,
            adjustments_made=self.config.total_adjustments,
            batch_results=self.batch_results,
            started_at=self.started_at,
            completed_at=self.completed_at
        )
        
        # Calculate summary metrics
        result.calculate_summary_metrics()
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert controller state to dictionary for serialization"""
        return {
            'execution_id': self.execution_id,
            'test_run_id': self.test_run.id,
            'state': self.state.value,
            'total_cases': self.total_cases,
            'completed_cases': self.completed_cases,
            'successful_cases': self.successful_cases,
            'failed_cases': self.failed_cases,
            'config': self.config.to_dict(),
            'stats': asdict(self.stats),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }