#!/usr/bin/env python3
"""
Migration: Add System Settings Table

This migration creates the system_settings table for storing service configurations
(Telegram, Plisio, Email, etc.) in the database instead of config files.

Run: python migrate_add_system_settings.py
"""

import os
import sys
from datetime import datetime, timezone

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_migration():
    """Run the system settings migration."""
    print("=" * 60)
    print("Migration: Add System Settings Table")
    print("=" * 60)
    
    try:
        from app import app, db
        from models import SystemSetting, SERVICE_CATEGORIES
        
        with app.app_context():
            # Check if table already exists
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if 'system_settings' in existing_tables:
                print("✅ Table 'system_settings' already exists")
                
                # Check if we need to initialize defaults
                count = SystemSetting.query.count()
                if count == 0:
                    print("📝 Initializing default settings...")
                    SystemSetting.initialize_defaults()
                    print(f"✅ Initialized {SystemSetting.query.count()} default settings")
                else:
                    print(f"ℹ️  Table has {count} existing settings")
            else:
                print("📝 Creating 'system_settings' table...")
                
                # Create the table
                db.create_all()
                
                print("✅ Table created successfully")
                
                # Initialize default settings
                print("📝 Initializing default settings...")
                SystemSetting.initialize_defaults()
                print(f"✅ Initialized {SystemSetting.query.count()} default settings")
            
            # Show summary by category
            print("\n" + "-" * 40)
            print("Settings by category:")
            print("-" * 40)
            
            for category, meta in SERVICE_CATEGORIES.items():
                settings = SystemSetting.query.filter_by(category=category).all()
                enabled_setting = next((s for s in settings if s.key == 'enabled'), None)
                enabled = enabled_setting and enabled_setting.get_value().lower() in ('true', '1', 'yes')
                status = "✅" if enabled else "⭕"
                print(f"  {status} {meta['name']}: {len(settings)} settings")
            
            print("\n" + "=" * 60)
            print("✅ Migration completed successfully!")
            print("=" * 60)
            print("\nYou can now configure services through:")
            print("  Admin Dashboard → Settings → Service Configuration")
            print("=" * 60)
            
            return True
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you have all dependencies installed.")
        return False
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def import_from_config():
    """
    Import existing settings from config.ini and environment variables
    into the database.
    """
    print("\n" + "=" * 60)
    print("Importing existing configuration...")
    print("=" * 60)
    
    try:
        from app import app, db
        from models import SystemSetting
        from config import Config
        import configparser
        import os
        
        with app.app_context():
            imported_count = 0
            
            # Import from Config class (which reads from env vars and config.ini)
            imports = [
                # Telegram
                ('telegram', 'bot_token', getattr(Config, 'TG_TOKEN', ''), True),
                ('telegram', 'chat_id', getattr(Config, 'TG_CHAT_ID', ''), False),
                ('telegram', 'enabled', str(getattr(Config, 'TG_ENABLED', False)).lower(), False),
                
                # Email
                ('email', 'smtp_server', getattr(Config, 'SMTP_SERVER', ''), False),
                ('email', 'smtp_port', str(getattr(Config, 'SMTP_PORT', 587)), False),
                ('email', 'smtp_username', getattr(Config, 'SMTP_USERNAME', ''), False),
                ('email', 'smtp_password', getattr(Config, 'SMTP_PASSWORD', ''), True),
                ('email', 'from_email', getattr(Config, 'SMTP_FROM_EMAIL', ''), False),
                ('email', 'from_name', getattr(Config, 'SMTP_FROM_NAME', 'Brain Capital'), False),
                ('email', 'enabled', str(getattr(Config, 'EMAIL_ENABLED', False)).lower(), False),
                
                # Payment (Plisio)
                ('payment', 'api_key', getattr(Config, 'PLISIO_API_KEY', ''), True),
                ('payment', 'webhook_secret', getattr(Config, 'PLISIO_WEBHOOK_SECRET', ''), True),
                ('payment', 'enabled', str(getattr(Config, 'PAYMENT_ENABLED', False)).lower(), False),
                
                # Twitter
                ('twitter', 'api_key', getattr(Config, 'TWITTER_API_KEY', ''), True),
                ('twitter', 'api_secret', getattr(Config, 'TWITTER_API_SECRET', ''), True),
                ('twitter', 'access_token', getattr(Config, 'TWITTER_ACCESS_TOKEN', ''), True),
                ('twitter', 'access_secret', getattr(Config, 'TWITTER_ACCESS_SECRET', ''), True),
                ('twitter', 'min_roi_threshold', str(getattr(Config, 'TWITTER_MIN_ROI_THRESHOLD', 50.0)), False),
                ('twitter', 'site_url', getattr(Config, 'SITE_URL', 'https://mimic.cash'), False),
                ('twitter', 'enabled', str(getattr(Config, 'TWITTER_ENABLED', False)).lower(), False),
                
                # OpenAI
                ('openai', 'api_key', getattr(Config, 'OPENAI_API_KEY', ''), True),
                ('openai', 'embedding_model', getattr(Config, 'OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'), False),
                ('openai', 'chat_model', getattr(Config, 'OPENAI_CHAT_MODEL', 'gpt-4o-mini'), False),
                ('openai', 'confidence_threshold', str(getattr(Config, 'RAG_CONFIDENCE_THRESHOLD', 0.7)), False),
                ('openai', 'chunk_size', str(getattr(Config, 'RAG_CHUNK_SIZE', 500)), False),
                ('openai', 'chunk_overlap', str(getattr(Config, 'RAG_CHUNK_OVERLAP', 50)), False),
                ('openai', 'enabled', str(getattr(Config, 'SUPPORT_BOT_ENABLED', False)).lower(), False),
                
                # WebPush
                ('webpush', 'vapid_public_key', getattr(Config, 'VAPID_PUBLIC_KEY', ''), False),
                ('webpush', 'vapid_private_key', getattr(Config, 'VAPID_PRIVATE_KEY', ''), True),
                ('webpush', 'vapid_claim_email', getattr(Config, 'VAPID_CLAIM_EMAIL', 'mailto:admin@mimic.cash'), False),
                ('webpush', 'enabled', str(getattr(Config, 'WEBPUSH_ENABLED', False)).lower(), False),
                
                # Binance
                ('binance', 'api_key', getattr(Config, 'BINANCE_MASTER_KEY', ''), True),
                ('binance', 'api_secret', getattr(Config, 'BINANCE_MASTER_SECRET', ''), True),
                ('binance', 'testnet', str(getattr(Config, 'IS_TESTNET', False)).lower(), False),
                
                # Webhook
                ('webhook', 'passphrase', getattr(Config, 'WEBHOOK_PASSPHRASE', ''), True),
                
                # Compliance
                ('compliance', 'tos_version', getattr(Config, 'TOS_VERSION', '1.0'), False),
                ('compliance', 'blocked_countries', ','.join(getattr(Config, 'BLOCKED_COUNTRIES', ['US', 'KP', 'IR'])), False),
                ('compliance', 'tos_consent_enabled', str(getattr(Config, 'TOS_CONSENT_ENABLED', True)).lower(), False),
                ('compliance', 'geo_blocking_enabled', str(getattr(Config, 'GEO_BLOCKING_ENABLED', False)).lower(), False),
                
                # General
                ('general', 'max_open_positions', str(getattr(Config, 'GLOBAL_MAX_POSITIONS', 10)), False),
                
                # Proxy
                ('proxy', 'enabled', str(getattr(Config, 'PROXY_ENABLED', False)).lower(), False),
                ('proxy', 'proxies', ','.join(getattr(Config, 'PROXY_LIST', [])), False),
                ('proxy', 'users_per_proxy', str(getattr(Config, 'PROXY_USERS_PER_PROXY', 50)), False),
                ('proxy', 'proxy_cooldown_seconds', str(getattr(Config, 'PROXY_COOLDOWN_SECONDS', 60)), False),
                ('proxy', 'max_proxy_retries', str(getattr(Config, 'PROXY_MAX_RETRIES', 3)), False),
                
                # Panic
                ('panic', 'otp_secret', getattr(Config, 'PANIC_OTP_SECRET', ''), True),
                ('panic', 'authorized_users', ','.join(str(u) for u in getattr(Config, 'PANIC_AUTHORIZED_USERS', [])), False),
            ]
            
            for category, key, value, is_sensitive in imports:
                if value and not value.startswith('${'):
                    existing = SystemSetting.query.filter_by(category=category, key=key).first()
                    if existing:
                        # Only update if current value is empty
                        if not existing.get_value():
                            existing.set_value(value, is_sensitive)
                            imported_count += 1
                            print(f"  📥 Imported {category}.{key}")
                    else:
                        # Create new setting
                        setting = SystemSetting(
                            category=category,
                            key=key,
                            is_sensitive=is_sensitive
                        )
                        setting.set_value(value, is_sensitive)
                        db.session.add(setting)
                        imported_count += 1
                        print(f"  📥 Created {category}.{key}")
            
            db.session.commit()
            print(f"\n✅ Imported {imported_count} settings from existing configuration")
            
            return True
            
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='System Settings Migration')
    parser.add_argument('--import-config', action='store_true', 
                       help='Import existing settings from config.ini and env vars')
    args = parser.parse_args()
    
    success = run_migration()
    
    if success and args.import_config:
        import_from_config()
    
    sys.exit(0 if success else 1)
