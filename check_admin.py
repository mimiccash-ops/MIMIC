#!/usr/bin/env python3
"""
Check and create/reset admin user
==================================
Quick script to check if admin exists and reset password if needed
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User

def check_and_fix_admin():
    """Check if admin exists and create/reset if needed"""
    with app.app_context():
        # Check if admin exists
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            print("❌ Admin user not found!")
            print("Creating admin user...")
            admin = User(
                username='admin',
                role='admin',
                is_active=True
            )
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created!")
            print("   Username: admin")
            print("   Password: admin")
        else:
            print(f"✅ Admin user exists (ID: {admin.id}, Role: {admin.role}, Active: {admin.is_active})")
            
            # Test password
            if admin.check_password('admin'):
                print("✅ Password 'admin' works correctly")
            else:
                print("⚠️  Password 'admin' does NOT work")
                print("Resetting password to 'admin'...")
                admin.set_password('admin')
                db.session.commit()
                print("✅ Password reset to 'admin'")
        
        # List all admin users
        print("\n📋 All admin users:")
        admins = User.query.filter_by(role='admin').all()
        for a in admins:
            print(f"   - {a.username} (ID: {a.id}, Active: {a.is_active})")

if __name__ == "__main__":
    try:
        check_and_fix_admin()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
