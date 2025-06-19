# services/execution/integration.py
"""
Integration bridge between the execution engine and the database models

This module provides the interface for the execution engine to work with
the simplified database models, handling execution tracking and persistence.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from extensions import db
from models import TestRun, ExecutionSession, ExecutionResult
from .engine import get_execution_engine, TestExecutionEngine
from .controller import ExecutionController
from .models import TaskResult, ExecutionState
from .config import AdaptiveConfig

logger = logging.getLogger(__name__)


class ExecutionIntegrationService:
    """
    Service that integrates the execution engine with the database models
    
    This service acts as a bridge between the new execution engine and the
    existing database structure, managing execution sessions and results.
    """
    
    def __init__(self, engine: Optional[TestExecutionEngine] = None):
        self.engine = engine or get_execution_engine()
    
    def start_test_run_execution(self, test_run: TestRun) -> ExecutionController:
        """
        Start execution for a test run using the execution engine
        
        Args:
            test_run: TestRun model instance
            
        Returns:
            ExecutionController for managing the execution
        """
        logger.info(f"Starting execution for test run {test_run.id} using execution engine")
        
        try:
            # Check if already has an active execution
            existing_session = test_run.get_active_execution_session()
            if existing_session:
                logger.warning(f"Test run {test_run.id} already has active execution session {existing_session.id}")
                # Get existing controller if possible
                existing_controller = self.engine.get_execution(test_run.id)
                if existing_controller:
                    return existing_controller
                else:
                    # Clean up orphaned session
                    existing_session.complete_execution('cancelled')
                    db.session.commit()
            
            # Start new execution
            controller = self.engine.start_execution(test_run)
            
            # Create execution session record
            session = ExecutionSession(
                test_run_id=test_run.id,
                execution_id=controller.execution_id,
                strategy_name=controller.strategy.name,
                state=controller.state.value,
                total_cases=controller.total_cases,
                config_snapshot=controller.config.to_dict()
            )
            
            db.session.add(session)
            
            # Update test run status
            test_run.status = 'running'
            test_run.started_at = datetime.utcnow()
            
            db.session.commit()
            
            # Set up result tracking
            self._setup_result_tracking(controller, session)
            
            logger.info(f"Execution started for test run {test_run.id} with session {session.id}")
            return controller
            
        except Exception as e:
            logger.error(f"Failed to start execution for test run {test_run.id}: {e}")
            # Rollback any database changes
            db.session.rollback()
            raise
    
    def pause_test_run_execution(self, test_run_id: int):
        """Pause execution for a test run"""
        self.engine.pause_execution(test_run_id)
        self._update_test_run_status(test_run_id, 'paused')
    
    def resume_test_run_execution(self, test_run_id: int):
        """Resume execution for a test run"""
        self.engine.resume_execution(test_run_id)
        self._update_test_run_status(test_run_id, 'running')
    
    def cancel_test_run_execution(self, test_run_id: int):
        """Cancel execution for a test run"""
        self.engine.cancel_execution(test_run_id)
        self._update_test_run_status(test_run_id, 'cancelled')
        
        # Complete execution session
        test_run = TestRun.query.get(test_run_id)
        if test_run:
            session = test_run.get_active_execution_session()
            if session:
                session.complete_execution('cancelled')
                db.session.commit()
    
    def get_execution_status(self, test_run_id: int) -> Optional[Dict[str, Any]]:
        """Get current execution status for a test run"""
        controller = self.engine.get_execution(test_run_id)
        if controller:
            stats = controller.monitor.get_real_time_stats()
            
            # Get database session info
            test_run = TestRun.query.get(test_run_id)
            if test_run:
                session = test_run.get_active_execution_session()
                if session:
                    stats['session_info'] = session.to_dict()
            
            return stats
        return None
    
    def cleanup_completed_execution(self, test_run_id: int):
        """Clean up completed execution and update database"""
        try:
            # Get execution result from engine
            result = self.engine.cleanup_completed_execution(test_run_id)
            
            if result:
                # Update test run status
                test_run = TestRun.query.get(test_run_id)
                if test_run:
                    test_run.status = 'completed' if result.state == ExecutionState.COMPLETED else 'failed'
                    test_run.completed_at = datetime.utcnow()
                    
                    # Update execution session
                    session = test_run.get_active_execution_session()
                    if session:
                        session.complete_execution(result.state.value)
                        session.total_cases = result.total_cases
                        session.completed_cases = result.completed_cases
                        session.successful_cases = result.successful_cases
                        session.failed_cases = result.failed_cases
                    
                    db.session.commit()
                
                logger.info(f"Cleaned up execution for test run {test_run_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup execution for test run {test_run_id}: {e}")
            db.session.rollback()
    
    def get_execution_results(self, test_run_id: int, limit: int = 100) -> List[ExecutionResult]:
        """Get execution results for a test run"""
        test_run = TestRun.query.get(test_run_id)
        if not test_run:
            return []
        
        session = ExecutionSession.query.filter_by(test_run_id=test_run_id).first()
        if not session:
            return []
        
        return ExecutionResult.query.filter_by(
            execution_session_id=session.id
        ).order_by(
            ExecutionResult.sequence_num
        ).limit(limit).all()
    
    def get_execution_summary(self, test_run_id: int) -> Dict[str, Any]:
        """Get execution summary for a test run"""
        test_run = TestRun.query.get(test_run_id)
        if not test_run:
            return {}
        
        session = ExecutionSession.query.filter_by(test_run_id=test_run_id).first()
        if not session:
            return {
                'test_run_id': test_run_id,
                'status': test_run.status,
                'using_execution_engine': test_run.is_using_execution_engine(),
                'has_execution_session': False
            }
        
        # Get result statistics
        results = ExecutionResult.query.filter_by(execution_session_id=session.id).all()
        
        summary = {
            'test_run_id': test_run_id,
            'execution_session_id': session.id,
            'execution_id': session.execution_id,
            'strategy_name': session.strategy_name,
            'status': session.state,
            'using_execution_engine': True,
            'has_execution_session': True,
            'total_cases': session.total_cases,
            'completed_cases': session.completed_cases,
            'successful_cases': session.successful_cases,
            'failed_cases': session.failed_cases,
            'progress_percentage': session.progress_percentage,
            'error_rate': session.error_rate,
            'success_rate': session.success_rate,
            'started_at': session.started_at.isoformat(),
            'updated_at': session.updated_at.isoformat() if session.updated_at else None,
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
            'config_snapshot': session.config_snapshot,
            'metrics_snapshot': session.metrics_snapshot,
            'result_count': len(results)
        }
        
        return summary
    
    def _setup_result_tracking(self, controller: ExecutionController, session: ExecutionSession):
        """Set up result tracking for the execution controller"""
        
        def on_task_result(task_result: TaskResult):
            """Handle individual task results"""
            try:
                # Create execution result record
                result = ExecutionResult.from_task_result(
                    task_result=task_result,
                    session_id=session.id,
                    test_case_id=task_result.test_case_id
                )
                
                db.session.add(result)
                
                # Update session progress
                session.update_progress(
                    completed=controller.completed_cases,
                    successful=controller.successful_cases,
                    failed=controller.failed_cases
                )
                
                db.session.commit()
                
            except Exception as e:
                logger.error(f"Failed to record task result: {e}")
                db.session.rollback()
        
        def on_progress_update(stats: Dict[str, Any]):
            """Handle progress updates"""
            try:
                # Update session metrics
                session.update_metrics_snapshot(stats.get('current_metrics', {}))
                session.update_config_snapshot(stats.get('adaptive_settings', {}))
                
                db.session.commit()
                
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")
                db.session.rollback()
        
        # Add callbacks to the controller
        controller.add_adjustment_callback(lambda adj, config: self._on_adjustment(session, adj, config))
        controller.monitor.add_progress_callback(on_progress_update)
    
    def _on_adjustment(self, session: ExecutionSession, adjustment, config: Dict[str, Any]):
        """Handle rate adjustments"""
        try:
            session.update_config_snapshot(config)
            db.session.commit()
            logger.info(f"Recorded adjustment {adjustment} for session {session.id}")
        except Exception as e:
            logger.error(f"Failed to record adjustment: {e}")
            db.session.rollback()
    
    def _update_test_run_status(self, test_run_id: int, status: str):
        """Update test run status"""
        try:
            test_run = TestRun.query.get(test_run_id)
            if test_run:
                test_run.status = status
                if status in ['completed', 'failed', 'cancelled']:
                    test_run.completed_at = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to update test run status: {e}")
            db.session.rollback()


# Global integration service instance
_integration_service: Optional[ExecutionIntegrationService] = None


def get_integration_service() -> ExecutionIntegrationService:
    """Get the global integration service instance"""
    global _integration_service
    if _integration_service is None:
        _integration_service = ExecutionIntegrationService()
    return _integration_service


# Convenience functions for use in routes
def start_test_run_with_engine(test_run: TestRun) -> ExecutionController:
    """Start test run execution using the execution engine"""
    service = get_integration_service()
    return service.start_test_run_execution(test_run)


def pause_test_run(test_run_id: int):
    """Pause test run execution"""
    service = get_integration_service()
    service.pause_test_run_execution(test_run_id)


def resume_test_run(test_run_id: int):
    """Resume test run execution"""
    service = get_integration_service()
    service.resume_test_run_execution(test_run_id)


def cancel_test_run(test_run_id: int):
    """Cancel test run execution"""
    service = get_integration_service()
    service.cancel_test_run_execution(test_run_id)


def get_test_run_status(test_run_id: int) -> Optional[Dict[str, Any]]:
    """Get test run execution status"""
    service = get_integration_service()
    return service.get_execution_status(test_run_id)


def get_test_run_summary(test_run_id: int) -> Dict[str, Any]:
    """Get test run execution summary"""
    service = get_integration_service()
    return service.get_execution_summary(test_run_id)