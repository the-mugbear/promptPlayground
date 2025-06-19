# services/execution/__init__.py
"""
Adaptive Execution Engine for FuzzyPrompts

This module provides a flexible, strategy-based execution system for test runs
that can adapt to different endpoint capabilities and execution requirements.

Architecture Overview:
- TestExecutionEngine: Main orchestrator for strategy selection and execution management
- ExecutionController: Stateful management of individual test run executions
- ExecutionStrategy: Base class for different execution patterns (Burst, Conservative, Adaptive, Chain)
- AdaptiveConfig: Dynamic configuration that learns and adjusts during execution
- ExecutionMonitor: Real-time monitoring and metrics collection
- Models: Data structures for execution context, results, and state management
"""

# Core engine components
from .engine import (
    TestExecutionEngine, 
    get_execution_engine, 
    create_execution_engine,
    start_test_execution,
    get_test_execution,
    pause_test_execution,
    resume_test_execution,
    cancel_test_execution,
    get_execution_stats
)

# Integration with database models (conditional import)
try:
    from .integration import (
        ExecutionIntegrationService,
        get_integration_service,
        start_test_run_with_engine,
        pause_test_run,
        resume_test_run,
        cancel_test_run,
        get_test_run_status,
        get_test_run_summary
    )
    _INTEGRATION_AVAILABLE = True
except ImportError:
    # Flask/SQLAlchemy not available, skip integration imports
    _INTEGRATION_AVAILABLE = False

# Execution management
from .controller import ExecutionController

# Strategy implementations
from .strategies import (
    ExecutionStrategy,
    BurstExecutionStrategy,
    ConservativeExecutionStrategy,
    AdaptiveExecutionStrategy,
    ChainExecutionStrategy
)

# Configuration and templates
from .config import AdaptiveConfig, ExecutionTemplate, ExecutionMode

# Data models
from .models import (
    ExecutionContext, 
    ExecutionResult, 
    ExecutionState, 
    ExecutionStats,
    TaskResult, 
    BatchResult, 
    RateAdjustment
)

# Monitoring and metrics
from .monitor import ExecutionMonitor, RealTimeMetrics, MetricWindow

__all__ = [
    # Core engine
    'TestExecutionEngine',
    'get_execution_engine',
    'create_execution_engine',
    
    # Engine convenience functions
    'start_test_execution',
    'get_test_execution', 
    'pause_test_execution',
    'resume_test_execution',
    'cancel_test_execution',
    'get_execution_stats',
    
    # Database integration (if available)
    *(['ExecutionIntegrationService',
       'get_integration_service',
       'start_test_run_with_engine',
       'pause_test_run',
       'resume_test_run',
       'cancel_test_run',
       'get_test_run_status',
       'get_test_run_summary'] if _INTEGRATION_AVAILABLE else []),
    
    # Management components
    'ExecutionController',
    
    # Strategies
    'ExecutionStrategy',
    'BurstExecutionStrategy',
    'ConservativeExecutionStrategy', 
    'AdaptiveExecutionStrategy',
    'ChainExecutionStrategy',
    
    # Configuration
    'AdaptiveConfig',
    'ExecutionTemplate',
    'ExecutionMode',
    
    # Data models
    'ExecutionContext',
    'ExecutionResult',
    'ExecutionState',
    'ExecutionStats',
    'TaskResult',
    'BatchResult',
    'RateAdjustment',
    
    # Monitoring
    'ExecutionMonitor',
    'RealTimeMetrics',
    'MetricWindow'
]

# Version and metadata
__version__ = '1.0.0'
__author__ = 'FuzzyPrompts Team'
__description__ = 'Adaptive execution engine for AI security testing'