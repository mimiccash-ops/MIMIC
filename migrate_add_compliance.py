"""
Migration: Add User Consent table for TOS compliance tracking.

Run this migration to add the user_consents table for tracking
Terms of Service and Risk Disclaimer acceptance.

Usage:
    python migrate_add_compliance.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from sqlalchemy import text, inspect
from config import Config
from models import db, UserConsent

def run_migration():
    """Run the compliance migration"""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        # Check if table already exists
        if 'user_consents' in existing_tables:
            print("✅ Table 'user_consents' already exists - skipping creation")
            return True
        
        print("🔄 Creating user_consents table...")
        
        # Detect database type
        db_url = str(db.engine.url)
        is_postgres = 'postgresql' in db_url
        is_sqlite = 'sqlite' in db_url
        
        if is_postgres:
            # PostgreSQL syntax
            sql = """
            CREATE TABLE IF NOT EXISTS user_consents (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tos_version VARCHAR(20) NOT NULL,
                accepted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                ip_address VARCHAR(45),
                user_agent VARCHAR(512),
                consent_type VARCHAR(50) DEFAULT 'tos_and_risk_disclaimer'
            );
            
            -- Create indexes for performance
            CREATE INDEX IF NOT EXISTS idx_user_consents_user_id ON user_consents(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_consents_tos_version ON user_consents(tos_version);
            CREATE INDEX IF NOT EXISTS idx_user_consents_accepted_at ON user_consents(accepted_at);
            CREATE INDEX IF NOT EXISTS idx_consent_user_version ON user_consents(user_id, tos_version);
            """
        else:
            # SQLite syntax
            sql = """
            CREATE TABLE IF NOT EXISTS user_consents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tos_version VARCHAR(20) NOT NULL,
                accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                ip_address VARCHAR(45),
                user_agent VARCHAR(512),
                consent_type VARCHAR(50) DEFAULT 'tos_and_risk_disclaimer'
            );
            
            CREATE INDEX IF NOT EXISTS idx_user_consents_user_id ON user_consents(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_consents_tos_version ON user_consents(tos_version);
            CREATE INDEX IF NOT EXISTS idx_user_consents_accepted_at ON user_consents(accepted_at);
            CREATE INDEX IF NOT EXISTS idx_consent_user_version ON user_consents(user_id, tos_version);
            """
        
        try:
            # Execute statements one by one
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for stmt in statements:
                db.session.execute(text(stmt))
            db.session.commit()
            print("✅ Successfully created user_consents table")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating table: {e}")
            return False


if __name__ == '__main__':
    print("=" * 50)
    print("Brain Capital - Compliance Migration")
    print("=" * 50)
    success = run_migration()
    sys.exit(0 if success else 1)
