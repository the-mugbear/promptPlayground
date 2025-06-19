# services/execution/engine.py
"""
Main execution engine that coordinates strategy selection and execution management
"""

import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

from .controller import ExecutionController
from .config import AdaptiveConfig, ExecutionTemplate
from .strategies import (
    ExecutionStrategy, BurstExecutionStrategy, ConservativeExecutionStrategy,
    AdaptiveExecutionStrategy, ChainExecutionStrategy
)
from .models import ExecutionState, ExecutionResult

logger = logging.getLogger(__name__)


class TestExecutionEngine:
    """
    Main execution engine that manages strategy selection, execution coordination,
    and provides the primary interface for test run execution.
    
    This engine acts as the orchestrator for the new adaptive execution system,
    replacing the monolithic orchestrator approach with a flexible strategy-based system.
    """
    
    def __init__(self):
        self.strategies: List[ExecutionStrategy] = []
        self.active_executions: Dict[int, ExecutionController] = {}  # test_run_id -> controller
        self.execution_history: List[ExecutionResult] = []
        
        # Initialize available strategies
        self._register_strategies()
        
        logger.info("TestExecutionEngine initialized with strategies: " + 
                   ", ".join([s.name for s in self.strategies]))
    
    def _register_strategies(self):
        """Register all available execution strategies"""
        self.strategies = [
            ChainExecutionStrategy(),      # Highest priority for chains
            BurstExecutionStrategy(),      # For high-capacity endpoints
            ConservativeExecutionStrategy(), # For fragile endpoints  
            AdaptiveExecutionStrategy()    # Default fallback strategy
        ]
    
    def start_execution(self, test_run) -> ExecutionController:
        """
        Start execution for a test run
        
        Args:
            test_run: TestRun object with execution configuration
            
        Returns:
            ExecutionController for managing the execution
        """
        if test_run.id in self.active_executions:
            raise ValueError(f"Execution already active for test run {test_run.id}")
        
        logger.info(f"Starting execution for test run {test_run.id} (target: {test_run.target_type})")
        
        try:
            # Select appropriate strategy
            strategy = self._select_strategy(test_run)
            logger.info(f"Selected strategy: {strategy.name} for test run {test_run.id}")
            
            # Create adaptive configuration
            config = self._create_execution_config(test_run)
            
            # Create execution controller
            controller = ExecutionController(test_run, strategy, config)
            
            # Register active execution
            self.active_executions[test_run.id] = controller
            
            # Start execution
            controller.start()
            
            return controller
            
        except Exception as e:
            logger.error(f"Failed to start execution for test run {test_run.id}: {e}")
            # Clean up if registration occurred
            if test_run.id in self.active_executions:
                del self.active_executions[test_run.id]
            raise
    
    def get_execution(self, test_run_id: int) -> Optional[ExecutionController]:
        """Get active execution controller for a test run"""
        return self.active_executions.get(test_run_id)
    
    def pause_execution(self, test_run_id: int):
        """Pause execution for a test run"""
        controller = self.active_executions.get(test_run_id)
        if controller:
            controller.pause()
            logger.info(f"Paused execution for test run {test_run_id}")
        else:
            logger.warning(f"No active execution found for test run {test_run_id}")
    
    def resume_execution(self, test_run_id: int):
        """Resume execution for a test run"""
        controller = self.active_executions.get(test_run_id)
        if controller:
            controller.resume()
            logger.info(f"Resumed execution for test run {test_run_id}")
        else:
            logger.warning(f"No active execution found for test run {test_run_id}")
    
    def cancel_execution(self, test_run_id: int):
        """Cancel execution for a test run"""
        controller = self.active_executions.get(test_run_id)
        if controller:
            controller.cancel()
            # Remove from active executions
            del self.active_executions[test_run_id]
            logger.info(f"Cancelled execution for test run {test_run_id}")
        else:
            logger.warning(f"No active execution found for test run {test_run_id}")
    
    def adjust_execution_rate(self, test_run_id: int, adjustment: str, value: Optional[float] = None):
        """Adjust execution rate for a test run"""
        controller = self.active_executions.get(test_run_id)
        if controller:
            controller.adjust_rate(adjustment, value)
            logger.info(f"Adjusted execution rate for test run {test_run_id}: {adjustment}")
        else:
            logger.warning(f"No active execution found for test run {test_run_id}")
    
    def get_execution_stats(self, test_run_id: int) -> Optional[Dict[str, Any]]:
        """Get real-time execution statistics"""
        controller = self.active_executions.get(test_run_id)
        if controller:
            return controller.monitor.get_real_time_stats()
        return None
    
    def list_active_executions(self) -> List[Dict[str, Any]]:
        """List all active executions with basic info"""
        active = []
        for test_run_id, controller in self.active_executions.items():
            stats = controller.get_current_stats()
            active.append({
                'test_run_id': test_run_id,
                'execution_id': controller.execution_id,
                'state': stats.current_state.value,
                'strategy': controller.strategy.name,
                'progress_percentage': stats.progress_percentage,
                'completed_cases': stats.completed_cases,
                'total_cases': stats.total_cases,
                'error_rate': stats.error_rate,
                'started_at': controller.started_at.isoformat() if controller.started_at else None
            })
        return active
    
    def cleanup_completed_execution(self, test_run_id: int) -> Optional[ExecutionResult]:
        """Clean up completed execution and return result"""
        controller = self.active_executions.get(test_run_id)
        if not controller:
            return None
        
        # Only cleanup if execution is actually completed
        if controller.state in [ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED]:
            result = controller._create_execution_result()
            
            # Store in history
            self.execution_history.append(result)
            
            # Remove from active executions
            del self.active_executions[test_run_id]
            
            logger.info(f"Cleaned up completed execution for test run {test_run_id}")
            return result
        
        return None
    
    def get_execution_history(self, limit: int = 10) -> List[ExecutionResult]:
        """Get recent execution history"""
        return self.execution_history[-limit:] if self.execution_history else []
    
    def get_strategy_by_name(self, name: str) -> Optional[ExecutionStrategy]:
        """Get strategy by name"""
        for strategy in self.strategies:
            if strategy.name.lower() == name.lower():
                return strategy
        return None
    
    def get_available_strategies(self) -> List[Dict[str, str]]:
        """Get list of available strategies with descriptions"""
        return [
            {
                'name': strategy.name,
                'description': strategy.description
            }
            for strategy in self.strategies
        ]
    
    def register_strategy(self, strategy: ExecutionStrategy):
        """Register a new execution strategy"""
        self.strategies.append(strategy)
        logger.info(f"Registered new strategy: {strategy.name}")
    
    def _select_strategy(self, test_run) -> ExecutionStrategy:
        """
        Select the most appropriate execution strategy for a test run
        
        Args:
            test_run: TestRun object
            
        Returns:
            Selected ExecutionStrategy
        """
        target = self._get_target(test_run)
        execution_config = self._extract_execution_config(test_run)
        
        # Check for explicit strategy preference
        preferred_strategy = execution_config.get('preferred_strategy')
        if preferred_strategy:
            strategy = self.get_strategy_by_name(preferred_strategy)
            if strategy and strategy.can_handle(test_run.target_type, target, execution_config):
                return strategy
            else:
                logger.warning(f"Preferred strategy '{preferred_strategy}' not suitable, "
                             f"falling back to automatic selection")
        
        # Check for execution template
        execution_mode = getattr(test_run, 'execution_mode', None)
        if execution_mode:
            template = ExecutionTemplate.get_template(execution_mode)
            if template:
                preferred_strategy = template.preferred_strategy
                strategy = self.get_strategy_by_name(preferred_strategy)
                if strategy and strategy.can_handle(test_run.target_type, target, execution_config):
                    return strategy
        
        # Automatic strategy selection based on target and configuration
        for strategy in self.strategies:
            if strategy.can_handle(test_run.target_type, target, execution_config):
                logger.info(f"Auto-selected strategy: {strategy.name} for target type: {test_run.target_type}")
                return strategy
        
        # Fallback to adaptive strategy (should always be last in list)
        fallback_strategy = self.strategies[-1]
        logger.warning(f"No specific strategy matched, using fallback: {fallback_strategy.name}")
        return fallback_strategy
    
    def _create_execution_config(self, test_run) -> AdaptiveConfig:
        """Create adaptive configuration for a test run"""
        # Start with test run configuration
        config = AdaptiveConfig.from_test_run(test_run)
        
        # Apply endpoint-specific settings if available
        if test_run.target_type == 'endpoint' and hasattr(test_run, 'endpoint'):
            endpoint_config = AdaptiveConfig.from_endpoint(test_run.endpoint)
            
            # Merge endpoint settings (endpoint settings take precedence for limits)
            if hasattr(test_run.endpoint, 'max_concurrent_requests'):
                config.max_concurrency = min(config.max_concurrency, 
                                           test_run.endpoint.max_concurrent_requests)
            
            if hasattr(test_run.endpoint, 'recommended_delay'):
                config.min_delay = max(config.min_delay, test_run.endpoint.recommended_delay)
        
        return config
    
    def _get_target(self, test_run):
        """Get the execution target (endpoint or chain)"""
        if test_run.target_type == 'endpoint':
            return getattr(test_run, 'endpoint', None)
        elif test_run.target_type == 'chain':
            return getattr(test_run, 'chain', None)
        else:
            raise ValueError(f"Unknown target type: {test_run.target_type}")
    
    def _extract_execution_config(self, test_run) -> Dict[str, Any]:
        """Extract execution configuration from test run"""
        config = {}
        
        # Extract basic settings
        if hasattr(test_run, 'delay_between_requests'):
            config['delay_between_requests'] = test_run.delay_between_requests
        
        if hasattr(test_run, 'run_serially'):
            config['run_serially'] = test_run.run_serially
        
        if hasattr(test_run, 'execution_mode'):
            config['execution_mode'] = test_run.execution_mode
        
        # Extract preferred strategy if specified
        if hasattr(test_run, 'preferred_strategy'):
            config['preferred_strategy'] = test_run.preferred_strategy
        
        # Add target-specific configuration hints
        if test_run.target_type == 'endpoint':
            endpoint = getattr(test_run, 'endpoint', None)
            if endpoint:
                if hasattr(endpoint, 'supports_burst_traffic'):
                    config['supports_burst_traffic'] = endpoint.supports_burst_traffic
                if hasattr(endpoint, 'rate_limit_per_minute'):
                    config['rate_limit_per_minute'] = endpoint.rate_limit_per_minute
        
        elif test_run.target_type == 'chain':
            chain = getattr(test_run, 'chain', None)
            if chain:
                if hasattr(chain, 'allow_parallel_instances'):
                    config['allow_parallel_instances'] = chain.allow_parallel_instances
                if hasattr(chain, 'max_parallel_instances'):
                    config['max_parallel_instances'] = chain.max_parallel_instances
        
        return config


# Global engine instance
_execution_engine: Optional[TestExecutionEngine] = None


def get_execution_engine() -> TestExecutionEngine:
    """Get the global execution engine instance"""
    global _execution_engine
    if _execution_engine is None:
        _execution_engine = TestExecutionEngine()
    return _execution_engine


def create_execution_engine() -> TestExecutionEngine:
    """Create a new execution engine instance"""
    return TestExecutionEngine()


# Convenience functions for common operations
def start_test_execution(test_run) -> ExecutionController:
    """Start execution for a test run using the global engine"""
    engine = get_execution_engine()
    return engine.start_execution(test_run)


def get_test_execution(test_run_id: int) -> Optional[ExecutionController]:
    """Get active execution controller for a test run"""
    engine = get_execution_engine()
    return engine.get_execution(test_run_id)


def pause_test_execution(test_run_id: int):
    """Pause execution for a test run"""
    engine = get_execution_engine()
    engine.pause_execution(test_run_id)


def resume_test_execution(test_run_id: int):
    """Resume execution for a test run"""
    engine = get_execution_engine()
    engine.resume_execution(test_run_id)


def cancel_test_execution(test_run_id: int):
    """Cancel execution for a test run"""
    engine = get_execution_engine()
    engine.cancel_execution(test_run_id)


def get_execution_stats(test_run_id: int) -> Optional[Dict[str, Any]]:
    """Get real-time execution statistics"""
    engine = get_execution_engine()
    return engine.get_execution_stats(test_run_id)