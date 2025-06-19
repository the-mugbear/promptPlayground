# services/execution/config.py
"""
Adaptive configuration and execution templates
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
import json
import logging
from .models import RateAdjustment

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution mode presets"""
    BURST = "burst"
    CONSERVATIVE = "conservative"
    ADAPTIVE = "adaptive"
    CHAIN_SEQUENTIAL = "chain_sequential"
    CHAIN_PARALLEL = "chain_parallel"
    LOAD_TEST = "load_test"
    DEVELOPMENT = "development"
    PRODUCTION = "production"


@dataclass
class AdaptiveConfig:
    """Dynamic configuration that adapts based on execution feedback"""
    
    # Core settings
    initial_delay: float = 0.5
    initial_batch_size: int = 4
    initial_concurrency: int = 2
    
    # Current adaptive values
    current_delay: float = 0.5
    current_batch_size: int = 4
    current_concurrency: int = 2
    
    # Adaptation parameters
    error_threshold: float = 0.1  # 10% error rate triggers adjustment
    response_time_threshold: float = 2.0  # 2 second response time threshold
    adjustment_sensitivity: float = 1.0  # How aggressively to adjust
    
    # Limits
    min_delay: float = 0.0
    max_delay: float = 10.0
    min_batch_size: int = 1
    max_batch_size: int = 20
    min_concurrency: int = 1
    max_concurrency: int = 50
    
    # Learning parameters
    success_threshold_for_speedup: int = 10  # Consecutive successes before speeding up
    consecutive_successes: int = 0
    consecutive_errors: int = 0
    total_adjustments: int = 0
    
    # Backoff/speedup multipliers
    slowdown_multiplier: float = 1.5
    speedup_multiplier: float = 0.9
    backoff_multiplier: float = 2.0
    
    def __post_init__(self):
        """Initialize current values from initial values"""
        self.current_delay = self.initial_delay
        self.current_batch_size = self.initial_batch_size
        self.current_concurrency = self.initial_concurrency
    
    @classmethod
    def from_test_run(cls, test_run) -> 'AdaptiveConfig':
        """Create config from TestRun settings"""
        config = cls()
        
        # Apply test run specific settings
        if hasattr(test_run, 'delay_between_requests'):
            config.initial_delay = test_run.delay_between_requests
            config.current_delay = test_run.delay_between_requests
        
        # Apply execution mode if specified
        execution_mode = getattr(test_run, 'execution_mode', None)
        if execution_mode:
            template = ExecutionTemplate.get_template(execution_mode)
            if template:
                config.apply_template(template)
        
        return config
    
    @classmethod
    def from_endpoint(cls, endpoint) -> 'AdaptiveConfig':
        """Create config based on endpoint capabilities"""
        config = cls()
        
        # Use endpoint-specific settings if available
        if hasattr(endpoint, 'max_concurrent_requests'):
            config.initial_concurrency = min(endpoint.max_concurrent_requests, config.max_concurrency)
            config.current_concurrency = config.initial_concurrency
        
        if hasattr(endpoint, 'recommended_delay'):
            config.initial_delay = endpoint.recommended_delay
            config.current_delay = endpoint.recommended_delay
        
        if hasattr(endpoint, 'rate_limit_per_minute'):
            # Calculate delay based on rate limit
            if endpoint.rate_limit_per_minute > 0:
                min_delay_from_rate_limit = 60.0 / endpoint.rate_limit_per_minute
                config.min_delay = max(config.min_delay, min_delay_from_rate_limit)
                config.current_delay = max(config.current_delay, min_delay_from_rate_limit)
        
        return config
    
    def apply_template(self, template: 'ExecutionTemplate'):
        """Apply execution template settings"""
        self.initial_delay = template.delay
        self.initial_batch_size = template.batch_size
        self.initial_concurrency = template.concurrency
        
        self.current_delay = template.delay
        self.current_batch_size = template.batch_size  
        self.current_concurrency = template.concurrency
        
        self.error_threshold = template.error_threshold
        self.adjustment_sensitivity = template.adjustment_sensitivity
    
    def adjust_for_response(self, status_code: int, response_time: float, error_message: Optional[str] = None):
        """Adjust configuration based on individual response"""
        
        # Handle rate limiting
        if status_code == 429:
            self._apply_rate_limit_adjustment()
            return
        
        # Handle server errors
        if status_code and status_code >= 500:
            self._apply_server_error_adjustment()
            return
        
        # Handle slow responses
        if response_time > self.response_time_threshold:
            self._apply_slow_response_adjustment()
            return
        
        # Handle successful fast responses
        if 200 <= status_code < 300 and response_time < 1.0:
            self._record_success()
            return
        
        # Handle other errors
        if status_code and (status_code < 200 or status_code >= 400):
            self._record_error()
    
    def adjust_for_batch_result(self, batch_result):
        """Adjust configuration based on batch results"""
        error_rate = batch_result.error_rate
        avg_response_time = batch_result.avg_response_time
        
        # Significant error rate - slow down
        if error_rate > self.error_threshold:
            logger.info(f"High error rate {error_rate:.2%}, applying slowdown")
            self._apply_adjustment(RateAdjustment.SLOW_DOWN)
        
        # High average response time - reduce concurrency
        elif avg_response_time > self.response_time_threshold:
            logger.info(f"High response time {avg_response_time:.2f}s, reducing concurrency")
            self._apply_adjustment(RateAdjustment.REDUCE_CONCURRENCY)
        
        # Good performance - consider speeding up
        elif error_rate < 0.05 and avg_response_time < 1.0:
            self.consecutive_successes += 1
            if self.consecutive_successes >= self.success_threshold_for_speedup:
                logger.info(f"Consistent good performance, speeding up")
                self._apply_adjustment(RateAdjustment.SPEED_UP)
                self.consecutive_successes = 0
    
    def apply_adjustment(self, adjustment: RateAdjustment):
        """Apply manual rate adjustment"""
        self._apply_adjustment(adjustment)
    
    def _apply_rate_limit_adjustment(self):
        """Apply adjustments for rate limiting (429 responses)"""
        logger.warning("Rate limit hit, applying backoff")
        self.current_delay = min(self.current_delay * self.backoff_multiplier, self.max_delay)
        self.current_batch_size = max(int(self.current_batch_size * 0.7), self.min_batch_size)
        self.current_concurrency = max(int(self.current_concurrency * 0.8), self.min_concurrency)
        self.consecutive_errors += 1
        self.consecutive_successes = 0
        self.total_adjustments += 1
    
    def _apply_server_error_adjustment(self):
        """Apply adjustments for server errors (5xx responses)"""
        logger.warning("Server error detected, reducing load")
        self.current_delay = min(self.current_delay * self.slowdown_multiplier, self.max_delay)
        self.current_concurrency = max(int(self.current_concurrency * 0.9), self.min_concurrency)
        self.consecutive_errors += 1
        self.consecutive_successes = 0
        self.total_adjustments += 1
    
    def _apply_slow_response_adjustment(self):
        """Apply adjustments for slow responses"""
        logger.info("Slow responses detected, applying modest slowdown")
        self.current_delay = min(self.current_delay * 1.2, self.max_delay)
        self.consecutive_errors += 1
        self.consecutive_successes = 0
        self.total_adjustments += 1
    
    def _record_success(self):
        """Record a successful fast response"""
        self.consecutive_successes += 1
        self.consecutive_errors = 0
        
        # Gradual speedup after consistent success
        if self.consecutive_successes >= self.success_threshold_for_speedup:
            self._apply_adjustment(RateAdjustment.SPEED_UP)
            self.consecutive_successes = 0
    
    def _record_error(self):
        """Record an error response"""
        self.consecutive_errors += 1
        self.consecutive_successes = 0
    
    def _apply_adjustment(self, adjustment: RateAdjustment):
        """Apply specific adjustment type"""
        if adjustment == RateAdjustment.SLOW_DOWN:
            self.current_delay = min(self.current_delay * self.slowdown_multiplier, self.max_delay)
            
        elif adjustment == RateAdjustment.SPEED_UP:
            self.current_delay = max(self.current_delay * self.speedup_multiplier, self.min_delay)
            if self.current_delay < 0.1:  # If delay is very low, try increasing batch size
                self.current_batch_size = min(self.current_batch_size + 1, self.max_batch_size)
                
        elif adjustment == RateAdjustment.REDUCE_CONCURRENCY:
            self.current_concurrency = max(self.current_concurrency - 1, self.min_concurrency)
            
        elif adjustment == RateAdjustment.INCREASE_CONCURRENCY:
            self.current_concurrency = min(self.current_concurrency + 1, self.max_concurrency)
            
        elif adjustment == RateAdjustment.RESET_TO_DEFAULT:
            self.current_delay = self.initial_delay
            self.current_batch_size = self.initial_batch_size
            self.current_concurrency = self.initial_concurrency
        
        self.total_adjustments += 1
        logger.info(f"Applied {adjustment.value}: delay={self.current_delay:.2f}, "
                   f"batch_size={self.current_batch_size}, concurrency={self.current_concurrency}")
    
    def get_current_settings(self) -> Dict[str, Any]:
        """Get current adaptive settings as dict"""
        return {
            'delay': self.current_delay,
            'batch_size': self.current_batch_size,
            'concurrency': self.current_concurrency,
            'total_adjustments': self.total_adjustments,
            'consecutive_successes': self.consecutive_successes,
            'consecutive_errors': self.consecutive_errors
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization"""
        return {
            'initial_delay': self.initial_delay,
            'initial_batch_size': self.initial_batch_size,
            'initial_concurrency': self.initial_concurrency,
            'current_delay': self.current_delay,
            'current_batch_size': self.current_batch_size,
            'current_concurrency': self.current_concurrency,
            'error_threshold': self.error_threshold,
            'response_time_threshold': self.response_time_threshold,
            'adjustment_sensitivity': self.adjustment_sensitivity,
            'total_adjustments': self.total_adjustments
        }


@dataclass
class ExecutionTemplate:
    """Pre-configured execution templates for common scenarios"""
    name: str
    description: str
    
    # Basic settings
    delay: float
    batch_size: int
    concurrency: int
    
    # Adaptation settings
    error_threshold: float = 0.1
    adjustment_sensitivity: float = 1.0
    auto_adjust: bool = True
    
    # Strategy preferences
    preferred_strategy: str = "adaptive"
    
    @classmethod
    def get_template(cls, mode: str) -> Optional['ExecutionTemplate']:
        """Get execution template by mode name"""
        templates = cls.get_all_templates()
        return templates.get(mode.lower())
    
    @classmethod
    def get_all_templates(cls) -> Dict[str, 'ExecutionTemplate']:
        """Get all available execution templates"""
        return {
            'burst': ExecutionTemplate(
                name="Burst",
                description="Maximum throughput for robust, high-capacity endpoints",
                delay=0.0,
                batch_size=10,
                concurrency=8,
                error_threshold=0.15,
                adjustment_sensitivity=1.5,
                preferred_strategy="burst"
            ),
            'conservative': ExecutionTemplate(
                name="Conservative", 
                description="Gentle execution for fragile or rate-limited endpoints",
                delay=2.0,
                batch_size=2,
                concurrency=1,
                error_threshold=0.05,
                adjustment_sensitivity=0.5,
                preferred_strategy="conservative"
            ),
            'adaptive': ExecutionTemplate(
                name="Adaptive",
                description="Smart execution that learns from endpoint responses",
                delay=0.5,
                batch_size=4,
                concurrency=3,
                error_threshold=0.1,
                adjustment_sensitivity=1.0,
                preferred_strategy="adaptive"
            ),
            'development': ExecutionTemplate(
                name="Development",
                description="Safe settings for development and testing",
                delay=1.0,
                batch_size=2,
                concurrency=2,
                error_threshold=0.2,
                adjustment_sensitivity=0.8,
                auto_adjust=False,
                preferred_strategy="conservative"
            ),
            'production': ExecutionTemplate(
                name="Production",
                description="Balanced settings for production environments",
                delay=0.3,
                batch_size=5,
                concurrency=4,
                error_threshold=0.08,
                adjustment_sensitivity=1.2,
                preferred_strategy="adaptive"
            ),
            'load_test': ExecutionTemplate(
                name="Load Test",
                description="High-volume testing to stress test endpoints",
                delay=0.0,
                batch_size=15,
                concurrency=10,
                error_threshold=0.2,
                adjustment_sensitivity=2.0,
                preferred_strategy="burst"
            ),
            'chain_sequential': ExecutionTemplate(
                name="Chain Sequential",
                description="Sequential chain execution with proper context passing",
                delay=0.5,
                batch_size=1,
                concurrency=1,
                error_threshold=0.05,
                adjustment_sensitivity=0.5,
                auto_adjust=False,
                preferred_strategy="chain"
            ),
            'chain_parallel': ExecutionTemplate(
                name="Chain Parallel",
                description="Parallel chain instances with internal sequencing",
                delay=0.3,
                batch_size=3,
                concurrency=3,
                error_threshold=0.1,
                adjustment_sensitivity=1.0,
                preferred_strategy="chain"
            )
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary"""
        return {
            'name': self.name,
            'description': self.description,
            'delay': self.delay,
            'batch_size': self.batch_size,
            'concurrency': self.concurrency,
            'error_threshold': self.error_threshold,
            'adjustment_sensitivity': self.adjustment_sensitivity,
            'auto_adjust': self.auto_adjust,
            'preferred_strategy': self.preferred_strategy
        }