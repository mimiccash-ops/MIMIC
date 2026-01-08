"""
Database Migration Script - Add Missing Columns
Adds new columns to existing database tables that may be missing after code updates

Run this script to update your existing database:
    python migrate_add_columns.py
"""

import os
import sys
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Migration")


def get_db_path():
    """Get the SQLite database path"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, 'brain_capital.db')


def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_column_if_not_exists(cursor, table_name, column_name, column_type, default_value=None):
    """Add a column to a table if it doesn't already exist"""
    if column_exists(cursor, table_name, column_name):
        logger.info(f"  ✓ Column {table_name}.{column_name} already exists")
        return False
    
    try:
        if default_value is not None:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
        else:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        
        cursor.execute(sql)
        logger.info(f"  ✅ Added column {table_name}.{column_name} ({column_type})")
        return True
    except sqlite3.OperationalError as e:
        logger.error(f"  ❌ Failed to add {table_name}.{column_name}: {e}")
        return False


def migrate_database():
    """Add all missing columns to the database"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        logger.error(f"❌ Database not found: {db_path}")
        logger.info("Run the application first to create the database, or this script if starting fresh.")
        return False
    
    logger.info(f"📦 Database: {db_path}")
    logger.info("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        changes_made = 0
        
        # ==================== USERS TABLE ====================
        logger.info("\n📋 Checking 'users' table...")
        
        user_columns = [
            ("risk_multiplier", "REAL", "1.0"),
            ("referral_code", "VARCHAR(20)", "NULL"),
            ("referred_by_id", "INTEGER", "NULL"),
            ("target_balance", "REAL", "1000.0"),
            ("telegram_enabled", "BOOLEAN", "0"),
            ("avatar", "VARCHAR(100)", "'🧑‍💻'"),
            ("avatar_type", "VARCHAR(20)", "'emoji'"),
        ]
        
        for col_name, col_type, default in user_columns:
            if add_column_if_not_exists(cursor, "users", col_name, col_type, default):
                changes_made += 1
        
        # ==================== TRADE_HISTORY TABLE ====================
        logger.info("\n📋 Checking 'trade_history' table...")
        
        trade_columns = [
            ("node_name", "VARCHAR(50)", "NULL"),
        ]
        
        for col_name, col_type, default in trade_columns:
            if add_column_if_not_exists(cursor, "trade_history", col_name, col_type, default):
                changes_made += 1
        
        # ==================== MESSAGES TABLE ====================
        logger.info("\n📋 Checking 'messages' table...")
        
        # Check if messages table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cursor.fetchone():
            logger.info("  Creating 'messages' table...")
            cursor.execute("""
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY,
                    sender_id INTEGER NOT NULL,
                    recipient_id INTEGER,
                    subject VARCHAR(200) DEFAULT '',
                    content TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT 0,
                    is_from_admin BOOLEAN DEFAULT 0,
                    parent_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (parent_id) REFERENCES messages(id) ON DELETE CASCADE
                )
            """)
            logger.info("  ✅ Created 'messages' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'messages' exists")
        
        # ==================== PASSWORD_RESET_TOKENS TABLE ====================
        logger.info("\n📋 Checking 'password_reset_tokens' table...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='password_reset_tokens'")
        if not cursor.fetchone():
            logger.info("  Creating 'password_reset_tokens' table...")
            cursor.execute("""
                CREATE TABLE password_reset_tokens (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token VARCHAR(100) UNIQUE NOT NULL,
                    code VARCHAR(6) NOT NULL,
                    method VARCHAR(20) NOT NULL,
                    is_used BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            logger.info("  ✅ Created 'password_reset_tokens' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'password_reset_tokens' exists")
        
        # ==================== EXCHANGE_CONFIGS TABLE ====================
        logger.info("\n📋 Checking 'exchange_configs' table...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='exchange_configs'")
        if not cursor.fetchone():
            logger.info("  Creating 'exchange_configs' table...")
            cursor.execute("""
                CREATE TABLE exchange_configs (
                    id INTEGER PRIMARY KEY,
                    exchange_name VARCHAR(50) UNIQUE NOT NULL,
                    display_name VARCHAR(100) NOT NULL,
                    is_enabled BOOLEAN DEFAULT 0,
                    requires_passphrase BOOLEAN DEFAULT 0,
                    description TEXT,
                    admin_api_key VARCHAR(500),
                    admin_api_secret VARCHAR(500),
                    admin_passphrase VARCHAR(500),
                    is_verified BOOLEAN DEFAULT 0,
                    verified_at DATETIME,
                    verification_error TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("  ✅ Created 'exchange_configs' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'exchange_configs' exists")
        
        # ==================== USER_EXCHANGES TABLE ====================
        logger.info("\n📋 Checking 'user_exchanges' table...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_exchanges'")
        if not cursor.fetchone():
            logger.info("  Creating 'user_exchanges' table...")
            cursor.execute("""
                CREATE TABLE user_exchanges (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    exchange_name VARCHAR(50) NOT NULL,
                    label VARCHAR(100) NOT NULL,
                    api_key VARCHAR(500) NOT NULL,
                    api_secret VARCHAR(500) NOT NULL,
                    passphrase VARCHAR(500),
                    status VARCHAR(20) DEFAULT 'PENDING',
                    is_active BOOLEAN DEFAULT 0,
                    trading_enabled BOOLEAN DEFAULT 0,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            logger.info("  ✅ Created 'user_exchanges' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'user_exchanges' exists")
            # Check for trading_enabled column
            if add_column_if_not_exists(cursor, "user_exchanges", "trading_enabled", "BOOLEAN", "0"):
                changes_made += 1
        
        # ==================== REFERRAL_COMMISSIONS TABLE ====================
        logger.info("\n📋 Checking 'referral_commissions' table...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='referral_commissions'")
        if not cursor.fetchone():
            logger.info("  Creating 'referral_commissions' table...")
            cursor.execute("""
                CREATE TABLE referral_commissions (
                    id INTEGER PRIMARY KEY,
                    referrer_id INTEGER NOT NULL,
                    referred_user_id INTEGER NOT NULL,
                    trade_id INTEGER,
                    commission_type VARCHAR(20) NOT NULL,
                    source_amount REAL DEFAULT 0.0,
                    commission_rate REAL DEFAULT 0.05,
                    amount REAL DEFAULT 0.0,
                    is_paid BOOLEAN DEFAULT 0,
                    paid_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (referred_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (trade_id) REFERENCES trade_history(id) ON DELETE SET NULL
                )
            """)
            logger.info("  ✅ Created 'referral_commissions' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'referral_commissions' exists")
        
        # Commit all changes
        conn.commit()
        
        logger.info("\n" + "=" * 60)
        if changes_made > 0:
            logger.info(f"✅ Migration complete! {changes_made} changes made.")
        else:
            logger.info("✅ Database is up to date. No changes needed.")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()


def create_indexes():
    """Create performance indexes after migration"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        return
    
    logger.info("\n📊 Creating performance indexes...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)",
        "CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_user ON user_exchanges(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_status ON user_exchanges(status)",
    ]
    
    try:
        for idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
            except sqlite3.OperationalError:
                pass  # Index might already exist or table doesn't exist
        
        conn.commit()
        logger.info("✅ Indexes created/verified")
    except Exception as e:
        logger.warning(f"⚠️ Some indexes may not have been created: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("  MIMIC (Brain Capital) - Database Migration")
    print("=" * 60)
    print()
    
    success = migrate_database()
    
    if success:
        create_indexes()
        print()
        print("=" * 60)
        print("✅ You can now run the application: python app.py")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ Migration failed. Please check the errors above.")
        print("=" * 60)
        sys.exit(1)

