#!/usr/bin/env python3
"""
Simple migration script to add tasks column - no Flask dependencies needed.
Uses psycopg2 directly to connect to PostgreSQL.

Usage:
    python3 migrations/add_tasks_column_simple.py
    # Or set DATABASE_URL environment variable:
    DATABASE_URL=postgresql://user:pass@host:5432/db python3 migrations/add_tasks_column_simple.py
"""

import os
import sys
import urllib.parse

def get_db_connection():
    """Get database connection from DATABASE_URL or config.ini"""
    # Try environment variable first
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        # Try reading from config.ini
        try:
            import configparser
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path)
                # Try to get from [Database] section if it exists
                if 'Database' in config and 'url' in config['Database']:
                    database_url = config['Database']['url']
        except Exception:
            pass
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment or config.ini")
        print("   Please set: export DATABASE_URL=postgresql://user:pass@host:5432/db")
        print("   Or run: psql -U user -d database -c \"ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS tasks JSON;\"")
        sys.exit(1)
    
    # Handle postgres:// -> postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Parse the URL
    try:
        parsed = urllib.parse.urlparse(database_url)
        conn_params = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password
        }
    except Exception as e:
        print(f"❌ Failed to parse DATABASE_URL: {e}")
        sys.exit(1)
    
    # Connect using psycopg2
    try:
        import psycopg2
        conn = psycopg2.connect(**conn_params)
        return conn
    except ImportError:
        print("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

def main():
    """Add tasks column to tournaments table"""
    print("📦 Starting migration: Add tasks column to tournaments table")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tournaments' AND column_name = 'tasks'
        """)
        
        if cursor.fetchone():
            print("✅ Column tournaments.tasks already exists")
            conn.close()
            return 0
        
        # Add the column
        print("🔧 Adding tasks column...")
        cursor.execute("ALTER TABLE tournaments ADD COLUMN tasks JSON")
        conn.commit()
        
        print("✅ Successfully added tasks column to tournaments table")
        conn.close()
        return 0
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to add column: {e}")
        conn.close()
        return 1

if __name__ == "__main__":
    sys.exit(main())
