"""
=============================================================================
MIMIC/BRAIN CAPITAL - High Traffic Database Index Migration
=============================================================================
Adds performance indexes for handling millions of trade_history records.
Supports both PostgreSQL and SQLite.

Usage:
    python migrate_high_traffic_indexes.py

This script is safe to run multiple times (idempotent).
=============================================================================
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text, inspect
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HighTrafficMigration")


def detect_database_type():
    """Detect if we're using PostgreSQL or SQLite"""
    with app.app_context():
        dialect = db.engine.dialect.name
        return dialect


def get_existing_indexes(connection, table_name):
    """Get list of existing indexes for a table"""
    dialect = db.engine.dialect.name
    
    if dialect == 'postgresql':
        result = connection.execute(text("""
            SELECT indexname FROM pg_indexes WHERE tablename = :table
        """), {"table": table_name})
    else:  # SQLite
        result = connection.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name = :table
        """), {"table": table_name})
    
    return {row[0] for row in result.fetchall()}


def create_index_safely(connection, index_name, create_sql, dialect):
    """Create an index if it doesn't exist"""
    try:
        if dialect == 'postgresql':
            # PostgreSQL supports IF NOT EXISTS and CONCURRENTLY
            connection.execute(text(create_sql))
        else:
            # SQLite - use IF NOT EXISTS
            connection.execute(text(create_sql))
        logger.info(f"✅ Created index: {index_name}")
        return True
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info(f"⏭️  Index already exists: {index_name}")
            return True
        else:
            logger.warning(f"⚠️  Failed to create {index_name}: {e}")
            return False


def migrate_postgresql(connection):
    """Add indexes optimized for PostgreSQL"""
    logger.info("🐘 Running PostgreSQL-specific migration...")
    
    indexes = [
        # Trade History - Critical for Dashboard
        ("idx_trade_history_user_close_time_desc", 
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_close_time_desc ON trade_history (user_id, close_time DESC)"),
        
        ("idx_trade_history_user_symbol_time",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_symbol_time ON trade_history (user_id, symbol, close_time DESC)"),
        
        ("idx_trade_history_user_pnl",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_pnl ON trade_history (user_id, pnl) WHERE pnl IS NOT NULL"),
        
        ("idx_trade_history_close_time_pnl",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_close_time_pnl ON trade_history (close_time DESC, pnl) WHERE pnl IS NOT NULL"),
        
        ("idx_trade_history_symbol_pnl",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_symbol_pnl ON trade_history (symbol, close_time DESC, pnl)"),
        
        ("idx_trade_history_user_side_time",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_side_time ON trade_history (user_id, side, close_time DESC)"),
        
        # Balance History
        ("idx_balance_history_user_timestamp_desc",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_balance_history_user_timestamp_desc ON balance_history (user_id, timestamp DESC)"),
        
        # Users
        ("idx_users_active_subscription",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_active_subscription ON users (is_active, subscription_expires_at DESC) WHERE is_active = true"),
        
        ("idx_users_subscription_expiring",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_subscription_expiring ON users (subscription_expires_at) WHERE subscription_expires_at IS NOT NULL AND is_active = true"),
        
        # Referral Commissions
        ("idx_referral_commissions_referrer_created",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_referral_commissions_referrer_created ON referral_commissions (referrer_id, created_at DESC)"),
        
        ("idx_referral_commissions_pending",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_referral_commissions_pending ON referral_commissions (referrer_id, amount) WHERE is_paid = false"),
        
        # Payments
        ("idx_payments_user_created_desc",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_user_created_desc ON payments (user_id, created_at DESC)"),
        
        # Chat Messages
        ("idx_chat_messages_room_created_desc",
         "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_messages_room_created_desc ON chat_messages (room, created_at DESC) WHERE is_deleted = false"),
    ]
    
    success_count = 0
    for idx_name, idx_sql in indexes:
        # For CONCURRENTLY, we need autocommit mode
        try:
            connection.execution_options(isolation_level="AUTOCOMMIT")
            if create_index_safely(connection, idx_name, idx_sql, 'postgresql'):
                success_count += 1
        except Exception as e:
            logger.warning(f"⚠️  Error with {idx_name}: {e}")
    
    return success_count, len(indexes)


def migrate_sqlite(connection):
    """Add indexes optimized for SQLite"""
    logger.info("📁 Running SQLite-specific migration...")
    
    indexes = [
        # Trade History - Critical for Dashboard
        ("idx_trade_history_user_close_time_desc",
         "CREATE INDEX IF NOT EXISTS idx_trade_history_user_close_time_desc ON trade_history (user_id, close_time DESC)"),
        
        ("idx_trade_history_user_symbol_time",
         "CREATE INDEX IF NOT EXISTS idx_trade_history_user_symbol_time ON trade_history (user_id, symbol, close_time DESC)"),
        
        ("idx_trade_history_user_pnl",
         "CREATE INDEX IF NOT EXISTS idx_trade_history_user_pnl ON trade_history (user_id, pnl)"),
        
        ("idx_trade_history_close_time_pnl",
         "CREATE INDEX IF NOT EXISTS idx_trade_history_close_time_pnl ON trade_history (close_time DESC, pnl)"),
        
        ("idx_trade_history_symbol_pnl",
         "CREATE INDEX IF NOT EXISTS idx_trade_history_symbol_pnl ON trade_history (symbol, close_time, pnl)"),
        
        ("idx_trade_history_user_side_time",
         "CREATE INDEX IF NOT EXISTS idx_trade_history_user_side_time ON trade_history (user_id, side, close_time DESC)"),
        
        # Balance History
        ("idx_balance_history_user_timestamp_desc",
         "CREATE INDEX IF NOT EXISTS idx_balance_history_user_timestamp_desc ON balance_history (user_id, timestamp DESC)"),
        
        ("idx_balance_history_timestamp_user",
         "CREATE INDEX IF NOT EXISTS idx_balance_history_timestamp_user ON balance_history (timestamp DESC, user_id)"),
        
        # Users - Active with subscription
        ("idx_users_active_subscription",
         "CREATE INDEX IF NOT EXISTS idx_users_active_subscription ON users (is_active, subscription_expires_at)"),
        
        # Referral Commissions
        ("idx_referral_commissions_referrer_created",
         "CREATE INDEX IF NOT EXISTS idx_referral_commissions_referrer_created ON referral_commissions (referrer_id, created_at DESC)"),
        
        ("idx_referral_commissions_pending",
         "CREATE INDEX IF NOT EXISTS idx_referral_commissions_pending ON referral_commissions (referrer_id, is_paid, amount)"),
        
        # Payments
        ("idx_payments_user_created_desc",
         "CREATE INDEX IF NOT EXISTS idx_payments_user_created_desc ON payments (user_id, created_at DESC)"),
        
        ("idx_payments_status_created",
         "CREATE INDEX IF NOT EXISTS idx_payments_status_created ON payments (status, created_at DESC)"),
        
        # Chat Messages
        ("idx_chat_messages_room_created_desc",
         "CREATE INDEX IF NOT EXISTS idx_chat_messages_room_created_desc ON chat_messages (room, is_deleted, created_at DESC)"),
        
        ("idx_chat_messages_user_room_created",
         "CREATE INDEX IF NOT EXISTS idx_chat_messages_user_room_created ON chat_messages (user_id, room, created_at DESC)"),
    ]
    
    success_count = 0
    for idx_name, idx_sql in indexes:
        if create_index_safely(connection, idx_name, idx_sql, 'sqlite'):
            success_count += 1
    
    return success_count, len(indexes)


def run_analyze(connection, dialect):
    """Update table statistics for query optimizer"""
    logger.info("📊 Updating table statistics...")
    
    tables = ['trade_history', 'balance_history', 'users', 'referral_commissions', 
              'payments', 'chat_messages', 'push_subscriptions', 'strategy_subscriptions']
    
    if dialect == 'postgresql':
        for table in tables:
            try:
                connection.execute(text(f"ANALYZE {table}"))
                logger.info(f"   Analyzed: {table}")
            except Exception as e:
                logger.debug(f"   Skip analyze {table}: {e}")
    else:  # SQLite
        try:
            connection.execute(text("ANALYZE"))
            logger.info("   Analyzed all tables")
        except Exception as e:
            logger.debug(f"   Skip analyze: {e}")


def show_index_summary(connection, dialect):
    """Display summary of indexes"""
    logger.info("\n" + "=" * 60)
    logger.info("📋 INDEX SUMMARY")
    logger.info("=" * 60)
    
    if dialect == 'postgresql':
        result = connection.execute(text("""
            SELECT 
                tablename,
                COUNT(*) as index_count,
                pg_size_pretty(SUM(pg_relation_size(indexrelid))) as total_size
            FROM pg_stat_user_indexes
            WHERE tablename IN ('trade_history', 'balance_history', 'users', 
                               'referral_commissions', 'payments', 'chat_messages')
            GROUP BY tablename
            ORDER BY SUM(pg_relation_size(indexrelid)) DESC
        """))
        
        for row in result.fetchall():
            logger.info(f"   {row[0]}: {row[1]} indexes, {row[2]}")
    else:
        result = connection.execute(text("""
            SELECT tbl_name, COUNT(*) as cnt
            FROM sqlite_master 
            WHERE type='index' AND sql IS NOT NULL
            GROUP BY tbl_name
            ORDER BY cnt DESC
        """))
        
        for row in result.fetchall():
            logger.info(f"   {row[0]}: {row[1]} indexes")


def main():
    """Main migration function"""
    print("\n" + "=" * 60)
    print("🚀 MIMIC - High Traffic Database Index Migration")
    print("=" * 60 + "\n")
    
    dialect = detect_database_type()
    logger.info(f"🔍 Detected database: {dialect.upper()}")
    
    with app.app_context():
        connection = db.engine.connect()
        
        try:
            if dialect == 'postgresql':
                success, total = migrate_postgresql(connection)
            else:
                trans = connection.begin()
                try:
                    success, total = migrate_sqlite(connection)
                    trans.commit()
                except:
                    trans.rollback()
                    raise
            
            logger.info(f"\n✅ Created {success}/{total} indexes successfully")
            
            # Run ANALYZE
            run_analyze(connection, dialect)
            
            # Show summary
            show_index_summary(connection, dialect)
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise
        finally:
            connection.close()
    
    print("\n" + "=" * 60)
    print("✅ Migration completed!")
    print("=" * 60)
    print("""
Next steps:
1. Monitor query performance with EXPLAIN ANALYZE
2. Set up regular VACUUM ANALYZE (daily cron job)
3. Consider table partitioning for 10M+ records
4. Enable pg_stat_statements for query monitoring
""")


if __name__ == "__main__":
    main()
