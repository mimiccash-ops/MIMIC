"""
Migration: Add push_subscriptions table for PWA Web Push notifications

Run this script to add the PushSubscription table to your database:
    python migrate_add_push_subscriptions.py

This migration adds support for Web Push notifications as part of the PWA feature.
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text, inspect


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database"""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Run the migration"""
    print("=" * 60)
    print("Migration: Add Push Subscriptions Table")
    print("=" * 60)
    
    with app.app_context():
        # Check if table already exists
        if check_table_exists('push_subscriptions'):
            print("✅ Table 'push_subscriptions' already exists")
            
            # Check for any missing columns and add them
            columns_to_check = [
                ('error_count', 'INTEGER DEFAULT 0'),
                ('last_used_at', 'TIMESTAMP'),
                ('language', "VARCHAR(10) DEFAULT 'en'")
            ]
            
            for col_name, col_type in columns_to_check:
                if not check_column_exists('push_subscriptions', col_name):
                    print(f"  Adding column: {col_name}")
                    try:
                        db.session.execute(text(
                            f"ALTER TABLE push_subscriptions ADD COLUMN {col_name} {col_type}"
                        ))
                        db.session.commit()
                        print(f"  ✅ Column '{col_name}' added")
                    except Exception as e:
                        print(f"  ⚠️ Could not add column '{col_name}': {e}")
                        db.session.rollback()
            
            return True
        
        # Create the table
        print("Creating 'push_subscriptions' table...")
        
        # Determine database type
        db_url = str(db.engine.url)
        is_sqlite = 'sqlite' in db_url
        is_postgres = 'postgresql' in db_url or 'postgres' in db_url
        
        if is_sqlite:
            create_sql = """
            CREATE TABLE push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh_key VARCHAR(500) NOT NULL,
                auth_key VARCHAR(500) NOT NULL,
                user_agent VARCHAR(500),
                language VARCHAR(10) DEFAULT 'en',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        else:
            # PostgreSQL
            create_sql = """
            CREATE TABLE push_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh_key VARCHAR(500) NOT NULL,
                auth_key VARCHAR(500) NOT NULL,
                user_agent VARCHAR(500),
                language VARCHAR(10) DEFAULT 'en',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                last_used_at TIMESTAMP WITH TIME ZONE,
                error_count INTEGER DEFAULT 0
            )
            """
        
        try:
            db.session.execute(text(create_sql))
            db.session.commit()
            print("✅ Table 'push_subscriptions' created successfully")
        except Exception as e:
            print(f"❌ Error creating table: {e}")
            db.session.rollback()
            return False
        
        # Create indexes
        print("Creating indexes...")
        
        indexes = [
            ("idx_push_user_id", "CREATE INDEX idx_push_user_id ON push_subscriptions(user_id)"),
            ("idx_push_is_active", "CREATE INDEX idx_push_is_active ON push_subscriptions(is_active)"),
            ("idx_push_user_active", "CREATE INDEX idx_push_user_active ON push_subscriptions(user_id, is_active)")
        ]
        
        for idx_name, idx_sql in indexes:
            try:
                db.session.execute(text(idx_sql))
                db.session.commit()
                print(f"  ✅ Index '{idx_name}' created")
            except Exception as e:
                # Index might already exist
                print(f"  ⚠️ Index '{idx_name}': {e}")
                db.session.rollback()
        
        print()
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Generate VAPID keys (see below)")
        print("2. Add keys to .env or config.ini")
        print("3. Install pywebpush: pip install pywebpush")
        print()
        print("Generate VAPID keys with:")
        print("  python generate_vapid_keys.py")
        print()
        
        return True


if __name__ == '__main__':
    migrate()
