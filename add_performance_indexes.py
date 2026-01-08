"""
Database Migration Script - Add Performance Indexes
Adds indexes to improve query performance for Brain Capital platform

Run this script to add indexes to your existing database:
python add_performance_indexes.py
"""

from app import app, db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Migration")


def add_indexes():
    """Add performance indexes to existing database tables"""
    
    with app.app_context():
        connection = db.engine.connect()
        trans = connection.begin()
        
        try:
            logger.info("🔧 Starting database index migration...")
            
            # Users table indexes
            indexes = [
                # Users table
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
                "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_users_is_paused ON users(is_paused)",
                "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
                "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_user_active_role ON users(is_active, role)",
                "CREATE INDEX IF NOT EXISTS idx_user_status ON users(is_active, is_paused)",
                
                # TradeHistory table
                "CREATE INDEX IF NOT EXISTS idx_trade_history_user_id ON trade_history(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_trade_history_close_time ON trade_history(close_time)",
                "CREATE INDEX IF NOT EXISTS idx_trade_user_time ON trade_history(user_id, close_time)",
                "CREATE INDEX IF NOT EXISTS idx_trade_symbol_time ON trade_history(symbol, close_time)",
                
                # BalanceHistory table
                "CREATE INDEX IF NOT EXISTS idx_balance_history_user_id ON balance_history(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_balance_history_timestamp ON balance_history(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_balance_user_time ON balance_history(user_id, timestamp)",
                
                # Messages table
                "CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id)",
                "CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON messages(recipient_id)",
                "CREATE INDEX IF NOT EXISTS idx_messages_is_read ON messages(is_read)",
                "CREATE INDEX IF NOT EXISTS idx_messages_is_from_admin ON messages(is_from_admin)",
                "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_message_recipient_read ON messages(recipient_id, is_read)",
                "CREATE INDEX IF NOT EXISTS idx_message_sender_time ON messages(sender_id, created_at)",
                
                # PasswordResetToken table
                "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token)",
                "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_is_used ON password_reset_tokens(is_used)",
                "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_token_user_used ON password_reset_tokens(user_id, is_used)",
                "CREATE INDEX IF NOT EXISTS idx_token_expires ON password_reset_tokens(expires_at, is_used)",
                
                # ExchangeConfig table
                "CREATE INDEX IF NOT EXISTS idx_exchange_configs_exchange_name ON exchange_configs(exchange_name)",
                "CREATE INDEX IF NOT EXISTS idx_exchange_configs_is_enabled ON exchange_configs(is_enabled)",
                "CREATE INDEX IF NOT EXISTS idx_exchange_configs_is_verified ON exchange_configs(is_verified)",
                "CREATE INDEX IF NOT EXISTS idx_exchange_enabled_verified ON exchange_configs(is_enabled, is_verified)",
                
                # UserExchange table
                "CREATE INDEX IF NOT EXISTS idx_user_exchanges_user_id ON user_exchanges(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_user_exchanges_exchange_name ON user_exchanges(exchange_name)",
                "CREATE INDEX IF NOT EXISTS idx_user_exchanges_status ON user_exchanges(status)",
                "CREATE INDEX IF NOT EXISTS idx_user_exchanges_is_active ON user_exchanges(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_user_exchanges_trading_enabled ON user_exchanges(trading_enabled)",
                "CREATE INDEX IF NOT EXISTS idx_user_exchange_status ON user_exchanges(user_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_user_exchange_active ON user_exchanges(user_id, is_active, trading_enabled)",
            ]
            
            for idx_sql in indexes:
                try:
                    connection.execute(text(idx_sql))
                    idx_name = idx_sql.split("INDEX IF NOT EXISTS ")[1].split(" ON ")[0]
                    logger.info(f"✅ Created index: {idx_name}")
                except Exception as e:
                    logger.warning(f"⚠️ Index creation warning: {e}")
                    # Continue with other indexes even if one fails
            
            trans.commit()
            logger.info("✅ Database index migration completed successfully!")
            logger.info("📊 Performance improvement: Queries should be significantly faster now.")
            
            # Show some statistics
            show_index_stats(connection)
            
        except Exception as e:
            trans.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise
        finally:
            connection.close()


def show_index_stats(connection):
    """Show index statistics"""
    try:
        # For SQLite
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"))
        indexes = result.fetchall()
        logger.info(f"📊 Total indexes in database: {len(indexes)}")
        
    except Exception as e:
        logger.debug(f"Could not fetch index stats: {e}")


def cleanup_old_data():
    """Optional: Clean up old data to improve performance"""
    with app.app_context():
        try:
            # Clean up expired password reset tokens (older than 24 hours)
            from models import PasswordResetToken
            from datetime import datetime, timezone, timedelta
            
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            deleted = PasswordResetToken.query.filter(
                PasswordResetToken.expires_at < cutoff
            ).delete()
            db.session.commit()
            
            if deleted > 0:
                logger.info(f"🧹 Cleaned up {deleted} expired password reset tokens")
                
        except Exception as e:
            logger.warning(f"⚠️ Cleanup warning: {e}")
            db.session.rollback()


def optimize_database():
    """Run database optimization commands"""
    with app.app_context():
        connection = db.engine.connect()
        try:
            # For SQLite - run VACUUM and ANALYZE
            logger.info("🔧 Running database optimization...")
            connection.execute(text("VACUUM"))
            connection.execute(text("ANALYZE"))
            logger.info("✅ Database optimization completed")
            
        except Exception as e:
            logger.warning(f"⚠️ Optimization warning: {e}")
        finally:
            connection.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Brain Capital - Database Performance Migration")
    print("=" * 60)
    print()
    
    # Add indexes
    add_indexes()
    
    # Optional cleanup
    response = input("\n🧹 Do you want to clean up old data? (y/N): ")
    if response.lower() == 'y':
        cleanup_old_data()
    
    # Optional optimization
    response = input("\n🔧 Do you want to optimize database? (y/N): ")
    if response.lower() == 'y':
        optimize_database()
    
    print()
    print("=" * 60)
    print("✅ Migration completed!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Restart your application")
    print("2. Monitor query performance")
    print("3. Check logs for any issues")
    print()

