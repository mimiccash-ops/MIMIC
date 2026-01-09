"""
Governance/Voting System Database Migration Script
Adds proposal and vote tables for Elite user voting

Run this script to add governance features:
    python migrate_add_governance.py

This migration adds:
- proposals table: Governance proposals that Elite users can vote on
- votes table: Individual votes on proposals
"""

import os
import sys
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GovernanceMigration")


def get_db_path():
    """Get the SQLite database path"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, 'brain_capital.db')


def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def table_exists(cursor, table_name):
    """Check if a table exists"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def migrate_governance():
    """Add governance/voting tables to the database"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        logger.error(f"❌ Database not found: {db_path}")
        logger.info("Run the application first to create the database.")
        return False
    
    logger.info(f"📦 Database: {db_path}")
    logger.info("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        changes_made = 0
        
        # ==================== PROPOSALS TABLE ====================
        logger.info("\n📋 Checking 'proposals' table...")
        
        if not table_exists(cursor, 'proposals'):
            logger.info("  Creating 'proposals' table...")
            cursor.execute("""
                CREATE TABLE proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(200) NOT NULL,
                    description TEXT NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    votes_yes INTEGER DEFAULT 0,
                    votes_no INTEGER DEFAULT 0,
                    votes_yes_weight REAL DEFAULT 0.0,
                    votes_no_weight REAL DEFAULT 0.0,
                    min_votes_required INTEGER DEFAULT 5,
                    pass_threshold REAL DEFAULT 60.0,
                    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    voting_ends_at DATETIME,
                    closed_at DATETIME,
                    implemented_at DATETIME,
                    admin_notes TEXT
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_category ON proposals(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_created_by ON proposals(created_by_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_voting_ends ON proposals(voting_ends_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_status_category ON proposals(status, category)")
            
            logger.info("  ✅ Created 'proposals' table with indexes")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'proposals' already exists")
        
        # ==================== VOTES TABLE ====================
        logger.info("\n📋 Checking 'votes' table...")
        
        if not table_exists(cursor, 'votes'):
            logger.info("  Creating 'votes' table...")
            cursor.execute("""
                CREATE TABLE votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id INTEGER NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    vote_type VARCHAR(10) NOT NULL,
                    vote_weight REAL DEFAULT 1.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(proposal_id, user_id)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_proposal ON votes(proposal_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_created_at ON votes(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_proposal_type ON votes(proposal_id, vote_type)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_proposal_vote ON votes(proposal_id, user_id)")
            
            logger.info("  ✅ Created 'votes' table with indexes")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'votes' already exists")
        
        # Commit all changes
        conn.commit()
        
        logger.info("\n" + "=" * 60)
        if changes_made > 0:
            logger.info(f"✅ Governance migration complete! {changes_made} table(s) created.")
        else:
            logger.info("✅ Governance tables already exist. No changes needed.")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()


def create_sample_proposals():
    """Create sample proposals for testing (optional)"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if there are any proposals
        cursor.execute("SELECT COUNT(*) FROM proposals")
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info("\n📋 Creating sample proposals...")
            
            from datetime import datetime, timedelta
            
            now = datetime.utcnow()
            week_later = now + timedelta(days=7)
            
            sample_proposals = [
                (
                    'Add SOL/USDT Trading Pair',
                    'Request to add Solana (SOL) against USDT as a new trading pair. SOL has shown strong volume and community interest.',
                    'trading_pair',
                    'active',
                    now.isoformat(),
                    week_later.isoformat()
                ),
                (
                    'Implement 15% Max Drawdown Limit',
                    'Proposal to set a platform-wide maximum daily drawdown limit of 15% to protect traders from excessive losses.',
                    'risk_management',
                    'active',
                    now.isoformat(),
                    week_later.isoformat()
                ),
                (
                    'Add Bitget Exchange Integration',
                    'Request to integrate Bitget exchange for copy trading. Bitget offers competitive fees and growing liquidity.',
                    'exchange',
                    'active',
                    now.isoformat(),
                    week_later.isoformat()
                ),
            ]
            
            for title, desc, category, status, created, ends in sample_proposals:
                cursor.execute("""
                    INSERT INTO proposals (title, description, category, status, created_at, voting_ends_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, desc, category, status, created, ends))
            
            conn.commit()
            logger.info("  ✅ Created 3 sample proposals for testing")
        else:
            logger.info(f"\n  ✓ {count} proposal(s) already exist, skipping samples")
            
    except Exception as e:
        logger.warning(f"  ⚠️ Could not create sample proposals: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  MIMIC - Governance/Voting System Migration")
    print("=" * 60)
    print()
    print("This script will add governance/voting features:")
    print("  • Proposals table: Create and manage governance proposals")
    print("  • Votes table: Track Elite user votes on proposals")
    print("  • Categories: Trading Pairs, Risk Management, Exchanges")
    print("  • Only Elite level users (order_rank >= 4) can vote")
    print()
    
    success = migrate_governance()
    
    if success:
        # Ask if user wants to create sample proposals
        print()
        create_samples = input("Would you like to create sample proposals for testing? (y/n): ").strip().lower()
        if create_samples == 'y':
            create_sample_proposals()
        
        print()
        print("=" * 60)
        print("✅ Governance system ready!")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ Migration failed. Please check the errors above.")
        print("=" * 60)
        sys.exit(1)
