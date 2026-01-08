"""
Migration script to add Smart Features columns:
- Risk Multiplier for position sizing
- DCA (Dollar Cost Averaging) settings
- Trailing Stop-Loss settings

Run this script once to update the database schema.
"""

import os
import sys
from sqlalchemy import text, inspect

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from config import Config
from models import db, User

def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column already exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def run_migration():
    """Add Smart Features columns to users table"""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        engine = db.engine
        
        # New columns to add with their SQL definitions
        new_columns = [
            # Risk multiplier
            ('risk_multiplier', 'FLOAT DEFAULT 1.0'),
            # DCA columns
            ('dca_enabled', 'BOOLEAN DEFAULT FALSE'),
            ('dca_multiplier', 'FLOAT DEFAULT 1.0'),
            ('dca_threshold', 'FLOAT DEFAULT -2.0'),
            ('dca_max_orders', 'INTEGER DEFAULT 3'),
            # Trailing Stop-Loss columns
            ('trailing_sl_enabled', 'BOOLEAN DEFAULT FALSE'),
            ('trailing_sl_activation', 'FLOAT DEFAULT 1.0'),
            ('trailing_sl_callback', 'FLOAT DEFAULT 0.5'),
        ]
        
        added_columns = []
        skipped_columns = []
        
        for column_name, column_def in new_columns:
            if check_column_exists(engine, 'users', column_name):
                skipped_columns.append(column_name)
                continue
            
            try:
                # SQLite uses different syntax than PostgreSQL
                if 'sqlite' in str(engine.url):
                    sql = f"ALTER TABLE users ADD COLUMN {column_name} {column_def}"
                else:
                    # PostgreSQL syntax
                    sql = f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column_name} {column_def}"
                
                with engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
                
                added_columns.append(column_name)
                print(f"✅ Added column: {column_name}")
                
            except Exception as e:
                print(f"⚠️ Error adding {column_name}: {e}")
        
        # Summary
        print("\n" + "=" * 50)
        print("MIGRATION SUMMARY - Smart Features")
        print("=" * 50)
        
        if added_columns:
            print(f"✅ Added {len(added_columns)} new columns:")
            for col in added_columns:
                print(f"   - {col}")
        
        if skipped_columns:
            print(f"⏭️ Skipped {len(skipped_columns)} existing columns:")
            for col in skipped_columns:
                print(f"   - {col}")
        
        if not added_columns and not skipped_columns:
            print("❌ No columns were processed")
        
        print("=" * 50)
        print("Migration complete!")


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("MIMIC v3.0 - Smart Features Migration")
    print("=" * 50)
    print("This will add Risk Multiplier, DCA, and Trailing Stop-Loss columns to the users table.\n")
    
    run_migration()

