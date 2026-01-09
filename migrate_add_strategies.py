"""
Database Migration: Add Multi-Strategy System Tables

This script adds the multi-strategy system to the database:
1. Creates strategies table
2. Creates strategy_subscriptions table
3. Creates default "Main" strategy
4. Migrates existing active users to subscribe to default strategy with 100% allocation

Usage:
    python migrate_add_strategies.py

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


def migrate():
    """Run the migration"""
    print("=" * 60)
    print("🔄 MULTI-STRATEGY SYSTEM MIGRATION")
    print("=" * 60)
    
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    print(f"\n📊 Database type: {db_type.upper()}")
    
    # Track changes
    changes = []
    
    try:
        # ============================================================
        # 1. Create strategies table
        # ============================================================
        print("\n📋 Step 1: Creating strategies table...")
        
        if not table_exists(cursor, 'strategies', db_type):
            if db_type == 'sqlite':
                cursor.execute("""
                    CREATE TABLE strategies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        description TEXT,
                        risk_level VARCHAR(20) DEFAULT 'medium',
                        master_exchange_id INTEGER REFERENCES exchange_configs(id) ON DELETE SET NULL,
                        default_risk_perc FLOAT,
                        default_leverage INTEGER,
                        max_positions INTEGER,
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_is_active ON strategies(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_risk_level ON strategies(risk_level)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_master_exchange ON strategies(master_exchange_id)")
            else:
                cursor.execute("""
                    CREATE TABLE strategies (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        description TEXT,
                        risk_level VARCHAR(20) DEFAULT 'medium',
                        master_exchange_id INTEGER REFERENCES exchange_configs(id) ON DELETE SET NULL,
                        default_risk_perc FLOAT,
                        default_leverage INTEGER,
                        max_positions INTEGER,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_is_active ON strategies(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_risk_level ON strategies(risk_level)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_master_exchange ON strategies(master_exchange_id)")
            
            changes.append("✅ Created table: strategies")
            print("   ✅ Created strategies table")
        else:
            print("   ⏭️  strategies table already exists")
        
        # ============================================================
        # 2. Create strategy_subscriptions table
        # ============================================================
        print("\n📋 Step 2: Creating strategy_subscriptions table...")
        
        if not table_exists(cursor, 'strategy_subscriptions', db_type):
            if db_type == 'sqlite':
                cursor.execute("""
                    CREATE TABLE strategy_subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
                        allocation_percent FLOAT DEFAULT 100.0,
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, strategy_id)
                    )
                """)
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON strategy_subscriptions(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_strategy_id ON strategy_subscriptions(strategy_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_is_active ON strategy_subscriptions(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_active ON strategy_subscriptions(user_id, is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_strategy_active ON strategy_subscriptions(strategy_id, is_active)")
            else:
                cursor.execute("""
                    CREATE TABLE strategy_subscriptions (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
                        allocation_percent FLOAT DEFAULT 100.0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, strategy_id)
                    )
                """)
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON strategy_subscriptions(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_strategy_id ON strategy_subscriptions(strategy_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_is_active ON strategy_subscriptions(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_active ON strategy_subscriptions(user_id, is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_strategy_active ON strategy_subscriptions(strategy_id, is_active)")
            
            changes.append("✅ Created table: strategy_subscriptions")
            print("   ✅ Created strategy_subscriptions table")
        else:
            print("   ⏭️  strategy_subscriptions table already exists")
        
        # ============================================================
        # 3. Create default "Main" strategy
        # ============================================================
        print("\n📋 Step 3: Creating default 'Main' strategy...")
        
        # Check if default strategy exists
        if db_type == 'sqlite':
            cursor.execute("SELECT id FROM strategies WHERE name = ?", ('Main',))
        else:
            cursor.execute("SELECT id FROM strategies WHERE name = %s", ('Main',))
        
        existing_strategy = cursor.fetchone()
        
        if not existing_strategy:
            # Get the first enabled exchange config as the master (if any)
            if db_type == 'sqlite':
                cursor.execute("SELECT id FROM exchange_configs WHERE is_enabled = 1 AND is_verified = 1 ORDER BY id ASC LIMIT 1")
            else:
                cursor.execute("SELECT id FROM exchange_configs WHERE is_enabled = TRUE AND is_verified = TRUE ORDER BY id ASC LIMIT 1")
            
            master_exchange = cursor.fetchone()
            master_exchange_id = master_exchange[0] if master_exchange else None
            
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            
            if db_type == 'sqlite':
                cursor.execute("""
                    INSERT INTO strategies (name, description, risk_level, master_exchange_id, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, ('Main', 'Default trading strategy - follows the main master account', 'medium', master_exchange_id, now, now))
            else:
                cursor.execute("""
                    INSERT INTO strategies (name, description, risk_level, master_exchange_id, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, TRUE, %s, %s)
                """, ('Main', 'Default trading strategy - follows the main master account', 'medium', master_exchange_id, now, now))
            
            changes.append("✅ Created default strategy: Main")
            print("   ✅ Created default 'Main' strategy")
            
            if master_exchange_id:
                print(f"   📌 Linked to master exchange ID: {master_exchange_id}")
            else:
                print("   ⚠️  No verified master exchange found - strategy created without master link")
        else:
            print("   ⏭️  Default 'Main' strategy already exists")
        
        # ============================================================
        # 4. Migrate existing active users to default strategy
        # ============================================================
        print("\n📋 Step 4: Migrating existing users to default strategy...")
        
        # Get default strategy ID
        if db_type == 'sqlite':
            cursor.execute("SELECT id FROM strategies WHERE name = ?", ('Main',))
        else:
            cursor.execute("SELECT id FROM strategies WHERE name = %s", ('Main',))
        
        strategy_row = cursor.fetchone()
        if not strategy_row:
            print("   ⚠️  Could not find default strategy - skipping user migration")
        else:
            default_strategy_id = strategy_row[0]
            
            # Get all active users who don't have a subscription yet
            if db_type == 'sqlite':
                cursor.execute("""
                    SELECT u.id FROM users u
                    WHERE u.is_active = 1
                    AND u.role = 'user'
                    AND NOT EXISTS (
                        SELECT 1 FROM strategy_subscriptions ss 
                        WHERE ss.user_id = u.id AND ss.strategy_id = ?
                    )
                """, (default_strategy_id,))
            else:
                cursor.execute("""
                    SELECT u.id FROM users u
                    WHERE u.is_active = TRUE
                    AND u.role = 'user'
                    AND NOT EXISTS (
                        SELECT 1 FROM strategy_subscriptions ss 
                        WHERE ss.user_id = u.id AND ss.strategy_id = %s
                    )
                """, (default_strategy_id,))
            
            users_to_migrate = cursor.fetchall()
            
            if users_to_migrate:
                now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                migrated_count = 0
                
                for (user_id,) in users_to_migrate:
                    try:
                        if db_type == 'sqlite':
                            cursor.execute("""
                                INSERT INTO strategy_subscriptions 
                                (user_id, strategy_id, allocation_percent, is_active, created_at, updated_at)
                                VALUES (?, ?, 100.0, 1, ?, ?)
                            """, (user_id, default_strategy_id, now, now))
                        else:
                            cursor.execute("""
                                INSERT INTO strategy_subscriptions 
                                (user_id, strategy_id, allocation_percent, is_active, created_at, updated_at)
                                VALUES (%s, %s, 100.0, TRUE, %s, %s)
                            """, (user_id, default_strategy_id, now, now))
                        migrated_count += 1
                    except Exception as e:
                        print(f"   ⚠️  Failed to migrate user {user_id}: {e}")
                
                changes.append(f"✅ Migrated {migrated_count} users to default strategy")
                print(f"   ✅ Migrated {migrated_count} active users to default strategy with 100% allocation")
            else:
                print("   ⏭️  No users need migration (all already subscribed or no active users)")
        
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
        
        print("\n🔧 Next steps:")
        print("   1. Restart the application")
        print("   2. Create additional strategies via Admin Dashboard")
        print("   3. Update TradingView webhooks to include strategy_id parameter")
        print("   4. Users can subscribe to strategies via their dashboard")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    migrate()
