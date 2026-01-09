#!/usr/bin/env python3
"""
Migration script to add SystemStats table for Insurance Fund (Safety Pool) tracking.

Run this script to create the system_stats table and initialize the Insurance Fund.

Usage:
    python migrate_add_insurance_fund.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from config import Config
from models import db, SystemStats
from sqlalchemy import text, inspect


def check_table_exists(engine, table_name):
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def run_migration():
    """Run the migration to add SystemStats table"""
    
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        print("=" * 60)
        print("🔄 Insurance Fund Migration")
        print("=" * 60)
        
        # Check if table already exists
        if check_table_exists(db.engine, 'system_stats'):
            print("✅ Table 'system_stats' already exists")
            
            # Check if Insurance Fund is initialized
            fund_info = SystemStats.get_insurance_fund_info()
            print(f"   Current Insurance Fund Balance: {fund_info['formatted_balance']}")
            
            if fund_info['balance'] == 0:
                # Initialize with a starting balance to show credibility
                print("\n🏦 Initializing Insurance Fund with seed balance...")
                # Start with $10,000 seed - this represents the platform's initial commitment
                SystemStats.add_to_insurance_fund(10000.0)
                fund_info = SystemStats.get_insurance_fund_info()
                print(f"   ✅ Insurance Fund initialized: {fund_info['formatted_balance']}")
        else:
            print("📦 Creating 'system_stats' table...")
            
            # Create the table
            SystemStats.__table__.create(db.engine, checkfirst=True)
            print("   ✅ Table created successfully")
            
            # Initialize the Insurance Fund with seed balance
            print("\n🏦 Initializing Insurance Fund...")
            # Start with $10,000 seed - this represents the platform's initial commitment
            SystemStats.add_to_insurance_fund(10000.0)
            fund_info = SystemStats.get_insurance_fund_info()
            print(f"   ✅ Insurance Fund initialized: {fund_info['formatted_balance']}")
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print("\n📊 Insurance Fund Info:")
        print(f"   Balance: {fund_info['formatted_balance']}")
        print(f"   Contribution Rate: {fund_info['contribution_rate']}")
        print(f"   Description: {fund_info['description']}")
        print(f"   Verified: {'✓ Yes' if fund_info['is_verified'] else '✗ No'}")


if __name__ == '__main__':
    run_migration()
