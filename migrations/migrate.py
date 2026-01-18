"""
Unified database migration script for MIMIC.

Consolidates schema updates, seed data, and index creation into one entrypoint.

Usage:
  python migrations/migrate.py
  python migrations/migrate.py --high-traffic
  python migrations/migrate.py --no-indexes
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from app import app, db
from sqlalchemy import inspect, text
from models import (
    ChatMessage,
    SystemSetting,
    SystemStats,
    Task,
    User,
    UserLevel,
    Strategy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Migration")


def get_db_type() -> str:
    return db.engine.dialect.name


def table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_column_if_missing(
    connection,
    inspector,
    db_type: str,
    table_name: str,
    column_name: str,
    sqlite_type: str,
    postgres_type: str,
    sqlite_default: str | None = None,
    postgres_default: str | None = None,
) -> bool:
    if not table_exists(inspector, table_name):
        return False
    if column_exists(inspector, table_name, column_name):
        logger.info("  ✓ Column %s.%s already exists", table_name, column_name)
        return False

    column_type = sqlite_type if db_type == "sqlite" else postgres_type
    default_value = sqlite_default if db_type == "sqlite" else postgres_default
    default_clause = f" DEFAULT {default_value}" if default_value is not None else ""
    sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}{default_clause}"

    try:
        connection.execute(text(sql))
        logger.info("  ✅ Added column %s.%s", table_name, column_name)
        return True
    except Exception as exc:
        logger.warning("  ⚠️ Failed to add %s.%s: %s", table_name, column_name, exc)
        return False


def apply_schema_updates(connection, db_type: str) -> int:
    changes = 0

    logger.info("📋 Ensuring tables exist...")
    db.create_all()

    inspector = inspect(db.engine)
    logger.info("📋 Ensuring columns exist on core tables...")
    user_columns = [
        # Google OAuth / WebAuthn columns (CRITICAL - must come first)
        ("google_sub", "VARCHAR(255)", "VARCHAR(255)", None, None),
        ("google_email_verified", "BOOLEAN", "BOOLEAN", "0", "FALSE"),
        ("auth_provider", "VARCHAR(20)", "VARCHAR(20)", "'local'", "'local'"),
        ("webauthn_enabled", "BOOLEAN", "BOOLEAN", "0", "FALSE"),
        # Other columns
        ("risk_multiplier", "REAL", "FLOAT", "1.0", "1.0"),
        ("referral_code", "VARCHAR(20)", "VARCHAR(20)", None, None),
        ("referred_by_id", "INTEGER", "INTEGER", None, None),
        ("target_balance", "REAL", "FLOAT", "1000.0", "1000.0"),
        ("telegram_enabled", "BOOLEAN", "BOOLEAN", "0", "FALSE"),
        ("telegram_chat_id", "VARCHAR(50)", "VARCHAR(50)", None, None),
        ("avatar", "VARCHAR(100)", "VARCHAR(100)", "'🧑‍💻'", "'🧑‍💻'"),
        ("avatar_type", "VARCHAR(20)", "VARCHAR(20)", "'emoji'", "'emoji'"),
        ("dca_enabled", "BOOLEAN", "BOOLEAN", "0", "FALSE"),
        ("dca_multiplier", "REAL", "FLOAT", "1.0", "1.0"),
        ("dca_threshold", "REAL", "FLOAT", "-2.0", "-2.0"),
        ("dca_max_orders", "INTEGER", "INTEGER", "3", "3"),
        ("trailing_sl_enabled", "BOOLEAN", "BOOLEAN", "0", "FALSE"),
        ("trailing_sl_activation", "REAL", "FLOAT", "1.0", "1.0"),
        ("trailing_sl_callback", "REAL", "FLOAT", "0.5", "0.5"),
        ("daily_drawdown_limit_perc", "REAL", "FLOAT", "10.0", "10.0"),
        ("daily_profit_target_perc", "REAL", "FLOAT", "20.0", "20.0"),
        ("risk_guardrails_enabled", "BOOLEAN", "BOOLEAN", "0", "FALSE"),
        ("risk_guardrails_paused_at", "DATETIME", "TIMESTAMP", None, None),
        ("risk_guardrails_reason", "VARCHAR(100)", "VARCHAR(100)", None, None),
        ("subscription_plan", "VARCHAR(50)", "VARCHAR(50)", "'free'", "'free'"),
        ("subscription_expires_at", "DATETIME", "TIMESTAMP", None, None),
        ("subscription_notified_expiring", "BOOLEAN", "BOOLEAN", "0", "FALSE"),
        ("xp", "INTEGER", "INTEGER", "0", "0"),
        ("current_level_id", "INTEGER", "INTEGER", None, None),
        ("discount_percent", "REAL", "FLOAT", "0.0", "0.0"),
        ("total_trading_volume", "REAL", "FLOAT", "0.0", "0.0"),
    ]

    for col in user_columns:
        if add_column_if_missing(connection, inspector, db_type, "users", *col):
            changes += 1

    trade_columns = [
        ("node_name", "VARCHAR(50)", "VARCHAR(50)", None, None),
    ]
    for col in trade_columns:
        if add_column_if_missing(connection, inspector, db_type, "trade_history", *col):
            changes += 1

    user_exchange_columns = [
        ("trading_enabled", "BOOLEAN", "BOOLEAN", "0", "FALSE"),
    ]
    for col in user_exchange_columns:
        if add_column_if_missing(connection, inspector, db_type, "user_exchanges", *col):
            changes += 1

    tournament_columns = [
        ("tasks", "TEXT", "JSON", "NULL", "NULL"),  # JSON array of tournament tasks/goals
    ]
    for col in tournament_columns:
        if add_column_if_missing(connection, inspector, db_type, "tournaments", *col):
            changes += 1

    push_columns = [
        ("error_count", "INTEGER", "INTEGER", "0", "0"),
        ("last_used_at", "DATETIME", "TIMESTAMP", None, None),
        ("language", "VARCHAR(10)", "VARCHAR(10)", "'en'", "'en'"),
    ]
    for col in push_columns:
        if add_column_if_missing(connection, inspector, db_type, "push_subscriptions", *col):
            changes += 1

    return changes


def seed_default_strategy() -> None:
    if not Strategy.query.filter_by(name="Main").first():
        strategy = Strategy(
            name="Main",
            description="Default trading strategy - follows the main master account",
            risk_level="medium",
            is_active=True,
        )
        db.session.add(strategy)
        db.session.commit()
        logger.info("  ✅ Created default 'Main' strategy")


def seed_user_levels() -> None:
    if UserLevel.query.first():
        return

    default_levels = [
        ("Novice", "fa-seedling", "#888888", 0, 1000, 0.0, 0, "Just getting started! Trade to earn XP and level up."),
        ("Amateur", "fa-user", "#4CAF50", 1000, 10000, 2.0, 1, "Building your skills! 2% commission discount."),
        ("Pro", "fa-chart-line", "#2196F3", 10000, 50000, 5.0, 2, "Proven trader! 5% commission discount."),
        ("Expert", "fa-star", "#9C27B0", 50000, 100000, 8.0, 3, "Top-tier performer! 8% commission discount."),
        ("Elite", "fa-crown", "#FFD700", 100000, None, 10.0, 4, "The best of the best! 10% commission discount."),
    ]

    for name, icon, color, min_xp, max_xp, discount, order_rank, desc in default_levels:
        level = UserLevel(
            name=name,
            icon=icon,
            color=color,
            min_xp=min_xp,
            max_xp=max_xp,
            discount_percent=discount,
            order_rank=order_rank,
            description=desc,
        )
        db.session.add(level)
    db.session.commit()
    logger.info("  ✅ Inserted default user levels")

    novice = UserLevel.query.filter_by(name="Novice").first()
    if novice:
        db.session.execute(
            text(
                """
                UPDATE users
                SET current_level_id = :level_id,
                    xp = COALESCE(xp, 0),
                    discount_percent = 0.0
                WHERE current_level_id IS NULL AND role = 'user'
                """
            ),
            {"level_id": novice.id},
        )
        db.session.commit()
        logger.info("  ✅ Set default Novice level for users without a level")


def seed_insurance_fund() -> None:
    if not SystemStats.query.filter_by(stat_key="insurance_fund_balance").first():
        stat = SystemStats(
            stat_key="insurance_fund_balance",
            stat_value=10000.0,
            description="Safety Pool - covers slippage losses in extreme market conditions",
        )
        db.session.add(stat)
        db.session.commit()
        logger.info("  ✅ Initialized Insurance Fund with $10,000 seed balance")


def seed_chat_welcome() -> None:
    if ChatMessage.query.first():
        return
    admin = User.query.filter_by(role="admin").first()
    if not admin:
        return
    welcome = ChatMessage(
        user_id=admin.id,
        room="general",
        message="🎉 Welcome to MIMIC Live Chat! Connect with fellow traders in real-time.",
        message_type="system",
        extra_data={"type": "welcome"},
    )
    db.session.add(welcome)
    db.session.commit()
    logger.info("  ✅ Created initial chat welcome message")


def seed_subscription_settings() -> None:
    settings = [
        {
            "category": "subscription",
            "key": "enabled",
            "value": "false",
            "is_sensitive": False,
            "description": "Enable/disable paid subscription requirement. When disabled, all users have free access.",
        },
        {
            "category": "subscription",
            "key": "auto_confirm",
            "value": "false",
            "is_sensitive": False,
            "description": "Automatically confirm payments after user marks as paid (risky - use only with trusted users)",
        },
        {
            "category": "subscription",
            "key": "confirm_timeout_hours",
            "value": "24",
            "is_sensitive": False,
            "description": "Hours to wait for admin to confirm payment before auto-expiring",
        },
        {
            "category": "subscription",
            "key": "default_days",
            "value": "30",
            "is_sensitive": False,
            "description": "Default subscription duration in days when manually activated",
        },
        {
            "category": "wallet",
            "key": "usdt_trc20",
            "value": "",
            "is_sensitive": False,
            "description": "USDT TRC20 (Tron) wallet address for receiving subscription payments",
        },
        {
            "category": "wallet",
            "key": "usdt_erc20",
            "value": "",
            "is_sensitive": False,
            "description": "USDT ERC20 (Ethereum) wallet address for receiving subscription payments",
        },
        {
            "category": "wallet",
            "key": "usdt_bep20",
            "value": "",
            "is_sensitive": False,
            "description": "USDT BEP20 (BSC) wallet address for receiving subscription payments",
        },
        {
            "category": "wallet",
            "key": "btc",
            "value": "",
            "is_sensitive": False,
            "description": "Bitcoin wallet address for receiving subscription payments",
        },
        {
            "category": "wallet",
            "key": "eth",
            "value": "",
            "is_sensitive": False,
            "description": "Ethereum wallet address for receiving subscription payments",
        },
        {
            "category": "wallet",
            "key": "ltc",
            "value": "",
            "is_sensitive": False,
            "description": "Litecoin wallet address for receiving subscription payments",
        },
        {
            "category": "wallet",
            "key": "sol",
            "value": "",
            "is_sensitive": False,
            "description": "Solana wallet address for receiving subscription payments",
        },
        {
            "category": "insurance_fund",
            "key": "wallet_address",
            "value": "",
            "is_sensitive": False,
            "description": "Wallet address for storing Insurance Fund (Safety Pool) funds",
        },
        {
            "category": "insurance_fund",
            "key": "wallet_network",
            "value": "USDT_TRC20",
            "is_sensitive": False,
            "description": "Network for Insurance Fund wallet (USDT_TRC20, USDT_ERC20, etc.)",
        },
        {
            "category": "insurance_fund",
            "key": "contribution_rate",
            "value": "5",
            "is_sensitive": False,
            "description": "Percentage of platform fees contributed to Insurance Fund",
        },
    ]

    created = 0
    updated = 0
    for setting_data in settings:
        existing = SystemSetting.query.filter_by(
            category=setting_data["category"],
            key=setting_data["key"],
        ).first()
        if existing:
            if existing.description != setting_data["description"]:
                existing.description = setting_data["description"]
                updated += 1
        else:
            new_setting = SystemSetting(
                category=setting_data["category"],
                key=setting_data["key"],
                is_sensitive=setting_data["is_sensitive"],
                description=setting_data["description"],
            )
            new_setting.set_value(setting_data["value"], setting_data["is_sensitive"])
            db.session.add(new_setting)
            created += 1

    if created or updated:
        db.session.commit()
        logger.info("  ✅ Subscription settings created: %s, updated: %s", created, updated)


def seed_task_samples() -> None:
    if Task.query.first():
        return

    admin = User.query.filter_by(role="admin").first()
    admin_id = admin.id if admin else None

    tasks = [
        Task(
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
            created_by_id=admin_id,
        ),
        Task(
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
            created_by_id=admin_id,
        ),
        Task(
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
            created_by_id=admin_id,
        ),
    ]

    db.session.add_all(tasks)
    db.session.commit()
    logger.info("  ✅ Created sample tasks")


def seed_defaults() -> None:
    logger.info("📋 Seeding default data...")
    seed_default_strategy()
    seed_user_levels()
    seed_insurance_fund()
    seed_chat_welcome()
    seed_subscription_settings()
    seed_task_samples()


def apply_core_indexes(connection) -> None:
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)",
        "CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_subscription_expires ON users(subscription_expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_user ON user_exchanges(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_status ON user_exchanges(status)",
        "CREATE INDEX IF NOT EXISTS idx_payment_user_id ON payments(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_payment_status ON payments(status)",
        "CREATE INDEX IF NOT EXISTS idx_payment_provider_txn ON payments(provider_txn_id)",
        "CREATE INDEX IF NOT EXISTS idx_commission_referrer ON referral_commissions(referrer_id)",
        "CREATE INDEX IF NOT EXISTS idx_commission_referred ON referral_commissions(referred_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name)",
        "CREATE INDEX IF NOT EXISTS idx_strategies_is_active ON strategies(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_strategies_risk_level ON strategies(risk_level)",
        "CREATE INDEX IF NOT EXISTS idx_strategies_master_exchange ON strategies(master_exchange_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON strategy_subscriptions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_strategy_id ON strategy_subscriptions(strategy_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_is_active ON strategy_subscriptions(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_active ON strategy_subscriptions(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_strategy_active ON strategy_subscriptions(strategy_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_room ON chat_messages(room)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_room_time ON chat_messages(room, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_bans_user ON chat_bans(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_bans_active ON chat_bans(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_chat_bans_user_active ON chat_bans(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_system_stats_key ON system_stats(stat_key)",
        "CREATE INDEX IF NOT EXISTS idx_user_levels_name ON user_levels(name)",
        "CREATE INDEX IF NOT EXISTS idx_user_levels_min_xp ON user_levels(min_xp)",
        "CREATE INDEX IF NOT EXISTS idx_user_levels_order ON user_levels(order_rank)",
        "CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_achievements_type ON user_achievements(achievement_type)",
        "CREATE INDEX IF NOT EXISTS idx_achievements_unlocked ON user_achievements(unlocked_at)",
        "CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp)",
        "CREATE INDEX IF NOT EXISTS idx_users_level ON users(current_level_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_volume ON users(total_trading_volume)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(key)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user_active ON api_keys(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_expires ON api_keys(expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_source ON document_chunks(source_file)",
        "CREATE INDEX IF NOT EXISTS idx_support_conv_session ON support_conversations(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_support_conv_user ON support_conversations(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_support_conv_resolved ON support_conversations(is_resolved)",
        "CREATE INDEX IF NOT EXISTS idx_support_msg_conv ON support_messages(conversation_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_priority ON support_tickets(priority)",
        "CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status)",
        "CREATE INDEX IF NOT EXISTS idx_tournaments_start ON tournaments(start_date)",
        "CREATE INDEX IF NOT EXISTS idx_tournaments_end ON tournaments(end_date)",
        "CREATE INDEX IF NOT EXISTS idx_tournaments_status_dates ON tournaments(status, start_date, end_date)",
        "CREATE INDEX IF NOT EXISTS idx_participants_tournament ON tournament_participants(tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_participants_user ON tournament_participants(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_participants_roi ON tournament_participants(current_roi)",
        "CREATE INDEX IF NOT EXISTS idx_participants_tournament_roi ON tournament_participants(tournament_id, current_roi)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_category ON proposals(category)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_created_by ON proposals(created_by_id)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_voting_ends ON proposals(voting_ends_at)",
        "CREATE INDEX IF NOT EXISTS idx_votes_proposal ON votes(proposal_id)",
        "CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_votes_created_at ON votes(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_votes_proposal_type ON votes(proposal_id, vote_type)",
        "CREATE INDEX IF NOT EXISTS idx_user_consents_user_id ON user_consents(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_consents_tos_version ON user_consents(tos_version)",
        "CREATE INDEX IF NOT EXISTS idx_user_consents_accepted_at ON user_consents(accepted_at)",
        "CREATE INDEX IF NOT EXISTS idx_consent_user_version ON user_consents(user_id, tos_version)",
        "CREATE INDEX IF NOT EXISTS idx_system_settings_category ON system_settings(category)",
        "CREATE INDEX IF NOT EXISTS idx_system_settings_key ON system_settings(key)",
        "CREATE INDEX IF NOT EXISTS idx_system_settings_category_key ON system_settings(category, key)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_users_is_paused ON users(is_paused)",
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_trade_history_user_id ON trade_history(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_trade_history_close_time ON trade_history(close_time)",
        "CREATE INDEX IF NOT EXISTS idx_trade_user_time ON trade_history(user_id, close_time)",
        "CREATE INDEX IF NOT EXISTS idx_trade_symbol_time ON trade_history(symbol, close_time)",
        "CREATE INDEX IF NOT EXISTS idx_balance_history_user_id ON balance_history(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_balance_history_timestamp ON balance_history(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_balance_user_time ON balance_history(user_id, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON messages(recipient_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_is_read ON messages(is_read)",
        "CREATE INDEX IF NOT EXISTS idx_messages_is_from_admin ON messages(is_from_admin)",
        "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_message_recipient_read ON messages(recipient_id, is_read)",
        "CREATE INDEX IF NOT EXISTS idx_message_sender_time ON messages(sender_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token)",
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_is_used ON password_reset_tokens(is_used)",
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_token_user_used ON password_reset_tokens(user_id, is_used)",
        "CREATE INDEX IF NOT EXISTS idx_token_expires ON password_reset_tokens(expires_at, is_used)",
        "CREATE INDEX IF NOT EXISTS idx_exchange_configs_exchange_name ON exchange_configs(exchange_name)",
        "CREATE INDEX IF NOT EXISTS idx_exchange_configs_is_enabled ON exchange_configs(is_enabled)",
        "CREATE INDEX IF NOT EXISTS idx_exchange_configs_is_verified ON exchange_configs(is_verified)",
        "CREATE INDEX IF NOT EXISTS idx_exchange_enabled_verified ON exchange_configs(is_enabled, is_verified)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_exchange_name ON user_exchanges(exchange_name)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_is_active ON user_exchanges(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchanges_trading_enabled ON user_exchanges(trading_enabled)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchange_status ON user_exchanges(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_user_exchange_active ON user_exchanges(user_id, is_active, trading_enabled)",
    ]

    for idx_sql in indexes:
        try:
            connection.execute(text(idx_sql))
        except Exception:
            pass


def apply_high_traffic_indexes(connection, db_type: str) -> None:
    if db_type == "postgresql":
        indexes = [
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_close_time_desc ON trade_history (user_id, close_time DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_symbol_time ON trade_history (user_id, symbol, close_time DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_pnl ON trade_history (user_id, pnl) WHERE pnl IS NOT NULL",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_close_time_pnl ON trade_history (close_time DESC, pnl) WHERE pnl IS NOT NULL",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_symbol_pnl ON trade_history (symbol, close_time DESC, pnl)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_side_time ON trade_history (user_id, side, close_time DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_balance_history_user_timestamp_desc ON balance_history (user_id, timestamp DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_active_subscription ON users (is_active, subscription_expires_at DESC) WHERE is_active = true",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_subscription_expiring ON users (subscription_expires_at) WHERE subscription_expires_at IS NOT NULL AND is_active = true",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_referral_commissions_referrer_created ON referral_commissions (referrer_id, created_at DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_referral_commissions_pending ON referral_commissions (referrer_id, amount) WHERE is_paid = false",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_user_created_desc ON payments (user_id, created_at DESC)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_messages_room_created_desc ON chat_messages (room, created_at DESC) WHERE is_deleted = false",
        ]
    else:
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_trade_history_user_close_time_desc ON trade_history (user_id, close_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_user_symbol_time ON trade_history (user_id, symbol, close_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_user_pnl ON trade_history (user_id, pnl)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_close_time_pnl ON trade_history (close_time DESC, pnl)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_symbol_pnl ON trade_history (symbol, close_time, pnl)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_user_side_time ON trade_history (user_id, side, close_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_balance_history_user_timestamp_desc ON balance_history (user_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_balance_history_timestamp_user ON balance_history (timestamp DESC, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_active_subscription ON users (is_active, subscription_expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_referral_commissions_referrer_created ON referral_commissions (referrer_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_referral_commissions_pending ON referral_commissions (referrer_id, is_paid, amount)",
            "CREATE INDEX IF NOT EXISTS idx_payments_user_created_desc ON payments (user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_payments_status_created ON payments (status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_room_created_desc ON chat_messages (room, is_deleted, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_user_room_created ON chat_messages (user_id, room, created_at DESC)",
        ]

    for idx_sql in indexes:
        try:
            if db_type == "postgresql" and "CONCURRENTLY" in idx_sql:
                connection.execution_options(isolation_level="AUTOCOMMIT").execute(text(idx_sql))
            else:
                connection.execute(text(idx_sql))
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified database migration")
    parser.add_argument("--no-indexes", action="store_true", help="Skip index creation")
    parser.add_argument("--high-traffic", action="store_true", help="Add high-traffic indexes")
    args = parser.parse_args()

    with app.app_context():
        db_type = get_db_type()
        logger.info("📦 Database type: %s", db_type.upper())

        connection = db.engine.connect()
        try:
            changes = apply_schema_updates(connection, db_type)
            try:
                connection.commit()
            except Exception:
                pass
            seed_defaults()

            if not args.no_indexes:
                logger.info("📊 Creating indexes...")
                apply_core_indexes(connection)
                if args.high_traffic:
                    apply_high_traffic_indexes(connection, db_type)
                try:
                    connection.commit()
                except Exception:
                    pass

            if changes:
                logger.info("✅ Migration complete! %s schema changes applied.", changes)
            else:
                logger.info("✅ Database is up to date. No schema changes needed.")
            return 0
        finally:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
