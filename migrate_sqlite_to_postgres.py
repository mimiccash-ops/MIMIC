"""
Brain Capital - SQLite to PostgreSQL Migration Script

This script migrates all data from the local SQLite database (brain_capital.db)
to the PostgreSQL database configured via DATABASE_URL environment variable.

Usage:
    1. Direct: python migrate_sqlite_to_postgres.py
    2. Docker: docker-compose --profile migration up migrate

IMPORTANT: 
    - Backup your data before running this migration
    - This script will NOT delete existing PostgreSQL data - it appends/updates
    - Run this only once after setting up the PostgreSQL database
"""

import os
import sys
import logging
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Migration")

# SQLAlchemy imports
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import IntegrityError

def get_sqlite_url():
    """Get SQLite database URL"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sqlite_path = os.path.join(base_dir, 'brain_capital.db')
    
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite database not found: {sqlite_path}")
        return None
    
    return f'sqlite:///{sqlite_path}'

def get_postgres_url():
    """Get PostgreSQL database URL from environment"""
    postgres_url = os.environ.get('DATABASE_URL')
    
    if not postgres_url:
        logger.error("DATABASE_URL environment variable not set!")
        logger.info("Example: DATABASE_URL=postgresql://user:password@localhost:5432/brain_capital")
        return None
    
    # Handle Heroku-style postgres:// URLs
    if postgres_url.startswith('postgres://'):
        postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)
    
    return postgres_url

def migrate_table(sqlite_session, postgres_session, model_class, batch_size=100):
    """
    Migrate a single table from SQLite to PostgreSQL
    
    Args:
        sqlite_session: SQLAlchemy session for SQLite
        postgres_session: SQLAlchemy session for PostgreSQL
        model_class: SQLAlchemy model class to migrate
        batch_size: Number of records to process at once
    """
    table_name = model_class.__tablename__
    logger.info(f"📦 Migrating table: {table_name}")
    
    try:
        # Count records in SQLite
        total_records = sqlite_session.query(model_class).count()
        logger.info(f"   Found {total_records} records in SQLite")
        
        if total_records == 0:
            logger.info(f"   ✓ No records to migrate for {table_name}")
            return 0
        
        # Migrate in batches
        migrated = 0
        skipped = 0
        offset = 0
        
        while offset < total_records:
            # Fetch batch from SQLite
            records = sqlite_session.query(model_class).offset(offset).limit(batch_size).all()
            
            for record in records:
                try:
                    # Get all column values from the SQLite record
                    mapper = inspect(model_class)
                    data = {}
                    
                    for column in mapper.columns:
                        value = getattr(record, column.key)
                        data[column.key] = value
                    
                    # Check if record already exists in PostgreSQL (by primary key)
                    pk_columns = [col.key for col in mapper.primary_key]
                    pk_values = {col: data[col] for col in pk_columns}
                    
                    existing = postgres_session.query(model_class).filter_by(**pk_values).first()
                    
                    if existing:
                        # Skip existing records (or update if needed)
                        skipped += 1
                        continue
                    
                    # Create new record in PostgreSQL
                    new_record = model_class(**data)
                    postgres_session.add(new_record)
                    migrated += 1
                    
                except IntegrityError as e:
                    postgres_session.rollback()
                    logger.warning(f"   ⚠ Skipping duplicate record in {table_name}: {e}")
                    skipped += 1
                except Exception as e:
                    postgres_session.rollback()
                    logger.error(f"   ✗ Error migrating record in {table_name}: {e}")
                    raise
            
            # Commit batch
            postgres_session.commit()
            offset += batch_size
            
            # Progress update
            progress = min(offset, total_records)
            logger.info(f"   Progress: {progress}/{total_records} processed")
        
        logger.info(f"   ✓ Migrated: {migrated}, Skipped: {skipped}")
        return migrated
        
    except Exception as e:
        postgres_session.rollback()
        logger.error(f"   ✗ Failed to migrate {table_name}: {e}")
        raise

def reset_sequences(postgres_engine, model_class):
    """
    Reset PostgreSQL sequences after data migration
    This ensures auto-increment IDs continue from the highest existing value
    """
    table_name = model_class.__tablename__
    
    try:
        with postgres_engine.connect() as conn:
            # Get the primary key column (assuming it's 'id')
            mapper = inspect(model_class)
            pk_columns = [col.key for col in mapper.primary_key]
            
            if 'id' in pk_columns:
                # Get max ID
                result = conn.execute(text(f"SELECT MAX(id) FROM {table_name}"))
                max_id = result.scalar() or 0
                
                # Reset sequence
                sequence_name = f"{table_name}_id_seq"
                conn.execute(text(f"SELECT setval('{sequence_name}', {max_id + 1}, false)"))
                conn.commit()
                logger.info(f"   ✓ Reset sequence {sequence_name} to {max_id + 1}")
                
    except Exception as e:
        logger.warning(f"   ⚠ Could not reset sequence for {table_name}: {e}")

def main():
    """Main migration function"""
    logger.info("=" * 60)
    logger.info("🚀 Brain Capital: SQLite to PostgreSQL Migration")
    logger.info("=" * 60)
    
    # Get database URLs
    sqlite_url = get_sqlite_url()
    postgres_url = get_postgres_url()
    
    if not sqlite_url or not postgres_url:
        logger.error("❌ Migration aborted: Missing database configuration")
        sys.exit(1)
    
    logger.info(f"📂 Source: SQLite ({sqlite_url})")
    logger.info(f"🐘 Target: PostgreSQL ({postgres_url.split('@')[1] if '@' in postgres_url else postgres_url})")
    
    # Create engines
    sqlite_engine = create_engine(
        sqlite_url,
        connect_args={'check_same_thread': False}
    )
    
    postgres_engine = create_engine(
        postgres_url,
        pool_size=5,
        pool_pre_ping=True
    )
    
    # Create sessions
    SQLiteSession = scoped_session(sessionmaker(bind=sqlite_engine))
    PostgresSession = scoped_session(sessionmaker(bind=postgres_engine))
    
    sqlite_session = SQLiteSession()
    postgres_session = PostgresSession()
    
    try:
        # Import models (after setting up mock config if needed)
        logger.info("\n📋 Loading models...")
        
        # We need to import models carefully since they depend on Config
        from models import db, User, TradeHistory, BalanceHistory, Message, PasswordResetToken, ExchangeConfig, UserExchange
        
        # Create all tables in PostgreSQL
        logger.info("🏗️  Creating tables in PostgreSQL...")
        
        # Bind the Flask-SQLAlchemy db to our postgres engine temporarily
        from flask import Flask
        temp_app = Flask(__name__)
        temp_app.config['SQLALCHEMY_DATABASE_URI'] = postgres_url
        temp_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with temp_app.app_context():
            db.init_app(temp_app)
            db.create_all()
        
        logger.info("   ✓ Tables created successfully")
        
        # Define migration order (respecting foreign key constraints)
        # Tables with no dependencies first, then tables that depend on them
        migration_order = [
            User,               # No dependencies
            ExchangeConfig,     # No dependencies
            TradeHistory,       # Depends on User
            BalanceHistory,     # Depends on User
            Message,            # Depends on User
            PasswordResetToken, # Depends on User
            UserExchange,       # Depends on User
        ]
        
        # Migrate each table
        logger.info("\n📤 Starting data migration...")
        total_migrated = 0
        
        for model_class in migration_order:
            try:
                count = migrate_table(sqlite_session, postgres_session, model_class)
                total_migrated += count
            except Exception as e:
                logger.error(f"❌ Migration failed for {model_class.__tablename__}: {e}")
                raise
        
        # Reset PostgreSQL sequences
        logger.info("\n🔢 Resetting PostgreSQL sequences...")
        for model_class in migration_order:
            reset_sequences(postgres_engine, model_class)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info(f"   Total records migrated: {total_migrated}")
        logger.info("=" * 60)
        
        # Verification
        logger.info("\n📊 Verification (PostgreSQL record counts):")
        for model_class in migration_order:
            count = postgres_session.query(model_class).count()
            logger.info(f"   {model_class.__tablename__}: {count} records")
        
    except Exception as e:
        logger.error(f"\n❌ MIGRATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        # Cleanup
        sqlite_session.close()
        postgres_session.close()
        SQLiteSession.remove()
        PostgresSession.remove()
        sqlite_engine.dispose()
        postgres_engine.dispose()

if __name__ == '__main__':
    main()

