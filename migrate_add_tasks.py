"""
Migration script to add Task/Challenge tables.

Run this script once to create:
- tasks table (admin-created challenges)
- task_participations table (user participation tracking)

Usage:
    python migrate_add_tasks.py

This is idempotent - safe to run multiple times.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Task, TaskParticipation


def migrate():
    """Create task tables if they don't exist."""
    with app.app_context():
        print("=" * 60)
        print("  TASK/CHALLENGE TABLES MIGRATION")
        print("=" * 60)
        
        # Create tables
        print("\n[*] Creating task tables...")
        db.create_all()
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'tasks' in tables:
            print("[OK] tasks table created successfully")
            
            # Show columns
            columns = [col['name'] for col in inspector.get_columns('tasks')]
            print(f"     Columns: {', '.join(columns[:8])}...")
        else:
            print("[!] tasks table NOT found - something went wrong")
        
        if 'task_participations' in tables:
            print("[OK] task_participations table created successfully")
            
            # Show columns
            columns = [col['name'] for col in inspector.get_columns('task_participations')]
            print(f"     Columns: {', '.join(columns[:8])}...")
        else:
            print("[!] task_participations table NOT found - something went wrong")
        
        # Create sample tasks if none exist
        existing = Task.query.first()
        if not existing:
            print("\n[*] Creating sample tasks...")
            
            from models import User
            admin = User.query.filter_by(role='admin').first()
            admin_id = admin.id if admin else None
            
            # Sample social task
            task1 = Task(
                title="Follow us on Twitter",
                description="Follow our official Twitter account and stay updated with the latest news and trading signals.",
                instructions="1. Go to our Twitter page\n2. Click the Follow button\n3. Submit your Twitter username as proof",
                task_type="social",
                icon="fa-twitter",
                color="#1da1f2",
                reward_type="xp",
                reward_amount=50,
                reward_description="50 XP points",
                requires_approval=True,
                status="active",
                is_featured=True,
                created_by_id=admin_id
            )
            db.session.add(task1)
            
            # Sample referral task
            task2 = Task(
                title="Invite 3 Friends",
                description="Invite 3 friends to join the platform using your referral link.",
                instructions="1. Share your referral link from your dashboard\n2. Wait for 3 friends to register\n3. Submit once completed",
                task_type="referral",
                icon="fa-users",
                color="#a855f7",
                reward_type="money",
                reward_amount=10.0,
                reward_description="$10 credited to your balance",
                requires_approval=True,
                status="active",
                is_featured=True,
                created_by_id=admin_id
            )
            db.session.add(task2)
            
            # Sample trading task
            task3 = Task(
                title="Complete 10 Trades",
                description="Complete at least 10 successful copy trades this week.",
                instructions="Make sure copy trading is enabled and complete 10 trades.",
                task_type="trading",
                icon="fa-chart-line",
                color="#00ff88",
                reward_type="subscription",
                reward_amount=7,
                reward_description="7 days of free Pro subscription",
                requires_approval=True,
                auto_verify=True,
                status="active",
                created_by_id=admin_id
            )
            db.session.add(task3)
            
            db.session.commit()
            print("[OK] Created 3 sample tasks")
        else:
            print(f"\n[INFO] Tasks already exist in database")
        
        print("\n" + "=" * 60)
        print("  MIGRATION COMPLETE!")
        print("=" * 60)


if __name__ == '__main__':
    migrate()
