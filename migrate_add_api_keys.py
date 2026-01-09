"""
Migration: Add API Keys table for Public Developer API

Run this script to add the api_keys table for the public API (api.mimic.cash).

Usage:
    python migrate_add_api_keys.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import inspect, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Migration")


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database"""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(db.engine)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def run_migration():
    """Run the API keys migration"""
    with app.app_context():
        logger.info("🚀 Starting API Keys migration...")
        
        # Check if table already exists
        if table_exists('api_keys'):
            logger.info("✅ Table 'api_keys' already exists")
            
            # Check for any missing columns and add them
            columns_to_check = [
                ('ip_whitelist', 'JSON'),
                ('total_requests', 'INTEGER DEFAULT 0'),
                ('revoked_at', 'DATETIME'),
            ]
            
            for col_name, col_type in columns_to_check:
                if not column_exists('api_keys', col_name):
                    logger.info(f"  Adding missing column: {col_name}")
                    try:
                        # SQLite doesn't support ADD COLUMN with constraints well
                        # PostgreSQL is more flexible
                        if 'sqlite' in str(db.engine.url):
                            db.session.execute(text(f"ALTER TABLE api_keys ADD COLUMN {col_name} {col_type}"))
                        else:
                            db.session.execute(text(f"ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        db.session.commit()
                        logger.info(f"  ✅ Added column {col_name}")
                    except Exception as e:
                        logger.warning(f"  ⚠️ Could not add column {col_name}: {e}")
                        db.session.rollback()
            
            return True
        
        # Create the table
        logger.info("📦 Creating 'api_keys' table...")
        
        # Import the model to ensure it's registered
        from models import ApiKey
        
        # Create all tables (this will only create missing ones)
        db.create_all()
        
        logger.info("✅ Table 'api_keys' created successfully!")
        
        # Create indexes if they don't exist
        try:
            # These indexes are defined in the model, but let's ensure they exist
            index_statements = [
                "CREATE INDEX IF NOT EXISTS idx_apikey_user_active ON api_keys (user_id, is_active)",
                "CREATE INDEX IF NOT EXISTS idx_apikey_key_active ON api_keys (key, is_active)",
                "CREATE INDEX IF NOT EXISTS ix_api_keys_key ON api_keys (key)",
                "CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys (user_id)",
                "CREATE INDEX IF NOT EXISTS ix_api_keys_is_active ON api_keys (is_active)",
                "CREATE INDEX IF NOT EXISTS ix_api_keys_created_at ON api_keys (created_at)",
                "CREATE INDEX IF NOT EXISTS ix_api_keys_expires_at ON api_keys (expires_at)",
            ]
            
            for stmt in index_statements:
                try:
                    db.session.execute(text(stmt))
                except Exception as e:
                    # Index might already exist or syntax differs between DBs
                    pass
            
            db.session.commit()
            logger.info("✅ Indexes created")
        except Exception as e:
            logger.warning(f"⚠️ Index creation had issues (may already exist): {e}")
            db.session.rollback()
        
        logger.info("🎉 Migration completed successfully!")
        return True


if __name__ == '__main__':
    try:
        success = run_migration()
        if success:
            print("\n✅ API Keys migration completed successfully!")
            print("\nNext steps:")
            print("1. Restart your application")
            print("2. Users can now create API keys in their profile settings")
            print("3. Configure api.mimic.cash subdomain to point to your FastAPI server")
        else:
            print("\n❌ Migration failed!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
