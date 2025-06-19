# services/execution/monitor.py
"""
Real-time execution monitoring and metrics collection
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field

from .models import TaskResult, BatchResult, RateAdjustment

logger = logging.getLogger(__name__)


@dataclass
class MetricWindow:
    """Time-based window for metric calculations"""
    size_seconds: int = 60  # 1 minute window
    values: deque = field(default_factory=deque)
    timestamps: deque = field(default_factory=deque)
    
    def add_value(self, value: float, timestamp: Optional[datetime] = None):
        """Add a new value to the window"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        self.values.append(value)
        self.timestamps.append(timestamp)
        
        # Remove old values outside the window
        cutoff = timestamp - timedelta(seconds=self.size_seconds)
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
            self.values.popleft()
    
    def get_average(self) -> float:
        """Get average value in the current window"""
        return sum(self.values) / len(self.values) if self.values else 0.0
    
    def get_count(self) -> int:
        """Get count of values in the current window"""
        return len(self.values)
    
    def get_rate_per_second(self) -> float:
        """Get rate per second for the current window"""
        if not self.timestamps or len(self.timestamps) < 2:
            return 0.0
        
        duration = (self.timestamps[-1] - self.timestamps[0]).total_seconds()
        return len(self.values) / duration if duration > 0 else 0.0


class RealTimeMetrics:
    """Collects and provides real-time execution metrics"""
    
    def __init__(self, window_size_seconds: int = 60):
        self.window_size = window_size_seconds
        
        # Metric windows
        self.response_times = MetricWindow(window_size_seconds)
        self.success_window = MetricWindow(window_size_seconds)
        self.error_window = MetricWindow(window_size_seconds)
        self.request_window = MetricWindow(window_size_seconds)
        
        # Counters
        self.total_requests = 0
        self.total_successes = 0
        self.total_errors = 0
        self.total_response_time = 0.0
        
        # Rate tracking
        self.last_rate_calculation = datetime.utcnow()
        self.requests_since_last_calc = 0
        
        # Thread safety
        self._lock = threading.Lock()
    
    def record_task_result(self, task_result: TaskResult):
        """Record metrics from a task result"""
        with self._lock:
            timestamp = task_result.completed_at
            
            # Record request
            self.request_window.add_value(1.0, timestamp)
            self.total_requests += 1
            self.requests_since_last_calc += 1
            
            # Record response time
            if task_result.response_time > 0:
                self.response_times.add_value(task_result.response_time, timestamp)
                self.total_response_time += task_result.response_time
            
            # Record success/error
            if task_result.success:
                self.success_window.add_value(1.0, timestamp)
                self.total_successes += 1
            else:
                self.error_window.add_value(1.0, timestamp)
                self.total_errors += 1
    
    def record_batch_result(self, batch_result: BatchResult):
        """Record metrics from a batch result"""
        # Batch-level metrics are calculated from individual task results
        # This method can be used for batch-specific logging or notifications
        logger.debug(f"Batch {batch_result.batch_id} completed: "
                    f"{batch_result.success_count}/{len(batch_result.results)} successful, "
                    f"avg response time: {batch_result.avg_response_time:.2f}s")
    
    def get_current_rate(self) -> float:
        """Get current requests per second"""
        with self._lock:
            return self.request_window.get_rate_per_second()
    
    def get_avg_response_time(self) -> float:
        """Get average response time in current window"""
        with self._lock:
            return self.response_times.get_average()
    
    def get_error_rate(self) -> float:
        """Get current error rate (0.0 to 1.0)"""
        with self._lock:
            total_in_window = self.success_window.get_count() + self.error_window.get_count()
            if total_in_window == 0:
                return 0.0
            return self.error_window.get_count() / total_in_window
    
    def get_success_rate(self) -> float:
        """Get current success rate (0.0 to 1.0)"""
        return 1.0 - self.get_error_rate()
    
    def get_lifetime_metrics(self) -> Dict[str, Any]:
        """Get lifetime execution metrics"""
        with self._lock:
            avg_response_time = (self.total_response_time / self.total_requests 
                               if self.total_requests > 0 else 0.0)
            error_rate = (self.total_errors / self.total_requests 
                         if self.total_requests > 0 else 0.0)
            
            return {
                'total_requests': self.total_requests,
                'total_successes': self.total_successes,
                'total_errors': self.total_errors,
                'avg_response_time': avg_response_time,
                'error_rate': error_rate,
                'success_rate': 1.0 - error_rate
            }
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current window metrics"""
        with self._lock:
            return {
                'current_rate': self.get_current_rate(),
                'avg_response_time': self.get_avg_response_time(),
                'error_rate': self.get_error_rate(),
                'success_rate': self.get_success_rate(),
                'requests_in_window': self.request_window.get_count(),
                'window_size_seconds': self.window_size
            }
    
    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self.response_times = MetricWindow(self.window_size)
            self.success_window = MetricWindow(self.window_size)
            self.error_window = MetricWindow(self.window_size)
            self.request_window = MetricWindow(self.window_size)
            
            self.total_requests = 0
            self.total_successes = 0
            self.total_errors = 0
            self.total_response_time = 0.0
            self.requests_since_last_calc = 0


class ExecutionMonitor:
    """Monitors execution progress and provides real-time feedback"""
    
    def __init__(self, controller):
        self.controller = controller
        self.metrics = RealTimeMetrics()
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Callbacks
        self.progress_callbacks: List[Callable] = []
        self.adjustment_callbacks: List[Callable] = []
        
        # Monitoring intervals
        self.update_interval = 5.0  # seconds
        self.adjustment_check_interval = 10.0  # seconds
        
        # Adjustment tracking
        self.last_adjustment_check = datetime.utcnow()
        self.consecutive_good_batches = 0
        self.consecutive_bad_batches = 0
    
    def start_monitoring(self):
        """Start real-time monitoring"""
        if self.is_monitoring:
            return
        
        logger.info(f"Starting execution monitoring for {self.controller.execution_id}")
        self.is_monitoring = True
        self.stop_event.clear()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name=f"ExecutionMonitor-{self.controller.execution_id}",
            daemon=True
        )
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        if not self.is_monitoring:
            return
        
        logger.info(f"Stopping execution monitoring for {self.controller.execution_id}")
        self.is_monitoring = False
        self.stop_event.set()
        
        # Wait for monitor thread to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
    
    def on_task_completed(self, task_result: TaskResult):
        """Handle task completion"""
        self.metrics.record_task_result(task_result)
        
        # Check for immediate adjustments needed
        if task_result.needs_rate_adjustment():
            self._handle_immediate_adjustment(task_result)
        
        # Notify progress callbacks
        self._notify_progress_callbacks()
    
    def on_batch_completed(self, batch_result: BatchResult):
        """Handle batch completion"""
        self.metrics.record_batch_result(batch_result)
        
        # Analyze batch performance for adjustments
        self._analyze_batch_performance(batch_result)
        
        # Update consecutive batch tracking
        if batch_result.error_rate > 0.1:  # More than 10% errors
            self.consecutive_bad_batches += 1
            self.consecutive_good_batches = 0
        else:
            self.consecutive_good_batches += 1
            self.consecutive_bad_batches = 0
        
        # Notify progress callbacks
        self._notify_progress_callbacks()
    
    def add_progress_callback(self, callback: Callable):
        """Add callback for progress updates"""
        self.progress_callbacks.append(callback)
    
    def add_adjustment_callback(self, callback: Callable):
        """Add callback for adjustment notifications"""
        self.adjustment_callbacks.append(callback)
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get current real-time statistics"""
        controller_stats = self.controller.get_current_stats()
        current_metrics = self.metrics.get_current_metrics()
        lifetime_metrics = self.metrics.get_lifetime_metrics()
        
        return {
            'execution_id': self.controller.execution_id,
            'state': controller_stats.current_state.value,
            'progress': {
                'total_cases': controller_stats.total_cases,
                'completed_cases': controller_stats.completed_cases,
                'successful_cases': controller_stats.successful_cases,
                'failed_cases': controller_stats.failed_cases,
                'progress_percentage': controller_stats.progress_percentage
            },
            'current_metrics': current_metrics,
            'lifetime_metrics': lifetime_metrics,
            'adaptive_settings': {
                'current_delay': controller_stats.current_delay,
                'current_batch_size': controller_stats.current_batch_size,
                'current_concurrency': controller_stats.current_concurrency,
                'total_adjustments': controller_stats.total_adjustments,
                'last_adjustment': controller_stats.last_adjustment.value if controller_stats.last_adjustment else None
            },
            'health': self._calculate_execution_health()
        }
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while not self.stop_event.wait(self.update_interval):
            try:
                # Update metrics and check for adjustments
                self._periodic_adjustment_check()
                
                # Notify progress callbacks
                self._notify_progress_callbacks()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    def _handle_immediate_adjustment(self, task_result: TaskResult):
        """Handle immediate rate adjustments for critical responses"""
        suggested = task_result.suggested_adjustment()
        if suggested:
            logger.warning(f"Immediate adjustment needed: {suggested.value} "
                          f"(status: {task_result.status_code}, time: {task_result.response_time:.2f}s)")
            
            # Apply conservative immediate adjustments
            if suggested == RateAdjustment.SLOW_DOWN:
                self.controller.adjust_rate(suggested)
            elif suggested == RateAdjustment.REDUCE_CONCURRENCY:
                self.controller.adjust_rate(suggested)
    
    def _analyze_batch_performance(self, batch_result: BatchResult):
        """Analyze batch performance for potential adjustments"""
        # High error rate
        if batch_result.error_rate > 0.15:
            logger.warning(f"High error rate in batch {batch_result.batch_id}: {batch_result.error_rate:.2%}")
            
        # Very slow responses
        if batch_result.avg_response_time > 5.0:
            logger.warning(f"Slow responses in batch {batch_result.batch_id}: {batch_result.avg_response_time:.2f}s avg")
        
        # Very fast responses (potential for speedup)
        if batch_result.error_rate < 0.02 and batch_result.avg_response_time < 0.5:
            logger.info(f"Excellent performance in batch {batch_result.batch_id}, consider speedup")
    
    def _periodic_adjustment_check(self):
        """Periodic check for automatic adjustments"""
        now = datetime.utcnow()
        if (now - self.last_adjustment_check).total_seconds() < self.adjustment_check_interval:
            return
        
        self.last_adjustment_check = now
        current_metrics = self.metrics.get_current_metrics()
        
        # Check for patterns requiring adjustment
        if self.consecutive_bad_batches >= 2:
            logger.info("Multiple consecutive bad batches detected, applying slowdown")
            self.controller.adjust_rate(RateAdjustment.SLOW_DOWN)
            self.consecutive_bad_batches = 0
            
        elif self.consecutive_good_batches >= 5:
            logger.info("Multiple consecutive good batches detected, considering speedup")
            if current_metrics['avg_response_time'] < 1.0:
                self.controller.adjust_rate(RateAdjustment.SPEED_UP)
            self.consecutive_good_batches = 0
    
    def _calculate_execution_health(self) -> str:
        """Calculate overall execution health status"""
        current_metrics = self.metrics.get_current_metrics()
        
        error_rate = current_metrics['error_rate']
        avg_response_time = current_metrics['avg_response_time']
        
        if error_rate > 0.2:
            return "critical"
        elif error_rate > 0.1 or avg_response_time > 5.0:
            return "warning"
        elif error_rate < 0.05 and avg_response_time < 2.0:
            return "excellent"
        else:
            return "good"
    
    def _notify_progress_callbacks(self):
        """Notify all progress callbacks with current stats"""
        if not self.progress_callbacks:
            return
        
        try:
            stats = self.get_real_time_stats()
            for callback in self.progress_callbacks:
                try:
                    callback(stats)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
        except Exception as e:
            logger.error(f"Error creating stats for progress callbacks: {e}")