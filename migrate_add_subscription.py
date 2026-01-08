"""
Database Migration: Add Subscription System Tables and Columns

This script adds the subscription system to the database:
1. Adds missing user columns (risk_multiplier, subscription fields, etc.)
2. Creates payments table

Usage:
    python migrate_add_subscription.py

This migration is idempotent - safe to run multiple times.
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

def get_db_connection():
    """Get database connection based on config"""
    db_url = Config.SQLALCHEMY_DATABASE_URI
    
    if 'sqlite' in db_url:
        # SQLite
        db_path = db_url.replace('sqlite:///', '')
        return sqlite3.connect(db_path), 'sqlite'
    elif 'postgresql' in db_url:
        # PostgreSQL
        import psycopg2
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        ), 'postgresql'
    else:
        raise ValueError(f"Unsupported database: {db_url}")


def column_exists(cursor, table, column, db_type):
    """Check if a column exists in a table"""
    if db_type == 'sqlite':
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        return column in columns
    else:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        """, (table, column))
        return cursor.fetchone() is not None


def table_exists(cursor, table, db_type):
    """Check if a table exists"""
    if db_type == 'sqlite':
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        return cursor.fetchone() is not None
    else:
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_name = %s
        """, (table,))
        return cursor.fetchone() is not None


def migrate():
    """Run the migration"""
    print("=" * 60)
    print("🔄 SUBSCRIPTION SYSTEM MIGRATION")
    print("=" * 60)
    
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    print(f"\n📊 Database type: {db_type.upper()}")
    
    # Track changes
    changes = []
    
    try:
        # ============================================================
        # 1. Add missing user columns (including older migrations)
        # ============================================================
        print("\n📋 Step 1: Adding missing columns to users table...")
        
        # risk_multiplier (from earlier migration)
        if not column_exists(cursor, 'users', 'risk_multiplier', db_type):
            if db_type == 'sqlite':
                cursor.execute("ALTER TABLE users ADD COLUMN risk_multiplier FLOAT DEFAULT 1.0")
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN risk_multiplier FLOAT DEFAULT 1.0")
            changes.append("✅ Added column: users.risk_multiplier")
            print("   ✅ Added risk_multiplier column")
        else:
            print("   ⏭️  risk_multiplier already exists")
        
        # referral_code (from earlier migration)
        if not column_exists(cursor, 'users', 'referral_code', db_type):
            if db_type == 'sqlite':
                # SQLite doesn't support UNIQUE in ALTER TABLE, add column first then create index
                cursor.execute("ALTER TABLE users ADD COLUMN referral_code VARCHAR(20)")
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
                except:
                    pass  # Index may already exist
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN referral_code VARCHAR(20) UNIQUE")
            changes.append("✅ Added column: users.referral_code")
            print("   ✅ Added referral_code column")
        else:
            print("   ⏭️  referral_code already exists")
        
        # referred_by_id (from earlier migration)
        if not column_exists(cursor, 'users', 'referred_by_id', db_type):
            if db_type == 'sqlite':
                cursor.execute("ALTER TABLE users ADD COLUMN referred_by_id INTEGER REFERENCES users(id)")
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN referred_by_id INTEGER REFERENCES users(id)")
            changes.append("✅ Added column: users.referred_by_id")
            print("   ✅ Added referred_by_id column")
        else:
            print("   ⏭️  referred_by_id already exists")
        
        # avatar (from earlier migration)
        if not column_exists(cursor, 'users', 'avatar', db_type):
            if db_type == 'sqlite':
                cursor.execute("ALTER TABLE users ADD COLUMN avatar VARCHAR(100) DEFAULT '🧑‍💻'")
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN avatar VARCHAR(100) DEFAULT '🧑‍💻'")
            changes.append("✅ Added column: users.avatar")
            print("   ✅ Added avatar column")
        else:
            print("   ⏭️  avatar already exists")
        
        # avatar_type (from earlier migration)
        if not column_exists(cursor, 'users', 'avatar_type', db_type):
            if db_type == 'sqlite':
                cursor.execute("ALTER TABLE users ADD COLUMN avatar_type VARCHAR(20) DEFAULT 'emoji'")
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN avatar_type VARCHAR(20) DEFAULT 'emoji'")
            changes.append("✅ Added column: users.avatar_type")
            print("   ✅ Added avatar_type column")
        else:
            print("   ⏭️  avatar_type already exists")
        
        # subscription_plan
        if not column_exists(cursor, 'users', 'subscription_plan', db_type):
            if db_type == 'sqlite':
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_plan VARCHAR(50) DEFAULT 'free'")
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_plan VARCHAR(50) DEFAULT 'free'")
            changes.append("✅ Added column: users.subscription_plan")
            print("   ✅ Added subscription_plan column")
        else:
            print("   ⏭️  subscription_plan already exists")
        
        # subscription_expires_at
        if not column_exists(cursor, 'users', 'subscription_expires_at', db_type):
            if db_type == 'sqlite':
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_expires_at DATETIME")
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_expires_at TIMESTAMP")
            changes.append("✅ Added column: users.subscription_expires_at")
            print("   ✅ Added subscription_expires_at column")
        else:
            print("   ⏭️  subscription_expires_at already exists")
        
        # subscription_notified_expiring
        if not column_exists(cursor, 'users', 'subscription_notified_expiring', db_type):
            if db_type == 'sqlite':
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_notified_expiring BOOLEAN DEFAULT 0")
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_notified_expiring BOOLEAN DEFAULT FALSE")
            changes.append("✅ Added column: users.subscription_notified_expiring")
            print("   ✅ Added subscription_notified_expiring column")
        else:
            print("   ⏭️  subscription_notified_expiring already exists")
        
        # ============================================================
        # 2. Create payments table
        # ============================================================
        print("\n📋 Step 2: Creating payments table...")
        
        if not table_exists(cursor, 'payments', db_type):
            if db_type == 'sqlite':
                cursor.execute("""
                    CREATE TABLE payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        provider VARCHAR(50) DEFAULT 'plisio',
                        provider_txn_id VARCHAR(200),
                        amount_usd FLOAT NOT NULL,
                        amount_crypto FLOAT,
                        currency VARCHAR(20) DEFAULT 'USDT_TRC20',
                        plan VARCHAR(50) NOT NULL,
                        days INTEGER DEFAULT 30,
                        status VARCHAR(30) DEFAULT 'pending',
                        wallet_address VARCHAR(200),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        completed_at DATETIME,
                        expires_at DATETIME
                    )
                """)
                # Add unique index separately for SQLite
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_provider_txn_id ON payments(provider_txn_id)")
            else:
                cursor.execute("""
                    CREATE TABLE payments (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        provider VARCHAR(50) DEFAULT 'plisio',
                        provider_txn_id VARCHAR(200) UNIQUE,
                        amount_usd FLOAT NOT NULL,
                        amount_crypto FLOAT,
                        currency VARCHAR(20) DEFAULT 'USDT_TRC20',
                        plan VARCHAR(50) NOT NULL,
                        days INTEGER DEFAULT 30,
                        status VARCHAR(30) DEFAULT 'pending',
                        wallet_address VARCHAR(200),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        expires_at TIMESTAMP
                    )
                """)
            changes.append("✅ Created table: payments")
            print("   ✅ Created payments table")
        else:
            print("   ⏭️  payments table already exists")
        
        # ============================================================
        # 3. Create indexes
        # ============================================================
        print("\n📋 Step 3: Creating indexes...")
        
        # Index on subscription_expires_at
        try:
            if db_type == 'sqlite':
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_subscription_expires ON users(subscription_expires_at)")
            else:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_subscription_expires ON users(subscription_expires_at)")
            print("   ✅ Created index on users.subscription_expires_at")
        except Exception as e:
            print(f"   ⏭️  Index may already exist: {e}")
        
        # Index on payments.user_id
        try:
            if db_type == 'sqlite':
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_user_id ON payments(user_id)")
            else:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_user_id ON payments(user_id)")
            print("   ✅ Created index on payments.user_id")
        except Exception as e:
            print(f"   ⏭️  Index may already exist: {e}")
        
        # Index on payments.status
        try:
            if db_type == 'sqlite':
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_status ON payments(status)")
            else:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_status ON payments(status)")
            print("   ✅ Created index on payments.status")
        except Exception as e:
            print(f"   ⏭️  Index may already exist: {e}")
        
        # Index on payments.provider_txn_id
        try:
            if db_type == 'sqlite':
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_provider_txn ON payments(provider_txn_id)")
            else:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_provider_txn ON payments(provider_txn_id)")
            print("   ✅ Created index on payments.provider_txn_id")
        except Exception as e:
            print(f"   ⏭️  Index may already exist: {e}")
        
        # Commit all changes
        conn.commit()
        
        # ============================================================
        # Summary
        # ============================================================
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 60)
        
        if changes:
            print("\n📝 Changes made:")
            for change in changes:
                print(f"   {change}")
        else:
            print("\n📝 No changes needed - database is already up to date.")
        
        print("\n🔐 Next steps:")
        print("   1. Set PLISIO_API_KEY in your .env file or environment")
        print("   2. Set PLISIO_WEBHOOK_SECRET for webhook verification")
        print("   3. Restart the application")
        print("   4. Test the /api/payment/plans endpoint")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    migrate()

