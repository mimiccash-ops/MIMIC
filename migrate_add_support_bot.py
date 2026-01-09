#!/usr/bin/env python3
"""
Migration: Add Support Bot Tables (pgvector)

This migration:
1. Enables the pgvector extension (PostgreSQL only)
2. Creates document_chunks table for storing embedded documentation
3. Creates support_tickets table for low-confidence queries
4. Creates support_conversations table for chat history

Run: python migrate_add_support_bot.py
"""

import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """Run the support bot migration"""
    
    # Import Flask app context
    try:
        from app import app, db
        from sqlalchemy import text, inspect
        from config import Config
    except ImportError as e:
        logger.error(f"Failed to import app: {e}")
        logger.info("Make sure you're running from the project root directory")
        sys.exit(1)
    
    with app.app_context():
        # Check if using PostgreSQL (required for pgvector)
        is_postgres = 'postgresql' in Config.SQLALCHEMY_DATABASE_URI
        
        if is_postgres:
            logger.info("🐘 PostgreSQL detected - enabling pgvector extension...")
            try:
                # Enable pgvector extension
                db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                db.session.commit()
                logger.info("✅ pgvector extension enabled")
            except Exception as e:
                logger.warning(f"⚠️ Could not enable pgvector: {e}")
                logger.info("Make sure pgvector is installed: https://github.com/pgvector/pgvector")
                db.session.rollback()
        else:
            logger.warning("⚠️ SQLite detected - pgvector requires PostgreSQL")
            logger.info("For production, please use PostgreSQL with pgvector extension")
            logger.info("Continuing with SQLite-compatible schema (embeddings as JSON)...")
        
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        # Create document_chunks table
        if 'document_chunks' not in existing_tables:
            logger.info("📄 Creating document_chunks table...")
            
            if is_postgres:
                # PostgreSQL with pgvector
                db.session.execute(text("""
                    CREATE TABLE document_chunks (
                        id SERIAL PRIMARY KEY,
                        source_file VARCHAR(200) NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        embedding vector(1536),
                        metadata JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """))
                
                # Create indexes for efficient search
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_source 
                    ON document_chunks (source_file);
                """))
                
                # Create vector similarity index (IVFFlat for faster search)
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
                    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                """))
            else:
                # SQLite fallback (store embeddings as JSON text)
                db.session.execute(text("""
                    CREATE TABLE document_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_file VARCHAR(200) NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        embedding TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_source 
                    ON document_chunks (source_file);
                """))
            
            db.session.commit()
            logger.info("✅ document_chunks table created")
        else:
            logger.info("ℹ️ document_chunks table already exists")
        
        # Create support_conversations table
        if 'support_conversations' not in existing_tables:
            logger.info("💬 Creating support_conversations table...")
            
            if is_postgres:
                db.session.execute(text("""
                    CREATE TABLE support_conversations (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(100) UNIQUE NOT NULL,
                        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        telegram_chat_id VARCHAR(50),
                        channel VARCHAR(20) DEFAULT 'web',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        is_resolved BOOLEAN DEFAULT FALSE
                    );
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_support_conv_session 
                    ON support_conversations (session_id);
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_support_conv_user 
                    ON support_conversations (user_id);
                """))
            else:
                db.session.execute(text("""
                    CREATE TABLE support_conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id VARCHAR(100) UNIQUE NOT NULL,
                        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        telegram_chat_id VARCHAR(50),
                        channel VARCHAR(20) DEFAULT 'web',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_resolved BOOLEAN DEFAULT 0
                    );
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_support_conv_session 
                    ON support_conversations (session_id);
                """))
            
            db.session.commit()
            logger.info("✅ support_conversations table created")
        else:
            logger.info("ℹ️ support_conversations table already exists")
        
        # Create support_messages table (conversation history)
        if 'support_messages' not in existing_tables:
            logger.info("📝 Creating support_messages table...")
            
            if is_postgres:
                db.session.execute(text("""
                    CREATE TABLE support_messages (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER REFERENCES support_conversations(id) ON DELETE CASCADE,
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        confidence FLOAT,
                        sources JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_support_msg_conv 
                    ON support_messages (conversation_id, created_at);
                """))
            else:
                db.session.execute(text("""
                    CREATE TABLE support_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id INTEGER REFERENCES support_conversations(id) ON DELETE CASCADE,
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        confidence FLOAT,
                        sources TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_support_msg_conv 
                    ON support_messages (conversation_id, created_at);
                """))
            
            db.session.commit()
            logger.info("✅ support_messages table created")
        else:
            logger.info("ℹ️ support_messages table already exists")
        
        # Create support_tickets table
        if 'support_tickets' not in existing_tables:
            logger.info("🎫 Creating support_tickets table...")
            
            if is_postgres:
                db.session.execute(text("""
                    CREATE TABLE support_tickets (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER REFERENCES support_conversations(id) ON DELETE SET NULL,
                        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        question TEXT NOT NULL,
                        ai_response TEXT,
                        confidence FLOAT,
                        status VARCHAR(20) DEFAULT 'open',
                        priority VARCHAR(20) DEFAULT 'normal',
                        assigned_to_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        admin_response TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        resolved_at TIMESTAMP WITH TIME ZONE
                    );
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_status 
                    ON support_tickets (status, created_at);
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_user 
                    ON support_tickets (user_id);
                """))
            else:
                db.session.execute(text("""
                    CREATE TABLE support_tickets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id INTEGER REFERENCES support_conversations(id) ON DELETE SET NULL,
                        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        question TEXT NOT NULL,
                        ai_response TEXT,
                        confidence FLOAT,
                        status VARCHAR(20) DEFAULT 'open',
                        priority VARCHAR(20) DEFAULT 'normal',
                        assigned_to_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        admin_response TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP
                    );
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_support_tickets_status 
                    ON support_tickets (status, created_at);
                """))
            
            db.session.commit()
            logger.info("✅ support_tickets table created")
        else:
            logger.info("ℹ️ support_tickets table already exists")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("🎉 Support Bot migration completed successfully!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Set OPENAI_API_KEY in your .env file")
        logger.info("2. Run: python ingest_docs.py  (to embed documentation)")
        logger.info("3. The /api/support/chat endpoint will be available")
        logger.info("")


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║          MIMIC - Support Bot Migration                       ║
║          pgvector + Document Chunks + Tickets                ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    run_migration()
