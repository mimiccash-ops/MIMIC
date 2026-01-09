#!/usr/bin/env python3
"""
Migration script to add Live Chat tables (ChatMessage, ChatBan)

This script creates the tables for the live chat feature including:
- chat_messages: Stores all chat messages
- chat_bans: Tracks muted and banned users

Usage:
    python migrate_add_chat.py
"""

import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from models import db, ChatMessage, ChatBan, User
from config import Config

def run_migration():
    """Run the chat tables migration"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    
    with app.app_context():
        print("=" * 60)
        print("🗨️  MIMIC Live Chat Migration")
        print("=" * 60)
        
        # Check current database type
        db_url = str(db.engine.url)
        if 'sqlite' in db_url:
            print("📦 Database: SQLite")
        elif 'postgresql' in db_url:
            print("🐘 Database: PostgreSQL")
        else:
            print(f"📦 Database: {db_url.split('://')[0]}")
        
        print("\n📋 Creating tables...")
        
        # Check if tables already exist
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        tables_to_create = []
        
        if 'chat_messages' not in existing_tables:
            tables_to_create.append('chat_messages')
            print("   ➕ chat_messages (new)")
        else:
            print("   ✓ chat_messages (exists)")
        
        if 'chat_bans' not in existing_tables:
            tables_to_create.append('chat_bans')
            print("   ➕ chat_bans (new)")
        else:
            print("   ✓ chat_bans (exists)")
        
        if tables_to_create:
            # Create all new tables
            db.create_all()
            print(f"\n✅ Created {len(tables_to_create)} new table(s)")
        else:
            print("\n✅ All tables already exist")
        
        # Create initial system welcome message
        if 'chat_messages' in tables_to_create:
            # Find admin user or first user to attribute system messages
            admin_user = User.query.filter_by(role='admin').first()
            if not admin_user:
                admin_user = User.query.first()
            
            if admin_user:
                # Create welcome message
                welcome_msg = ChatMessage(
                    user_id=admin_user.id,
                    room='general',
                    message='🎉 Welcome to MIMIC Live Chat! Connect with fellow traders in real-time.',
                    message_type='system',
                    extra_data={'type': 'welcome'}
                )
                db.session.add(welcome_msg)
                db.session.commit()
                print("   ✓ Created initial welcome message")
        
        # Verify tables
        print("\n📊 Verification:")
        inspector = db.inspect(db.engine)
        
        for table in ['chat_messages', 'chat_bans']:
            if table in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns(table)]
                indexes = [idx['name'] for idx in inspector.get_indexes(table)]
                print(f"   ✓ {table}: {len(columns)} columns, {len(indexes)} indexes")
            else:
                print(f"   ✗ {table}: NOT FOUND")
        
        print("\n" + "=" * 60)
        print("🎉 Live Chat migration completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Restart the MIMIC application")
        print("2. Access the chat from user dashboard")
        print("3. Admins can moderate users via the admin panel")
        print("=" * 60)


if __name__ == '__main__':
    run_migration()
