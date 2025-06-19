#!/usr/bin/env python3
"""
Create Fresh Database Schema for Execution Engine

This script creates a completely fresh, modern database schema
optimized for the execution engine with no legacy baggage.
"""

import os
import shutil
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, init, migrate, upgrade
from extensions import db

def create_fresh_app():
    """Create Flask app for database operations"""
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://localhost/fuzzyprompts_fresh')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'fresh-db-setup'
    
    db.init_app(app)
    migrate = Migrate(app, db)
    
    return app

def main():
    print("🚀 Creating Fresh Database Schema for Execution Engine")
    print("=" * 60)
    
    # Remove old migrations if they exist
    if os.path.exists('migrations'):
        print("🗑️ Removing old migrations...")
        shutil.rmtree('migrations')
    
    app = create_fresh_app()
    
    with app.app_context():
        # Initialize fresh migrations
        print("📝 Initializing fresh migrations...")
        init()
        
        # Create initial migration
        print("📦 Creating initial migration...")
        migrate(message="Initial fresh schema for execution engine")
        
        # Apply migration
        print("⬆️ Applying migration...")
        upgrade()
        
        print("\n✅ Fresh database schema created successfully!")
        print("🎯 Next: Update models to use execution engine")

if __name__ == '__main__':
    main()