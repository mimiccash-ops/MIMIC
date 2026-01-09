"""
Migration script to add Tournament tables.

Run this script once to create:
- tournaments table
- tournament_participants table

Usage:
    python migrate_add_tournaments.py

This is idempotent - safe to run multiple times.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Tournament, TournamentParticipant


def migrate():
    """Create tournament tables if they don't exist."""
    with app.app_context():
        print("=" * 60)
        print("  TOURNAMENT TABLES MIGRATION")
        print("=" * 60)
        
        # Create tables
        print("\n[*] Creating tournament tables...")
        db.create_all()
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'tournaments' in tables:
            print("[OK] tournaments table created successfully")
            
            # Show columns
            columns = [col['name'] for col in inspector.get_columns('tournaments')]
            print(f"     Columns: {', '.join(columns[:5])}...")
        else:
            print("[!] tournaments table NOT found - something went wrong")
        
        if 'tournament_participants' in tables:
            print("[OK] tournament_participants table created successfully")
            
            # Show columns
            columns = [col['name'] for col in inspector.get_columns('tournament_participants')]
            print(f"     Columns: {', '.join(columns[:5])}...")
        else:
            print("[!] tournament_participants table NOT found - something went wrong")
        
        # Create a sample upcoming tournament if none exists
        existing = Tournament.query.first()
        if not existing:
            print("\n[*] Creating sample weekly tournament...")
            tournament = Tournament.create_weekly_tournament(
                name="MIMIC Weekly Championship",
                entry_fee=10.0
            )
            print(f"[OK] Created: {tournament.name}")
            print(f"     Start: {tournament.start_date}")
            print(f"     End: {tournament.end_date}")
            print(f"     Entry Fee: ${tournament.entry_fee}")
        else:
            print(f"\n[INFO] Tournament already exists: {existing.name}")
        
        print("\n" + "=" * 60)
        print("  MIGRATION COMPLETE!")
        print("=" * 60)


if __name__ == '__main__':
    migrate()
