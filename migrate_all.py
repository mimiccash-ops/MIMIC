"""
COMPREHENSIVE Database Migration Script
Adds ALL missing columns and tables to existing database

Run this script to update your existing database:
    python migrate_all.py

This combines all migrations:
- migrate_add_columns.py
- migrate_add_smart_features.py
- migrate_add_risk_guardrails.py
- migrate_add_subscription.py
- migrate_add_strategies.py
- migrate_add_chat.py (Live Chat feature)
- migrate_add_gamification.py (Levels & Achievements)
- migrate_add_support_bot.py (RAG Support Bot with pgvector)
- migrate_add_governance.py (Governance/Voting system for Elite users)
"""

import os
import sys
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Migration")


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


def migrate_database():
    """Add all missing columns to the database"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        logger.error(f"❌ Database not found: {db_path}")
        logger.info("Run the application first to create the database, or delete this file to start fresh.")
        return False
    
    logger.info(f"📦 Database: {db_path}")
    logger.info("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        changes_made = 0
        
        # ==================== USERS TABLE ====================
        logger.info("\n📋 Checking 'users' table...")
        
        # All user columns that might be missing
        user_columns = [
            # Basic columns from migrate_add_columns.py
            ("risk_multiplier", "REAL", "1.0"),
            ("referral_code", "VARCHAR(20)", "NULL"),
            ("referred_by_id", "INTEGER", "NULL"),
            ("target_balance", "REAL", "1000.0"),
            ("telegram_enabled", "BOOLEAN", "0"),
            ("telegram_chat_id", "VARCHAR(50)", "NULL"),
            ("avatar", "VARCHAR(100)", "'🧑‍💻'"),
            ("avatar_type", "VARCHAR(20)", "'emoji'"),
            
            # DCA columns from migrate_add_smart_features.py
            ("dca_enabled", "BOOLEAN", "0"),
            ("dca_multiplier", "REAL", "1.0"),
            ("dca_threshold", "REAL", "-2.0"),
            ("dca_max_orders", "INTEGER", "3"),
            
            # Trailing Stop-Loss columns from migrate_add_smart_features.py
            ("trailing_sl_enabled", "BOOLEAN", "0"),
            ("trailing_sl_activation", "REAL", "1.0"),
            ("trailing_sl_callback", "REAL", "0.5"),
            
            # Risk Guardrails columns from migrate_add_risk_guardrails.py
            ("daily_drawdown_limit_perc", "REAL", "10.0"),
            ("daily_profit_target_perc", "REAL", "20.0"),
            ("risk_guardrails_enabled", "BOOLEAN", "0"),
            ("risk_guardrails_paused_at", "DATETIME", "NULL"),
            ("risk_guardrails_reason", "VARCHAR(100)", "NULL"),
            
            # Subscription columns from migrate_add_subscription.py
            ("subscription_plan", "VARCHAR(50)", "'free'"),
            ("subscription_expires_at", "DATETIME", "NULL"),
            ("subscription_notified_expiring", "BOOLEAN", "0"),
            
            # Gamification columns from migrate_add_gamification.py
            ("xp", "INTEGER", "0"),
            ("current_level_id", "INTEGER", "NULL"),
            ("discount_percent", "REAL", "0.0"),
            ("total_trading_volume", "REAL", "0.0"),
        ]
        
        for col_name, col_type, default in user_columns:
            if add_column_if_not_exists(cursor, "users", col_name, col_type, default):
                changes_made += 1
        
        # ==================== TRADE_HISTORY TABLE ====================
        logger.info("\n📋 Checking 'trade_history' table...")
        
        trade_columns = [
            ("node_name", "VARCHAR(50)", "NULL"),
        ]
        
        for col_name, col_type, default in trade_columns:
            if add_column_if_not_exists(cursor, "trade_history", col_name, col_type, default):
                changes_made += 1
        
        # ==================== MESSAGES TABLE ====================
        logger.info("\n📋 Checking 'messages' table...")
        
        if not table_exists(cursor, 'messages'):
            logger.info("  Creating 'messages' table...")
            cursor.execute("""
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY,
                    sender_id INTEGER NOT NULL,
                    recipient_id INTEGER,
                    subject VARCHAR(200) DEFAULT '',
                    content TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT 0,
                    is_from_admin BOOLEAN DEFAULT 0,
                    parent_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (parent_id) REFERENCES messages(id) ON DELETE CASCADE
                )
            """)
            logger.info("  ✅ Created 'messages' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'messages' exists")
        
        # ==================== PASSWORD_RESET_TOKENS TABLE ====================
        logger.info("\n📋 Checking 'password_reset_tokens' table...")
        
        if not table_exists(cursor, 'password_reset_tokens'):
            logger.info("  Creating 'password_reset_tokens' table...")
            cursor.execute("""
                CREATE TABLE password_reset_tokens (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token VARCHAR(100) UNIQUE NOT NULL,
                    code VARCHAR(6) NOT NULL,
                    method VARCHAR(20) NOT NULL,
                    is_used BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            logger.info("  ✅ Created 'password_reset_tokens' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'password_reset_tokens' exists")
        
        # ==================== EXCHANGE_CONFIGS TABLE ====================
        logger.info("\n📋 Checking 'exchange_configs' table...")
        
        if not table_exists(cursor, 'exchange_configs'):
            logger.info("  Creating 'exchange_configs' table...")
            cursor.execute("""
                CREATE TABLE exchange_configs (
                    id INTEGER PRIMARY KEY,
                    exchange_name VARCHAR(50) UNIQUE NOT NULL,
                    display_name VARCHAR(100) NOT NULL,
                    is_enabled BOOLEAN DEFAULT 0,
                    requires_passphrase BOOLEAN DEFAULT 0,
                    description TEXT,
                    admin_api_key VARCHAR(500),
                    admin_api_secret VARCHAR(500),
                    admin_passphrase VARCHAR(500),
                    is_verified BOOLEAN DEFAULT 0,
                    verified_at DATETIME,
                    verification_error TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("  ✅ Created 'exchange_configs' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'exchange_configs' exists")
        
        # ==================== USER_EXCHANGES TABLE ====================
        logger.info("\n📋 Checking 'user_exchanges' table...")
        
        if not table_exists(cursor, 'user_exchanges'):
            logger.info("  Creating 'user_exchanges' table...")
            cursor.execute("""
                CREATE TABLE user_exchanges (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    exchange_name VARCHAR(50) NOT NULL,
                    label VARCHAR(100) NOT NULL,
                    api_key VARCHAR(500) NOT NULL,
                    api_secret VARCHAR(500) NOT NULL,
                    passphrase VARCHAR(500),
                    status VARCHAR(20) DEFAULT 'PENDING',
                    is_active BOOLEAN DEFAULT 0,
                    trading_enabled BOOLEAN DEFAULT 0,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            logger.info("  ✅ Created 'user_exchanges' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'user_exchanges' exists")
            # Check for trading_enabled column
            if add_column_if_not_exists(cursor, "user_exchanges", "trading_enabled", "BOOLEAN", "0"):
                changes_made += 1
        
        # ==================== REFERRAL_COMMISSIONS TABLE ====================
        logger.info("\n📋 Checking 'referral_commissions' table...")
        
        if not table_exists(cursor, 'referral_commissions'):
            logger.info("  Creating 'referral_commissions' table...")
            cursor.execute("""
                CREATE TABLE referral_commissions (
                    id INTEGER PRIMARY KEY,
                    referrer_id INTEGER NOT NULL,
                    referred_user_id INTEGER NOT NULL,
                    trade_id INTEGER,
                    commission_type VARCHAR(20) NOT NULL,
                    source_amount REAL DEFAULT 0.0,
                    commission_rate REAL DEFAULT 0.05,
                    amount REAL DEFAULT 0.0,
                    is_paid BOOLEAN DEFAULT 0,
                    paid_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (referred_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (trade_id) REFERENCES trade_history(id) ON DELETE SET NULL
                )
            """)
            logger.info("  ✅ Created 'referral_commissions' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'referral_commissions' exists")
        
        # ==================== REFERRAL_CLICKS TABLE (Influencer Dashboard) ====================
        logger.info("\n📋 Checking 'referral_clicks' table...")
        
        if not table_exists(cursor, 'referral_clicks'):
            logger.info("  Creating 'referral_clicks' table...")
            cursor.execute("""
                CREATE TABLE referral_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    ip_hash VARCHAR(64),
                    user_agent VARCHAR(512),
                    referer_url VARCHAR(1024),
                    utm_source VARCHAR(100),
                    utm_medium VARCHAR(100),
                    utm_campaign VARCHAR(100),
                    converted BOOLEAN DEFAULT 0,
                    converted_user_id INTEGER,
                    converted_at DATETIME,
                    deposited BOOLEAN DEFAULT 0,
                    first_deposit_amount FLOAT,
                    first_deposit_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (converted_user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_click_referrer_date ON referral_clicks(referrer_id, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_click_conversion ON referral_clicks(referrer_id, converted)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_click_ip_referrer ON referral_clicks(ip_hash, referrer_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_click_deposited ON referral_clicks(referrer_id, deposited)")
            logger.info("  ✅ Created 'referral_clicks' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'referral_clicks' exists")
        
        # ==================== PAYOUT_REQUESTS TABLE (Influencer Dashboard) ====================
        logger.info("\n📋 Checking 'payout_requests' table...")
        
        if not table_exists(cursor, 'payout_requests'):
            logger.info("  Creating 'payout_requests' table...")
            cursor.execute("""
                CREATE TABLE payout_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount FLOAT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                    payment_method VARCHAR(50) NOT NULL,
                    payment_address VARCHAR(500),
                    admin_id INTEGER,
                    admin_notes TEXT,
                    txn_id VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at DATETIME,
                    paid_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payout_user_status ON payout_requests(user_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payout_status_date ON payout_requests(status, created_at)")
            logger.info("  ✅ Created 'payout_requests' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'payout_requests' exists")
        
        # ==================== PAYMENTS TABLE ====================
        logger.info("\n📋 Checking 'payments' table...")
        
        if not table_exists(cursor, 'payments'):
            logger.info("  Creating 'payments' table...")
            cursor.execute("""
                CREATE TABLE payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider VARCHAR(50) DEFAULT 'plisio',
                    provider_txn_id VARCHAR(200),
                    amount_usd FLOAT NOT NULL,
                    amount_crypto FLOAT,
                    currency VARCHAR(20) DEFAULT 'USDT_TRC20',
                    plan VARCHAR(50) NOT NULL,
                    days INTEGER DEFAULT 30,
                    status VARCHAR(30) DEFAULT 'pending',
                    wallet_address VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME,
                    expires_at DATETIME
                )
            """)
            # Add unique index for provider_txn_id
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_provider_txn_id ON payments(provider_txn_id)")
            logger.info("  ✅ Created 'payments' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'payments' exists")
        
        # ==================== STRATEGIES TABLE ====================
        logger.info("\n📋 Checking 'strategies' table...")
        
        if not table_exists(cursor, 'strategies'):
            logger.info("  Creating 'strategies' table...")
            cursor.execute("""
                CREATE TABLE strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description TEXT,
                    risk_level VARCHAR(20) DEFAULT 'medium',
                    master_exchange_id INTEGER REFERENCES exchange_configs(id) ON DELETE SET NULL,
                    default_risk_perc REAL,
                    default_leverage INTEGER,
                    max_positions INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("  ✅ Created 'strategies' table")
            changes_made += 1
            
            # Create default "Main" strategy
            cursor.execute("""
                INSERT INTO strategies (name, description, risk_level, is_active)
                VALUES ('Main', 'Default trading strategy - follows the main master account', 'medium', 1)
            """)
            logger.info("  ✅ Created default 'Main' strategy")
        else:
            logger.info("  ✓ Table 'strategies' exists")
        
        # ==================== STRATEGY_SUBSCRIPTIONS TABLE ====================
        logger.info("\n📋 Checking 'strategy_subscriptions' table...")
        
        if not table_exists(cursor, 'strategy_subscriptions'):
            logger.info("  Creating 'strategy_subscriptions' table...")
            cursor.execute("""
                CREATE TABLE strategy_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
                    allocation_percent REAL DEFAULT 100.0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, strategy_id)
                )
            """)
            logger.info("  ✅ Created 'strategy_subscriptions' table")
            changes_made += 1
            
            # Migrate existing active users to default strategy
            cursor.execute("SELECT id FROM strategies WHERE name = 'Main'")
            strategy_row = cursor.fetchone()
            if strategy_row:
                default_strategy_id = strategy_row[0]
                cursor.execute("""
                    INSERT INTO strategy_subscriptions (user_id, strategy_id, allocation_percent, is_active)
                    SELECT id, ?, 100.0, 1 FROM users WHERE is_active = 1 AND role = 'user'
                """, (default_strategy_id,))
                logger.info("  ✅ Migrated active users to default strategy")
        else:
            logger.info("  ✓ Table 'strategy_subscriptions' exists")
        
        # ==================== CHAT_MESSAGES TABLE (Live Chat) ====================
        logger.info("\n📋 Checking 'chat_messages' table...")
        
        if not table_exists(cursor, 'chat_messages'):
            logger.info("  Creating 'chat_messages' table...")
            cursor.execute("""
                CREATE TABLE chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    room VARCHAR(50) DEFAULT 'general' NOT NULL,
                    message TEXT NOT NULL,
                    message_type VARCHAR(20) DEFAULT 'user',
                    extra_data TEXT,
                    is_deleted BOOLEAN DEFAULT 0,
                    deleted_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Create indexes for chat messages
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_room ON chat_messages(room)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_messages(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_room_time ON chat_messages(room, created_at)")
            logger.info("  ✅ Created 'chat_messages' table")
            changes_made += 1
            
            # Create initial welcome message
            cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
            admin_row = cursor.fetchone()
            if admin_row:
                cursor.execute("""
                    INSERT INTO chat_messages (user_id, room, message, message_type, extra_data)
                    VALUES (?, 'general', '🎉 Welcome to MIMIC Live Chat! Connect with fellow traders in real-time.', 'system', '{"type": "welcome"}')
                """, (admin_row[0],))
                logger.info("  ✅ Created initial welcome message")
        else:
            logger.info("  ✓ Table 'chat_messages' exists")
        
        # ==================== CHAT_BANS TABLE (Moderation) ====================
        logger.info("\n📋 Checking 'chat_bans' table...")
        
        if not table_exists(cursor, 'chat_bans'):
            logger.info("  Creating 'chat_bans' table...")
            cursor.execute("""
                CREATE TABLE chat_bans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    ban_type VARCHAR(20) DEFAULT 'mute',
                    reason VARCHAR(500),
                    expires_at DATETIME,
                    issued_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            # Create indexes for chat bans
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chatban_user ON chat_bans(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chatban_active ON chat_bans(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chatban_user_active ON chat_bans(user_id, is_active)")
            logger.info("  ✅ Created 'chat_bans' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'chat_bans' exists")
        
        # ==================== SYSTEM_STATS TABLE (Insurance Fund / Safety Pool) ====================
        logger.info("\n📋 Checking 'system_stats' table (Insurance Fund)...")
        
        if not table_exists(cursor, 'system_stats'):
            logger.info("  Creating 'system_stats' table...")
            cursor.execute("""
                CREATE TABLE system_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_key VARCHAR(50) UNIQUE NOT NULL,
                    stat_value REAL DEFAULT 0.0,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Create index for stat_key lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_stats_key ON system_stats(stat_key)")
            logger.info("  ✅ Created 'system_stats' table")
            changes_made += 1
            
            # Initialize Insurance Fund with seed balance ($10,000)
            cursor.execute("""
                INSERT INTO system_stats (stat_key, stat_value, description)
                VALUES ('insurance_fund_balance', 10000.0, 'Safety Pool - covers slippage losses in extreme market conditions')
            """)
            logger.info("  ✅ Initialized Insurance Fund with $10,000 seed balance")
        else:
            logger.info("  ✓ Table 'system_stats' exists")
            # Check if Insurance Fund exists, if not create it
            cursor.execute("SELECT stat_value FROM system_stats WHERE stat_key = 'insurance_fund_balance'")
            fund_row = cursor.fetchone()
            if fund_row is None:
                cursor.execute("""
                    INSERT INTO system_stats (stat_key, stat_value, description)
                    VALUES ('insurance_fund_balance', 10000.0, 'Safety Pool - covers slippage losses in extreme market conditions')
                """)
                logger.info("  ✅ Initialized Insurance Fund with $10,000 seed balance")
                changes_made += 1
            else:
                logger.info(f"  ✓ Insurance Fund balance: ${fund_row[0]:,.2f}")
        
        # ==================== USER_LEVELS TABLE (Gamification) ====================
        logger.info("\n📋 Checking 'user_levels' table (Gamification)...")
        
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
            
            logger.info("  ✅ Inserted default levels (Novice -> Amateur -> Pro -> Expert -> Elite)")
        else:
            logger.info("  ✓ Table 'user_levels' exists")
        
        # ==================== USER_ACHIEVEMENTS TABLE (Gamification) ====================
        logger.info("\n📋 Checking 'user_achievements' table (Gamification)...")
        
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
        
        # ==================== API_KEYS TABLE (Public Developer API) ====================
        logger.info("\n📋 Checking 'api_keys' table (Public API)...")
        
        if not table_exists(cursor, 'api_keys'):
            logger.info("  Creating 'api_keys' table...")
            cursor.execute("""
                CREATE TABLE api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    key VARCHAR(64) UNIQUE NOT NULL,
                    secret_hash VARCHAR(256) NOT NULL,
                    label VARCHAR(100) NOT NULL DEFAULT 'Default API Key',
                    permissions INTEGER DEFAULT 7,
                    rate_limit INTEGER DEFAULT 60,
                    ip_whitelist TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    last_used_at DATETIME,
                    total_requests INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    revoked_at DATETIME
                )
            """)
            # Create indexes
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_active ON api_keys(user_id, is_active)")
            logger.info("  ✅ Created 'api_keys' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'api_keys' exists")
        
        # ==================== SUPPORT BOT TABLES (RAG) ====================
        logger.info("\n📋 Checking 'document_chunks' table (Support Bot)...")
        
        if not table_exists(cursor, 'document_chunks'):
            logger.info("  Creating 'document_chunks' table...")
            cursor.execute("""
                CREATE TABLE document_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file VARCHAR(200) NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_source ON document_chunks(source_file)")
            logger.info("  ✅ Created 'document_chunks' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'document_chunks' exists")
        
        logger.info("\n📋 Checking 'support_conversations' table...")
        
        if not table_exists(cursor, 'support_conversations'):
            logger.info("  Creating 'support_conversations' table...")
            cursor.execute("""
                CREATE TABLE support_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(100) UNIQUE NOT NULL,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    telegram_chat_id VARCHAR(50),
                    channel VARCHAR(20) DEFAULT 'web',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_resolved BOOLEAN DEFAULT 0
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_conv_session ON support_conversations(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_conv_user ON support_conversations(user_id)")
            logger.info("  ✅ Created 'support_conversations' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'support_conversations' exists")
        
        logger.info("\n📋 Checking 'support_messages' table...")
        
        if not table_exists(cursor, 'support_messages'):
            logger.info("  Creating 'support_messages' table...")
            cursor.execute("""
                CREATE TABLE support_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER REFERENCES support_conversations(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    confidence FLOAT,
                    sources TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_msg_conv ON support_messages(conversation_id, created_at)")
            logger.info("  ✅ Created 'support_messages' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'support_messages' exists")
        
        logger.info("\n📋 Checking 'support_tickets' table...")
        
        if not table_exists(cursor, 'support_tickets'):
            logger.info("  Creating 'support_tickets' table...")
            cursor.execute("""
                CREATE TABLE support_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER REFERENCES support_conversations(id) ON DELETE SET NULL,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    question TEXT NOT NULL,
                    ai_response TEXT,
                    confidence FLOAT,
                    status VARCHAR(20) DEFAULT 'open',
                    priority VARCHAR(20) DEFAULT 'normal',
                    assigned_to_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    admin_response TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    resolved_at DATETIME
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id)")
            logger.info("  ✅ Created 'support_tickets' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'support_tickets' exists")
        
        # ==================== TOURNAMENTS TABLE ====================
        logger.info("\n📋 Checking 'tournaments' table...")
        
        if not table_exists(cursor, 'tournaments'):
            logger.info("  Creating 'tournaments' table...")
            cursor.execute("""
                CREATE TABLE tournaments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    start_date DATETIME NOT NULL,
                    end_date DATETIME NOT NULL,
                    entry_fee REAL DEFAULT 10.0 NOT NULL,
                    prize_pool REAL DEFAULT 0.0 NOT NULL,
                    prize_1st_pct REAL DEFAULT 50.0,
                    prize_2nd_pct REAL DEFAULT 30.0,
                    prize_3rd_pct REAL DEFAULT 20.0,
                    min_participants INTEGER DEFAULT 3,
                    max_participants INTEGER,
                    status VARCHAR(20) DEFAULT 'upcoming',
                    winner_1st_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    winner_2nd_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    winner_3rd_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    finalized_at DATETIME
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_start ON tournaments(start_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_end ON tournaments(end_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_status_dates ON tournaments(status, start_date, end_date)")
            logger.info("  ✅ Created 'tournaments' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'tournaments' exists")
        
        # ==================== TOURNAMENT_PARTICIPANTS TABLE ====================
        logger.info("\n📋 Checking 'tournament_participants' table...")
        
        if not table_exists(cursor, 'tournament_participants'):
            logger.info("  Creating 'tournament_participants' table...")
            cursor.execute("""
                CREATE TABLE tournament_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    entry_fee_paid REAL DEFAULT 0.0,
                    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    starting_balance REAL DEFAULT 0.0,
                    current_balance REAL DEFAULT 0.0,
                    current_roi REAL DEFAULT 0.0,
                    trades_count INTEGER DEFAULT 0,
                    final_rank INTEGER,
                    prize_won REAL DEFAULT 0.0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tournament_id, user_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_tournament ON tournament_participants(tournament_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_user ON tournament_participants(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_roi ON tournament_participants(current_roi)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_tournament_roi ON tournament_participants(tournament_id, current_roi)")
            logger.info("  ✅ Created 'tournament_participants' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'tournament_participants' exists")
        
        # ==================== PROPOSALS TABLE (Governance) ====================
        logger.info("\n📋 Checking 'proposals' table (Governance)...")
        
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_category ON proposals(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_created_by ON proposals(created_by_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proposals_voting_ends ON proposals(voting_ends_at)")
            logger.info("  ✅ Created 'proposals' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'proposals' exists")
        
        # ==================== VOTES TABLE (Governance) ====================
        logger.info("\n📋 Checking 'votes' table (Governance)...")
        
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_proposal ON votes(proposal_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_created_at ON votes(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_proposal_type ON votes(proposal_id, vote_type)")
            logger.info("  ✅ Created 'votes' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'votes' exists")
        
        # ==================== USER_CONSENTS TABLE (Compliance - TOS Tracking) ====================
        logger.info("\n📋 Checking 'user_consents' table (Compliance)...")
        
        if not table_exists(cursor, 'user_consents'):
            logger.info("  Creating 'user_consents' table...")
            cursor.execute("""
                CREATE TABLE user_consents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    tos_version VARCHAR(20) NOT NULL,
                    accepted_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    ip_address VARCHAR(45),
                    user_agent VARCHAR(512),
                    consent_type VARCHAR(50) DEFAULT 'tos_and_risk_disclaimer'
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_consents_user_id ON user_consents(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_consents_tos_version ON user_consents(tos_version)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_consents_accepted_at ON user_consents(accepted_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_consent_user_version ON user_consents(user_id, tos_version)")
            logger.info("  ✅ Created 'user_consents' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'user_consents' exists")
        
        # ==================== SYSTEM_SETTINGS TABLE ====================
        logger.info("\n📋 Checking 'system_settings' table (Service Configuration)...")
        
        if not table_exists(cursor, 'system_settings'):
            logger.info("  Creating 'system_settings' table...")
            cursor.execute("""
                CREATE TABLE system_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category VARCHAR(50) NOT NULL,
                    key VARCHAR(100) NOT NULL,
                    value TEXT,
                    value_encrypted TEXT,
                    is_sensitive BOOLEAN DEFAULT 0,
                    is_enabled BOOLEAN DEFAULT 1,
                    description VARCHAR(500),
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    UNIQUE(category, key)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_settings_category ON system_settings(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_settings_key ON system_settings(key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_settings_category_key ON system_settings(category, key)")
            logger.info("  ✅ Created 'system_settings' table")
            changes_made += 1
        else:
            logger.info("  ✓ Table 'system_settings' exists")
        
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
                SET current_level_id = ?, xp = COALESCE(xp, 0), discount_percent = 0.0
                WHERE current_level_id IS NULL AND role = 'user'
            """, (novice_id,))
            logger.info("  ✅ Set default Novice level for users without a level")
        
        # Commit all changes
        conn.commit()
        
        logger.info("\n" + "=" * 60)
        if changes_made > 0:
            logger.info(f"✅ Migration complete! {changes_made} changes made.")
        else:
            logger.info("✅ Database is up to date. No changes needed.")
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


def create_indexes():
    """Create performance indexes after migration"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        return
    
    logger.info("\n📊 Creating performance indexes...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    indexes = [
        # User indexes
        "CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)",
        "CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_subscription_expires ON users(subscription_expires_at)",
        
        # Message indexes
        "CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)",
        
        # User exchanges indexes
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_user ON user_exchanges(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_status ON user_exchanges(status)",
        
        # Payment indexes
        "CREATE INDEX IF NOT EXISTS idx_payment_user_id ON payments(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_payment_status ON payments(status)",
        "CREATE INDEX IF NOT EXISTS idx_payment_provider_txn ON payments(provider_txn_id)",
        
        # Referral commission indexes
        "CREATE INDEX IF NOT EXISTS idx_commission_referrer ON referral_commissions(referrer_id)",
        "CREATE INDEX IF NOT EXISTS idx_commission_referred ON referral_commissions(referred_user_id)",
        
        # Strategy indexes
        "CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name)",
        "CREATE INDEX IF NOT EXISTS idx_strategies_is_active ON strategies(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_strategies_risk_level ON strategies(risk_level)",
        "CREATE INDEX IF NOT EXISTS idx_strategies_master_exchange ON strategies(master_exchange_id)",
        
        # Strategy subscription indexes
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON strategy_subscriptions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_strategy_id ON strategy_subscriptions(strategy_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_is_active ON strategy_subscriptions(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_active ON strategy_subscriptions(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_strategy_active ON strategy_subscriptions(strategy_id, is_active)",
        
        # Chat message indexes
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_room ON chat_messages(room)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_room_time ON chat_messages(room, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id)",
        
        # Chat ban indexes
        "CREATE INDEX IF NOT EXISTS idx_chat_bans_user ON chat_bans(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_bans_active ON chat_bans(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_chat_bans_user_active ON chat_bans(user_id, is_active)",
        
        # System stats indexes (Insurance Fund)
        "CREATE INDEX IF NOT EXISTS idx_system_stats_key ON system_stats(stat_key)",
        
        # User level indexes (Gamification)
        "CREATE INDEX IF NOT EXISTS idx_user_levels_name ON user_levels(name)",
        "CREATE INDEX IF NOT EXISTS idx_user_levels_min_xp ON user_levels(min_xp)",
        "CREATE INDEX IF NOT EXISTS idx_user_levels_order ON user_levels(order_rank)",
        
        # User achievement indexes (Gamification)
        "CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_achievements_type ON user_achievements(achievement_type)",
        "CREATE INDEX IF NOT EXISTS idx_achievements_unlocked ON user_achievements(unlocked_at)",
        
        # User gamification indexes
        "CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp)",
        "CREATE INDEX IF NOT EXISTS idx_users_level ON users(current_level_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_volume ON users(total_trading_volume)",
        
        # API keys indexes (Public Developer API)
        "CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(key)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user_active ON api_keys(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_expires ON api_keys(expires_at)",
        
        # Support Bot indexes (RAG)
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_source ON document_chunks(source_file)",
        "CREATE INDEX IF NOT EXISTS idx_support_conv_session ON support_conversations(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_support_conv_user ON support_conversations(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_support_conv_resolved ON support_conversations(is_resolved)",
        "CREATE INDEX IF NOT EXISTS idx_support_msg_conv ON support_messages(conversation_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_priority ON support_tickets(priority)",
        
        # Tournament indexes
        "CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status)",
        "CREATE INDEX IF NOT EXISTS idx_tournaments_start ON tournaments(start_date)",
        "CREATE INDEX IF NOT EXISTS idx_tournaments_end ON tournaments(end_date)",
        "CREATE INDEX IF NOT EXISTS idx_tournaments_status_dates ON tournaments(status, start_date, end_date)",
        "CREATE INDEX IF NOT EXISTS idx_participants_tournament ON tournament_participants(tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_participants_user ON tournament_participants(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_participants_roi ON tournament_participants(current_roi)",
        "CREATE INDEX IF NOT EXISTS idx_participants_tournament_roi ON tournament_participants(tournament_id, current_roi)",
        
        # Governance / Voting indexes
        "CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_category ON proposals(category)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_created_by ON proposals(created_by_id)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_voting_ends ON proposals(voting_ends_at)",
        "CREATE INDEX IF NOT EXISTS idx_votes_proposal ON votes(proposal_id)",
        "CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_votes_created_at ON votes(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_votes_proposal_type ON votes(proposal_id, vote_type)",
        
        # Compliance / TOS consent indexes
        "CREATE INDEX IF NOT EXISTS idx_user_consents_user_id ON user_consents(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_consents_tos_version ON user_consents(tos_version)",
        "CREATE INDEX IF NOT EXISTS idx_user_consents_accepted_at ON user_consents(accepted_at)",
        "CREATE INDEX IF NOT EXISTS idx_consent_user_version ON user_consents(user_id, tos_version)",
        
        # System settings indexes (Admin Service Configuration)
        "CREATE INDEX IF NOT EXISTS idx_system_settings_category ON system_settings(category)",
        "CREATE INDEX IF NOT EXISTS idx_system_settings_key ON system_settings(key)",
        "CREATE INDEX IF NOT EXISTS idx_system_settings_category_key ON system_settings(category, key)",
    ]
    
    try:
        for idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
            except sqlite3.OperationalError:
                pass  # Index might already exist or table doesn't exist
        
        conn.commit()
        logger.info("✅ Indexes created/verified")
    except Exception as e:
        logger.warning(f"⚠️ Some indexes may not have been created: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  MIMIC (Brain Capital) - COMPREHENSIVE Database Migration")
    print("=" * 60)
    print()
    print("This script will add ALL missing columns and tables:")
    print("  • User settings (risk multiplier, DCA, trailing SL)")
    print("  • Risk guardrails columns")
    print("  • Subscription system columns")
    print("  • Referral system columns")
    print("  • Multi-strategy system (strategies, strategy_subscriptions)")
    print("  • Live Chat system (chat_messages, chat_bans)")
    print("  • Insurance Fund / Safety Pool (system_stats)")
    print("  • Gamification system (user_levels, user_achievements)")
    print("  • Tournament system (tournaments, tournament_participants)")
    print("  • Governance/Voting system (proposals, votes)")
    print("  • Compliance/TOS consent tracking (user_consents)")
    print("  • Public API keys (api_keys)")
    print("  • RAG Support Bot (document_chunks, support_conversations, etc.)")
    print("  • System Settings (admin-configurable services: Telegram, Plisio, etc.)")
    print("  • All required tables (messages, payments, etc.)")
    print()
    
    success = migrate_database()
    
    if success:
        create_indexes()
        print()
        print("=" * 60)
        print("✅ You can now run the application: python app.py")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ Migration failed. Please check the errors above.")
        print("=" * 60)
        sys.exit(1)

