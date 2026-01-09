#!/usr/bin/env python3
"""
Migration script for Influencer Dashboard tables.

Creates:
- referral_clicks: Track click statistics for referral links
- payout_requests: Handle commission payout requests

Run: python migrate_add_influencer.py
"""

import sqlite3
import os
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_db_path():
    """Get database path from config"""
    try:
        from config import Config
        db_uri = Config.SQLALCHEMY_DATABASE_URI
        if db_uri.startswith('sqlite:///'):
            return db_uri.replace('sqlite:///', '')
        elif 'postgresql' in db_uri:
            return None  # PostgreSQL
    except Exception:
        pass
    return 'trading.db'


def table_exists(cursor, table_name):
    """Check if a table exists in SQLite"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def migrate_sqlite():
    """Run migration for SQLite database"""
    db_path = get_db_path()
    if not db_path:
        logger.info("Not using SQLite, skipping SQLite migration")
        return False
    
    if not os.path.exists(db_path):
        logger.warning(f"Database file not found: {db_path}")
        return False
    
    logger.info(f"📦 Migrating SQLite database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # ==================== REFERRAL_CLICKS TABLE ====================
        logger.info("\n📋 Checking 'referral_clicks' table...")
        
        if not table_exists(cursor, 'referral_clicks'):
            logger.info("  Creating 'referral_clicks' table...")
            cursor.execute("""
                CREATE TABLE referral_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    ip_hash VARCHAR(64),
                    user_agent VARCHAR(512),
                    referer_url VARCHAR(1024),
                    utm_source VARCHAR(100),
                    utm_medium VARCHAR(100),
                    utm_campaign VARCHAR(100),
                    converted BOOLEAN DEFAULT 0,
                    converted_user_id INTEGER,
                    converted_at DATETIME,
                    deposited BOOLEAN DEFAULT 0,
                    first_deposit_amount FLOAT,
                    first_deposit_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (converted_user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            logger.info("  ✅ Created 'referral_clicks' table")
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_click_referrer_date ON referral_clicks(referrer_id, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_click_conversion ON referral_clicks(referrer_id, converted)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_click_ip_referrer ON referral_clicks(ip_hash, referrer_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_click_deposited ON referral_clicks(referrer_id, deposited)")
            logger.info("  ✅ Created indexes for 'referral_clicks'")
        else:
            logger.info("  ✓ Table 'referral_clicks' already exists")
        
        # ==================== PAYOUT_REQUESTS TABLE ====================
        logger.info("\n📋 Checking 'payout_requests' table...")
        
        if not table_exists(cursor, 'payout_requests'):
            logger.info("  Creating 'payout_requests' table...")
            cursor.execute("""
                CREATE TABLE payout_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount FLOAT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                    payment_method VARCHAR(50) NOT NULL,
                    payment_address VARCHAR(500),
                    admin_id INTEGER,
                    admin_notes TEXT,
                    txn_id VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at DATETIME,
                    paid_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            logger.info("  ✅ Created 'payout_requests' table")
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payout_user_status ON payout_requests(user_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payout_status_date ON payout_requests(status, created_at)")
            logger.info("  ✅ Created indexes for 'payout_requests'")
        else:
            logger.info("  ✓ Table 'payout_requests' already exists")
        
        conn.commit()
        logger.info("\n✅ SQLite migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def migrate_postgresql():
    """Run migration for PostgreSQL database"""
    try:
        import psycopg2
        from config import Config
        
        db_uri = Config.SQLALCHEMY_DATABASE_URI
        if 'postgresql' not in db_uri:
            logger.info("Not using PostgreSQL, skipping PostgreSQL migration")
            return False
        
        logger.info("📦 Migrating PostgreSQL database...")
        
        conn = psycopg2.connect(db_uri)
        cursor = conn.cursor()
        
        # ==================== REFERRAL_CLICKS TABLE ====================
        logger.info("\n📋 Checking 'referral_clicks' table...")
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'referral_clicks'
            )
        """)
        exists = cursor.fetchone()[0]
        
        if not exists:
            logger.info("  Creating 'referral_clicks' table...")
            cursor.execute("""
                CREATE TABLE referral_clicks (
                    id SERIAL PRIMARY KEY,
                    referrer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    ip_hash VARCHAR(64),
                    user_agent VARCHAR(512),
                    referer_url VARCHAR(1024),
                    utm_source VARCHAR(100),
                    utm_medium VARCHAR(100),
                    utm_campaign VARCHAR(100),
                    converted BOOLEAN DEFAULT FALSE,
                    converted_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    converted_at TIMESTAMP WITH TIME ZONE,
                    deposited BOOLEAN DEFAULT FALSE,
                    first_deposit_amount DOUBLE PRECISION,
                    first_deposit_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX idx_click_referrer_date ON referral_clicks(referrer_id, created_at DESC)")
            cursor.execute("CREATE INDEX idx_click_conversion ON referral_clicks(referrer_id, converted)")
            cursor.execute("CREATE INDEX idx_click_ip_referrer ON referral_clicks(ip_hash, referrer_id)")
            cursor.execute("CREATE INDEX idx_click_deposited ON referral_clicks(referrer_id, deposited)")
            logger.info("  ✅ Created 'referral_clicks' table with indexes")
        else:
            logger.info("  ✓ Table 'referral_clicks' already exists")
        
        # ==================== PAYOUT_REQUESTS TABLE ====================
        logger.info("\n📋 Checking 'payout_requests' table...")
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'payout_requests'
            )
        """)
        exists = cursor.fetchone()[0]
        
        if not exists:
            logger.info("  Creating 'payout_requests' table...")
            cursor.execute("""
                CREATE TABLE payout_requests (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    amount DOUBLE PRECISION NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                    payment_method VARCHAR(50) NOT NULL,
                    payment_address VARCHAR(500),
                    admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    admin_notes TEXT,
                    txn_id VARCHAR(200),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    reviewed_at TIMESTAMP WITH TIME ZONE,
                    paid_at TIMESTAMP WITH TIME ZONE
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX idx_payout_user_status ON payout_requests(user_id, status)")
            cursor.execute("CREATE INDEX idx_payout_status_date ON payout_requests(status, created_at)")
            logger.info("  ✅ Created 'payout_requests' table with indexes")
        else:
            logger.info("  ✓ Table 'payout_requests' already exists")
        
        conn.commit()
        logger.info("\n✅ PostgreSQL migration completed successfully!")
        return True
        
    except ImportError:
        logger.info("psycopg2 not installed, skipping PostgreSQL migration")
        return False
    except Exception as e:
        logger.error(f"❌ PostgreSQL migration error: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def main():
    """Run migrations"""
    print("""
╔════════════════════════════════════════════════════════════╗
║    MIMIC - Influencer Dashboard Migration                  ║
║    Creates: referral_clicks, payout_requests tables        ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # Try PostgreSQL first, then SQLite
    pg_result = migrate_postgresql()
    sqlite_result = migrate_sqlite()
    
    if pg_result or sqlite_result:
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print("\nNew tables created:")
        print("  • referral_clicks - Track click statistics for partners")
        print("  • payout_requests - Commission payout request system")
        print("\nYou can now access the Influencer Dashboard at /influencer")
        return 0
    else:
        print("\n❌ No migration was performed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
