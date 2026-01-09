-- =============================================================================
-- MIMIC/BRAIN CAPITAL - HIGH TRAFFIC DATABASE OPTIMIZATION
-- =============================================================================
-- SQL Migration Script for PostgreSQL
-- Optimizes trade_history and related tables for millions of records
--
-- Run with: psql -d your_database -f add_high_traffic_indexes.sql
-- Or via Python: python migrate_high_traffic_indexes.py
-- =============================================================================

-- Enable timing for performance analysis
\timing on

BEGIN;

-- =============================================================================
-- TRADE_HISTORY TABLE INDEXES (Critical for Dashboard Performance)
-- =============================================================================

-- Primary lookup: user's recent trades (Dashboard loading)
-- This is THE most important index for dashboard performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_close_time_desc 
    ON trade_history (user_id, close_time DESC);

-- Compound index for user + symbol + time (filtering by symbol)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_symbol_time 
    ON trade_history (user_id, symbol, close_time DESC);

-- PnL analysis queries (profitable/losing trades)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_pnl 
    ON trade_history (user_id, pnl) 
    WHERE pnl IS NOT NULL;

-- Index for leaderboard calculations (aggregating PnL)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_close_time_pnl 
    ON trade_history (close_time DESC, pnl) 
    WHERE pnl IS NOT NULL;

-- Symbol performance analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_symbol_pnl 
    ON trade_history (symbol, close_time DESC, pnl);

-- Side-based analysis (LONG vs SHORT performance)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_user_side_time 
    ON trade_history (user_id, side, close_time DESC);

-- Node-based analysis (which trading nodes perform best)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_history_node_time 
    ON trade_history (node_name, close_time DESC) 
    WHERE node_name IS NOT NULL;

-- =============================================================================
-- BALANCE_HISTORY TABLE INDEXES (Charts & Analytics)
-- =============================================================================

-- User balance over time (Balance chart)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_balance_history_user_timestamp_desc 
    ON balance_history (user_id, timestamp DESC);

-- Time-range queries for charts
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_balance_history_timestamp_user 
    ON balance_history (timestamp DESC, user_id);

-- =============================================================================
-- USERS TABLE INDEXES (Admin queries)
-- =============================================================================

-- Active users with subscription status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_active_subscription 
    ON users (is_active, subscription_expires_at DESC) 
    WHERE is_active = true;

-- Subscription expiring soon (for notifications)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_subscription_expiring 
    ON users (subscription_expires_at) 
    WHERE subscription_expires_at IS NOT NULL 
    AND is_active = true;

-- Referral lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_referral_code_lower 
    ON users (LOWER(referral_code)) 
    WHERE referral_code IS NOT NULL;

-- =============================================================================
-- REFERRAL_COMMISSIONS TABLE INDEXES
-- =============================================================================

-- Referrer's commissions (Referral dashboard)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_referral_commissions_referrer_created 
    ON referral_commissions (referrer_id, created_at DESC);

-- Pending payouts
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_referral_commissions_pending 
    ON referral_commissions (referrer_id, amount) 
    WHERE is_paid = false;

-- =============================================================================
-- PAYMENTS TABLE INDEXES
-- =============================================================================

-- User payment history
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_user_created_desc 
    ON payments (user_id, created_at DESC);

-- Pending payments (for admin)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_status_created 
    ON payments (status, created_at DESC) 
    WHERE status = 'pending';

-- =============================================================================
-- CHAT_MESSAGES TABLE INDEXES (High volume)
-- =============================================================================

-- Room messages with pagination
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_messages_room_created_desc 
    ON chat_messages (room, created_at DESC) 
    WHERE is_deleted = false;

-- User's messages
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_messages_user_room_created 
    ON chat_messages (user_id, room, created_at DESC);

-- =============================================================================
-- PUSH_SUBSCRIPTIONS TABLE INDEXES
-- =============================================================================

-- Active subscriptions by user
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_push_subscriptions_user_active 
    ON push_subscriptions (user_id) 
    WHERE is_active = true;

-- =============================================================================
-- STRATEGY_SUBSCRIPTIONS TABLE INDEXES
-- =============================================================================

-- Active strategy subscribers
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_strategy_subscriptions_strategy_active 
    ON strategy_subscriptions (strategy_id, allocation_percent) 
    WHERE is_active = true;

-- =============================================================================
-- TABLE STATISTICS UPDATE
-- =============================================================================

-- Update statistics for query optimizer
ANALYZE trade_history;
ANALYZE balance_history;
ANALYZE users;
ANALYZE referral_commissions;
ANALYZE payments;
ANALYZE chat_messages;
ANALYZE push_subscriptions;
ANALYZE strategy_subscriptions;

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Show all indexes on trade_history
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'trade_history'
ORDER BY indexname;

-- Show index sizes
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE tablename IN ('trade_history', 'balance_history', 'users')
ORDER BY pg_relation_size(indexrelid) DESC;

-- =============================================================================
-- MAINTENANCE RECOMMENDATIONS
-- =============================================================================
/*
For ongoing performance with millions of records:

1. VACUUM ANALYZE regularly (at least daily):
   VACUUM ANALYZE trade_history;
   VACUUM ANALYZE balance_history;

2. Consider table partitioning for trade_history by month:
   CREATE TABLE trade_history_y2026m01 PARTITION OF trade_history
   FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

3. Archive old data (older than 1 year):
   INSERT INTO trade_history_archive 
   SELECT * FROM trade_history WHERE close_time < NOW() - INTERVAL '1 year';
   DELETE FROM trade_history WHERE close_time < NOW() - INTERVAL '1 year';

4. Monitor slow queries:
   SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

5. Enable auto-vacuum tuning in postgresql.conf:
   autovacuum_vacuum_scale_factor = 0.05
   autovacuum_analyze_scale_factor = 0.02
*/
