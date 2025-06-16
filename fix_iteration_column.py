#!/usr/bin/env python3
"""
Script to fix the iteration column in test_executions table.
This handles any NULL values and ensures proper defaults.
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from extensions import db
from models.model_TestExecution import TestExecution

def fix_iteration_column():
    """Fix NULL iteration values in test_executions table"""
    print("Checking for NULL iteration values...")
    
    # Find records with NULL iteration
    null_iterations = TestExecution.query.filter(TestExecution.iteration.is_(None)).all()
    
    if null_iterations:
        print(f"Found {len(null_iterations)} records with NULL iteration values")
        
        # Update each record to have iteration = 1
        for execution in null_iterations:
            execution.iteration = 1
            print(f"Updated execution {execution.id} to iteration = 1")
        
        # Commit the changes
        db.session.commit()
        print("Successfully updated all NULL iteration values")
    else:
        print("No NULL iteration values found")
    
    # Verify the fix
    remaining_nulls = TestExecution.query.filter(TestExecution.iteration.is_(None)).count()
    if remaining_nulls == 0:
        print("✅ All iteration values are now properly set")
    else:
        print(f"❌ Still have {remaining_nulls} NULL iteration values")

if __name__ == "__main__":
    try:
        fix_iteration_column()
    except Exception as e:
        print(f"Error fixing iteration column: {e}")
        db.session.rollback()
        sys.exit(1)