#!/usr/bin/env python3
"""
Migration script to add Subscription Management Settings.

Adds settings for:
- Subscription enabled/disabled toggle
- Payment wallet addresses for different networks
- Insurance Fund wallet address
- Auto-confirm payments setting

Usage:
    python migrate_add_subscription_settings.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from config import Config
from models import db, SystemSetting
from sqlalchemy import text, inspect


def check_table_exists(engine, table_name):
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def run_migration():
    """Run the migration to add subscription settings"""
    
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        print("=" * 60)
        print("🔄 Subscription Management Settings Migration")
        print("=" * 60)
        
        # Ensure system_settings table exists
        if not check_table_exists(db.engine, 'system_settings'):
            print("📦 Creating 'system_settings' table...")
            SystemSetting.__table__.create(db.engine, checkfirst=True)
            print("   ✅ Table created successfully")
        
        # Define subscription settings
        subscription_settings = [
            # Subscription system toggle
            {
                'category': 'subscription',
                'key': 'enabled',
                'value': 'false',
                'is_sensitive': False,
                'description': 'Enable/disable paid subscription requirement. When disabled, all users have free access.'
            },
            # Auto-confirm payments
            {
                'category': 'subscription',
                'key': 'auto_confirm',
                'value': 'false',
                'is_sensitive': False,
                'description': 'Automatically confirm payments after user marks as paid (risky - use only with trusted users)'
            },
            # Payment confirmation timeout (hours)
            {
                'category': 'subscription',
                'key': 'confirm_timeout_hours',
                'value': '24',
                'is_sensitive': False,
                'description': 'Hours to wait for admin to confirm payment before auto-expiring'
            },
            # Default subscription days when manually activated
            {
                'category': 'subscription',
                'key': 'default_days',
                'value': '30',
                'is_sensitive': False,
                'description': 'Default subscription duration in days when manually activated'
            },
            
            # Payment wallet addresses by network
            {
                'category': 'wallet',
                'key': 'usdt_trc20',
                'value': '',
                'is_sensitive': False,
                'description': 'USDT TRC20 (Tron) wallet address for receiving subscription payments'
            },
            {
                'category': 'wallet',
                'key': 'usdt_erc20',
                'value': '',
                'is_sensitive': False,
                'description': 'USDT ERC20 (Ethereum) wallet address for receiving subscription payments'
            },
            {
                'category': 'wallet',
                'key': 'usdt_bep20',
                'value': '',
                'is_sensitive': False,
                'description': 'USDT BEP20 (BSC) wallet address for receiving subscription payments'
            },
            {
                'category': 'wallet',
                'key': 'btc',
                'value': '',
                'is_sensitive': False,
                'description': 'Bitcoin wallet address for receiving subscription payments'
            },
            {
                'category': 'wallet',
                'key': 'eth',
                'value': '',
                'is_sensitive': False,
                'description': 'Ethereum wallet address for receiving subscription payments'
            },
            {
                'category': 'wallet',
                'key': 'ltc',
                'value': '',
                'is_sensitive': False,
                'description': 'Litecoin wallet address for receiving subscription payments'
            },
            {
                'category': 'wallet',
                'key': 'sol',
                'value': '',
                'is_sensitive': False,
                'description': 'Solana wallet address for receiving subscription payments'
            },
            
            # Insurance Fund wallet
            {
                'category': 'insurance_fund',
                'key': 'wallet_address',
                'value': '',
                'is_sensitive': False,
                'description': 'Wallet address for storing Insurance Fund (Safety Pool) funds'
            },
            {
                'category': 'insurance_fund',
                'key': 'wallet_network',
                'value': 'USDT_TRC20',
                'is_sensitive': False,
                'description': 'Network for Insurance Fund wallet (USDT_TRC20, USDT_ERC20, etc.)'
            },
            {
                'category': 'insurance_fund',
                'key': 'contribution_rate',
                'value': '5',
                'is_sensitive': False,
                'description': 'Percentage of platform fees contributed to Insurance Fund'
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for setting_data in subscription_settings:
            # Check if setting already exists
            existing = SystemSetting.query.filter_by(
                category=setting_data['category'],
                key=setting_data['key']
            ).first()
            
            if existing:
                # Update description if needed
                if existing.description != setting_data['description']:
                    existing.description = setting_data['description']
                    updated_count += 1
                    print(f"   ⬆️  Updated: {setting_data['category']}.{setting_data['key']}")
            else:
                # Create new setting
                new_setting = SystemSetting(
                    category=setting_data['category'],
                    key=setting_data['key'],
                    is_sensitive=setting_data['is_sensitive'],
                    description=setting_data['description']
                )
                new_setting.set_value(setting_data['value'], setting_data['is_sensitive'])
                db.session.add(new_setting)
                created_count += 1
                print(f"   ✅ Created: {setting_data['category']}.{setting_data['key']}")
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print(f"\n📊 Summary:")
        print(f"   Created: {created_count} settings")
        print(f"   Updated: {updated_count} settings")
        print(f"   Skipped: {len(subscription_settings) - created_count - updated_count} (already exist)")
        
        print("\n📋 Settings categories added:")
        print("   - subscription: Subscription system toggle and settings")
        print("   - wallet: Payment wallet addresses by network")
        print("   - insurance_fund: Insurance Fund wallet and settings")


if __name__ == '__main__':
    run_migration()
