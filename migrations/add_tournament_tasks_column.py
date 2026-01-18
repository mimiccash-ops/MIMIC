#!/usr/bin/env python3
"""
Quick migration script to add tasks column to tournaments table.
Run this if the main migrate.py can't connect to the database.

Usage:
    python3 migrations/add_tournament_tasks_column.py
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from app import app, db
from sqlalchemy import inspect, text

def main():
    """Add tasks column to tournaments table if it doesn't exist."""
    
    with app.app_context():
        db_type = db.engine.dialect.name
        print(f"📦 Database type: {db_type.upper()}")
        
        inspector = inspect(db.engine)
        
        # Check if tournaments table exists
        if 'tournaments' not in inspector.get_table_names():
            print("❌ tournaments table does not exist!")
            return 1
        
        # Check if tasks column already exists
        columns = [col["name"] for col in inspector.get_columns('tournaments')]
        if 'tasks' in columns:
            print("✅ Column tournaments.tasks already exists")
            return 0
        
        # Add the column
        try:
            if db_type == "postgresql":
                sql = "ALTER TABLE tournaments ADD COLUMN tasks JSON"
            else:  # SQLite
                sql = "ALTER TABLE tournaments ADD COLUMN tasks TEXT"
            
            with db.engine.begin() as connection:
                connection.execute(text(sql))
            
            print("✅ Successfully added tasks column to tournaments table")
            return 0
            
        except Exception as e:
            print(f"❌ Failed to add column: {e}")
            import traceback
            traceback.print_exc()
            return 1

if __name__ == "__main__":
    sys.exit(main())
