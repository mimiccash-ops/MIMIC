#!/usr/bin/env python3
"""
Reset Admin Password Script
===========================
This script resets the password for an admin user.

Usage:
    python scripts/reset_admin.py <username> [new_password]
    docker compose run --rm web python scripts/reset_admin.py <username> [new_password]

If new_password is not provided, a random password will be generated.

Note: If running locally and getting database connection errors, use Docker:
    docker compose run --rm web python scripts/reset_admin.py admin
"""

import sys
import os
import secrets
import string

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_password(length=16):
    """Generate a random secure password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def reset_admin_password(username, new_password=None):
    """Reset password for admin user."""
    with app.app_context():
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if not user:
            print(f"❌ User '{username}' not found!")
            return False
        
        # Check if user is admin
        if user.role != 'admin':
            print(f"⚠️  User '{username}' is not an admin (role: {user.role})")
            response = input("Do you want to reset password anyway? (y/N): ")
            if response.lower() != 'y':
                print("❌ Password reset cancelled")
                return False
        
        # Generate password if not provided
        if not new_password:
            new_password = generate_password()
        
        # Hash password
        password_hash = pwd_context.hash(new_password)
        
        # Update user
        user.password_hash = password_hash
        db.session.commit()
        
        print(f"✅ Password reset successful for user '{username}'")
        print(f"📝 New password: {new_password}")
        print(f"⚠️  Please save this password securely!")
        
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/reset_admin.py <username> [new_password]")
        sys.exit(1)
    
    username = sys.argv[1]
    new_password = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        reset_admin_password(username, new_password)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
