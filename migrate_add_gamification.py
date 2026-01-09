"""
Gamification System Database Migration Script
Adds user levels, achievements, and XP tracking

Run this script to add gamification features:
    python migrate_add_gamification.py

This migration adds:
- user_levels table: Defines level tiers (Novice -> Elite)
- user_achievements table: Tracks unlocked badges
- Gamification columns to users table: xp, current_level_id, discount_percent, total_trading_volume
"""

import os
import sys
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GamificationMigration")


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


def add_column_if_not_exists(cursor, table_name, column_name, column_type, default_value=None):
    """Add a column to a table if it doesn't already exist"""
    if column_exists(cursor, table_name, column_name):
        logger.info(f"  ✓ Column {table_name}.{column_name} already exists")
        return False
    
    try:
        if default_value is not None:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
        else:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        
        cursor.execute(sql)
        logger.info(f"  ✅ Added column {table_name}.{column_name} ({column_type})")
        return True
    except sqlite3.OperationalError as e:
        logger.error(f"  ❌ Failed to add {table_name}.{column_name}: {e}")
        return False


def migrate_gamification():
    """Add gamification tables and columns to the database"""
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
        
        # ==================== USER_LEVELS TABLE ====================
        logger.info("\n📋 Checking 'user_levels' table...")
        
        if not table_exists(cursor, 'user_levels'):
            logger.info("  Creating 'user_levels' table...")
            cursor.execute("""
                CREATE TABLE user_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    icon VARCHAR(50) DEFAULT 'fa-user',
                    color VARCHAR(20) DEFAULT '#888888',
                    min_xp INTEGER DEFAULT 0 NOT NULL,
                    max_xp INTEGER,
                    discount_percent REAL DEFAULT 0.0,
                    order_rank INTEGER DEFAULT 0,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("  ✅ Created 'user_levels' table")
            changes_made += 1
            
            # Insert default levels
            default_levels = [
                ('Novice', 'fa-seedling', '#888888', 0, 1000, 0.0, 0, 'Just getting started! Trade to earn XP and level up.'),
                ('Amateur', 'fa-user', '#4CAF50', 1000, 10000, 2.0, 1, 'Building your skills! 2% commission discount.'),
                ('Pro', 'fa-chart-line', '#2196F3', 10000, 50000, 5.0, 2, 'Proven trader! 5% commission discount.'),
                ('Expert', 'fa-star', '#9C27B0', 50000, 100000, 8.0, 3, 'Top-tier performer! 8% commission discount.'),
                ('Elite', 'fa-crown', '#FFD700', 100000, None, 10.0, 4, 'The best of the best! 10% commission discount.'),
            ]
            
            for name, icon, color, min_xp, max_xp, discount, order_rank, desc in default_levels:
                cursor.execute("""
                    INSERT INTO user_levels (name, icon, color, min_xp, max_xp, discount_percent, order_rank, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, icon, color, min_xp, max_xp, discount, order_rank, desc))
            
            logger.info("  ✅ Inserted default levels (Novice -> Elite)")
        else:
            logger.info("  ✓ Table 'user_levels' exists")
        
        # ==================== USER_ACHIEVEMENTS TABLE ====================
        logger.info("\n📋 Checking 'user_achievements' table...")
        
        if not table_exists(cursor, 'user_achievements'):
            logger.info("  Creating 'user_achievements' table...")
            cursor.execute("""
                CREATE TABLE user_achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    achievement_type VARCHAR(50) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    icon VARCHAR(50) DEFAULT 'fa-trophy',
                    color VARCHAR(20) DEFAULT '#FFD700',
                    rarity VARCHAR(20) DEFAULT 'common',
                    unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, achievement_type)
                )
            """)
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_achievements_type ON user_achievements(achievement_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_achievements_user_type ON user_achievements(user_id, achievement_type)")
            logger.info("  ✅ Created 'user_achievements' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'user_achievements' exists")
        
        # ==================== USERS TABLE GAMIFICATION COLUMNS ====================
        logger.info("\n📋 Checking gamification columns in 'users' table...")
        
        gamification_columns = [
            ("xp", "INTEGER", "0"),
            ("current_level_id", "INTEGER", "NULL"),
            ("discount_percent", "REAL", "0.0"),
            ("total_trading_volume", "REAL", "0.0"),
        ]
        
        for col_name, col_type, default in gamification_columns:
            if add_column_if_not_exists(cursor, "users", col_name, col_type, default):
                changes_made += 1
        
        # ==================== INITIALIZE USER LEVELS ====================
        logger.info("\n📋 Initializing user levels for existing users...")
        
        # Get Novice level ID
        cursor.execute("SELECT id FROM user_levels WHERE name = 'Novice'")
        novice_row = cursor.fetchone()
        if novice_row:
            novice_id = novice_row[0]
            # Set Novice level for all users without a level
            cursor.execute("""
                UPDATE users 
                SET current_level_id = ?, xp = 0, discount_percent = 0.0
                WHERE current_level_id IS NULL
            """, (novice_id,))
            logger.info("  ✅ Set default Novice level for users without a level")
        
        # Commit all changes
        conn.commit()
        
        logger.info("\n" + "=" * 60)
        if changes_made > 0:
            logger.info(f"✅ Gamification migration complete! {changes_made} changes made.")
        else:
            logger.info("✅ Gamification tables already exist. No changes needed.")
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


def create_gamification_indexes():
    """Create performance indexes for gamification tables"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        return
    
    logger.info("\n📊 Creating gamification indexes...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    indexes = [
        # User level indexes
        "CREATE INDEX IF NOT EXISTS idx_user_levels_name ON user_levels(name)",
        "CREATE INDEX IF NOT EXISTS idx_user_levels_min_xp ON user_levels(min_xp)",
        "CREATE INDEX IF NOT EXISTS idx_user_levels_order ON user_levels(order_rank)",
        
        # User achievement indexes
        "CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_achievements_type ON user_achievements(achievement_type)",
        "CREATE INDEX IF NOT EXISTS idx_achievements_unlocked ON user_achievements(unlocked_at)",
        
        # User gamification indexes
        "CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp)",
        "CREATE INDEX IF NOT EXISTS idx_users_level ON users(current_level_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_volume ON users(total_trading_volume)",
    ]
    
    try:
        for idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
            except sqlite3.OperationalError:
                pass  # Index might already exist
        
        conn.commit()
        logger.info("✅ Gamification indexes created/verified")
    except Exception as e:
        logger.warning(f"⚠️ Some indexes may not have been created: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  MIMIC - Gamification System Migration")
    print("=" * 60)
    print()
    print("This script will add gamification features:")
    print("  • User Levels (Novice -> Amateur -> Pro -> Expert -> Elite)")
    print("  • Commission discounts based on level")
    print("  • Achievement badges (First Blood, Diamond Hands, Whale, etc.)")
    print("  • XP tracking (Volume/1000 + Days Active)")
    print()
    
    success = migrate_gamification()
    
    if success:
        create_gamification_indexes()
        print()
        print("=" * 60)
        print("✅ You can now run the application with gamification enabled!")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ Migration failed. Please check the errors above.")
        print("=" * 60)
        sys.exit(1)
