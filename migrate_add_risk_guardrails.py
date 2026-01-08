"""
Migration: Add Risk Guardrails columns to User model

This migration adds the following columns:
- daily_drawdown_limit_perc: Maximum daily drawdown percentage (default 10%)
- daily_profit_target_perc: Daily profit lock percentage (default 20%)
- risk_guardrails_enabled: Whether risk guardrails are enabled for this user
- risk_guardrails_paused_at: Timestamp when user was paused by guardrails
- risk_guardrails_reason: Reason for pause (drawdown/profit_lock)

Usage:
    python migrate_add_risk_guardrails.py
"""

import os
import sys
from sqlalchemy import text, inspect

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from models import db
from flask import Flask


def run_migration():
    """Run the migration to add risk guardrails columns"""
    
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    
    with app.app_context():
        # Check which columns already exist
        inspector = inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('users')]
        
        migrations = []
        
        # Define columns to add
        columns_to_add = [
            ('daily_drawdown_limit_perc', 'FLOAT DEFAULT 10.0'),
            ('daily_profit_target_perc', 'FLOAT DEFAULT 20.0'),
            ('risk_guardrails_enabled', 'BOOLEAN DEFAULT FALSE'),
            ('risk_guardrails_paused_at', 'DATETIME'),
            ('risk_guardrails_reason', 'VARCHAR(100)'),
        ]
        
        for col_name, col_def in columns_to_add:
            if col_name not in existing_columns:
                migrations.append((col_name, col_def))
                print(f"📋 Will add column: {col_name}")
            else:
                print(f"✅ Column already exists: {col_name}")
        
        if not migrations:
            print("\n✅ All columns already exist. Nothing to migrate.")
            return
        
        # Determine database type
        db_url = str(db.engine.url)
        is_sqlite = 'sqlite' in db_url
        is_postgres = 'postgresql' in db_url or 'postgres' in db_url
        
        print(f"\n🔧 Database type: {'SQLite' if is_sqlite else 'PostgreSQL' if is_postgres else 'Unknown'}")
        print(f"🔧 Running {len(migrations)} migrations...\n")
        
        for col_name, col_def in migrations:
            try:
                if is_sqlite:
                    # SQLite syntax
                    sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"
                else:
                    # PostgreSQL syntax
                    sql = f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                
                db.session.execute(text(sql))
                db.session.commit()
                print(f"✅ Added column: {col_name}")
                
            except Exception as e:
                db.session.rollback()
                if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                    print(f"⚠️ Column {col_name} already exists (skipping)")
                else:
                    print(f"❌ Error adding {col_name}: {e}")
        
        print("\n✅ Migration completed successfully!")
        print("\nℹ️ Risk Guardrails columns have been added to the users table.")
        print("   - daily_drawdown_limit_perc: Default 10% (stop if equity drops 10%)")
        print("   - daily_profit_target_perc: Default 20% (lock if profit reaches 20%)")
        print("   - risk_guardrails_enabled: Default False (must be enabled per user)")


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║           MIMIC - Risk Guardrails Migration                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  Adding daily equity protection columns to User model                ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    run_migration()

