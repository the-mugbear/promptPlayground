# services/execution/models.py
"""
Core data models for the execution engine
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import uuid


class ExecutionState(Enum):
    """Execution state enumeration"""
    PENDING = "pending"
    RUNNING = "running" 
    PAUSED = "paused"
    PAUSING = "pausing"  # Transitional state
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RateAdjustment(Enum):
    """Rate adjustment commands"""
    SLOW_DOWN = "slow_down"
    SPEED_UP = "speed_up"
    REDUCE_CONCURRENCY = "reduce_concurrency"
    INCREASE_CONCURRENCY = "increase_concurrency"
    RESET_TO_DEFAULT = "reset_to_default"


@dataclass
class ExecutionContext:
    """Context for individual task execution"""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    test_run_id: int = 0
    test_case_id: int = 0
    sequence_num: int = 0
    iteration_num: int = 1
    
    # Execution settings
    delay: float = 0.0
    timeout: int = 30
    retry_count: int = 0
    max_retries: int = 2
    
    # Request configuration
    request_config: Dict[str, Any] = field(default_factory=dict)
    
    # Adaptive settings
    batch_id: str = ""
    strategy_name: str = ""
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class TaskResult:
    """Result from individual task execution"""
    execution_id: str
    test_case_id: int
    sequence_num: int
    iteration_num: int
    
    # Response data
    status_code: Optional[int] = None
    response_body: str = ""
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_time: float = 0.0
    
    # Execution metadata
    success: bool = False
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Timestamps
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime = field(default_factory=datetime.utcnow)
    
    def needs_rate_adjustment(self) -> bool:
        """Determine if this result suggests rate adjustment is needed"""
        if self.status_code == 429:  # Rate limited
            return True
        if self.status_code and self.status_code >= 500:  # Server error
            return True
        if self.response_time > 10.0:  # Very slow response
            return True
        return False
    
    def suggested_adjustment(self) -> Optional[RateAdjustment]:
        """Suggest appropriate rate adjustment based on result"""
        if self.status_code == 429:
            return RateAdjustment.SLOW_DOWN
        elif self.status_code and self.status_code >= 500:
            return RateAdjustment.REDUCE_CONCURRENCY
        elif self.response_time > 5.0:
            return RateAdjustment.SLOW_DOWN
        elif self.response_time < 0.5 and self.success:
            return RateAdjustment.SPEED_UP
        return None


@dataclass
class BatchResult:
    """Result from batch execution"""
    batch_id: str
    batch_size: int
    results: List[TaskResult] = field(default_factory=list)
    
    # Batch metrics
    success_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    
    # Timestamps
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_metrics(self):
        """Calculate batch metrics from individual results"""
        if not self.results:
            return
            
        self.success_count = sum(1 for r in self.results if r.success)
        self.error_count = len(self.results) - self.success_count
        self.error_rate = self.error_count / len(self.results)
        
        response_times = [r.response_time for r in self.results if r.response_time > 0]
        self.avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0


@dataclass 
class ExecutionResult:
    """Final result from complete execution"""
    test_run_id: int
    strategy_name: str
    state: ExecutionState
    
    # Execution summary
    total_cases: int = 0
    completed_cases: int = 0
    successful_cases: int = 0
    failed_cases: int = 0
    
    # Performance metrics
    total_duration: float = 0.0
    avg_response_time: float = 0.0
    requests_per_second: float = 0.0
    error_rate: float = 0.0
    
    # Adaptive metrics
    initial_delay: float = 0.0
    final_delay: float = 0.0
    initial_batch_size: int = 0
    final_batch_size: int = 0
    adjustments_made: int = 0
    
    # Batch results
    batch_results: List[BatchResult] = field(default_factory=list)
    
    # Timestamps
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def calculate_summary_metrics(self):
        """Calculate summary metrics from batch results"""
        if not self.batch_results:
            return
            
        all_results = []
        for batch in self.batch_results:
            all_results.extend(batch.results)
        
        if all_results:
            self.completed_cases = len(all_results)
            self.successful_cases = sum(1 for r in all_results if r.success)
            self.failed_cases = self.completed_cases - self.successful_cases
            self.error_rate = self.failed_cases / self.completed_cases
            
            response_times = [r.response_time for r in all_results if r.response_time > 0]
            self.avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
            
            if self.total_duration > 0:
                self.requests_per_second = self.completed_cases / self.total_duration


@dataclass
class ExecutionStats:
    """Real-time execution statistics"""
    test_run_id: int
    current_state: ExecutionState
    
    # Progress
    total_cases: int = 0
    completed_cases: int = 0
    successful_cases: int = 0
    failed_cases: int = 0
    progress_percentage: float = 0.0
    
    # Current metrics
    current_rate: float = 0.0  # requests per second
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    
    # Adaptive settings
    current_delay: float = 0.0
    current_batch_size: int = 0
    current_concurrency: int = 0
    
    # Recent adjustments
    last_adjustment: Optional[RateAdjustment] = None
    last_adjustment_time: Optional[datetime] = None
    total_adjustments: int = 0
    
    # Timestamps
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def update_progress(self):
        """Update progress percentage"""
        if self.total_cases > 0:
            self.progress_percentage = (self.completed_cases / self.total_cases) * 100.0