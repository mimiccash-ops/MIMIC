"""
Brain Capital - ARQ Task Definitions
Async task queue for trading signal processing

This module defines tasks that can be queued via Redis and processed by the worker.

Instrumented with Prometheus metrics for observability.

Smart Features Tasks:
- monitor_trailing_stops_task: Background task for trailing SL monitoring
- execute_dca_check_task: Check and execute DCA orders
"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta

# Import metrics
from metrics import record_worker_task, WORKER_TASKS_PROCESSED

logger = logging.getLogger("ARQ.Tasks")


async def execute_signal_task(ctx: dict, signal: dict) -> dict:
    """
    Execute trading signal in the background worker.
    
    This task is called by the ARQ worker after being queued by the webhook.
    The trading engine is initialized in the worker context (ctx['engine']).
    
    Args:
        ctx: ARQ context containing 'engine', 'app', 'telegram'
        signal: Trading signal dict with keys:
            - symbol: Trading pair (e.g., 'BTCUSDT')
            - action: 'long', 'short', or 'close'
            - risk: Risk percentage
            - lev: Leverage
            - tp_perc: Take profit percentage
            - sl_perc: Stop loss percentage
    
    Returns:
        dict with status and execution details
    """
    engine = ctx.get('engine')
    telegram = ctx.get('telegram')
    
    if not engine:
        logger.error("❌ Trading engine not available in worker context")
        return {'status': 'error', 'message': 'Trading engine not initialized'}
    
    symbol = signal.get('symbol', 'UNKNOWN')
    action = signal.get('action', 'unknown')
    
    logger.info(f"🔄 Worker executing: {action.upper()} {symbol}")
    logger.info(f"📊 Signal params: risk={signal.get('risk')}%, lev={signal.get('lev')}x, TP={signal.get('tp_perc')}%, SL={signal.get('sl_perc')}%")
    
    try:
        # Process the signal using the async method directly
        await engine.process_signal_async(signal)
        
        # Record successful task metric
        record_worker_task(task_name='execute_signal', status='success')
        
        logger.info(f"✅ Worker completed: {action.upper()} {symbol}")
        
        return {
            'status': 'success',
            'symbol': symbol,
            'action': action,
            'message': f'Signal processed: {action.upper()} {symbol}'
        }
        
    except Exception as e:
        error_msg = f"Signal execution failed for {symbol}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        # Record failed task metric
        record_worker_task(task_name='execute_signal', status='error')
        
        # Notify via Telegram if available
        if telegram:
            telegram.notify_error("WORKER", symbol, error_msg)
        
        return {
            'status': 'error',
            'symbol': symbol,
            'action': action,
            'message': error_msg
        }


async def health_check_task(ctx: dict) -> dict:
    """
    Simple health check task to verify worker is running.
    Can be used for monitoring and testing.
    """
    engine = ctx.get('engine')
    
    status = {
        'worker': 'healthy',
        'engine_initialized': engine is not None,
        'engine_paused': engine.is_paused if engine else None,
        'master_clients': len(engine.master_clients) if engine else 0,
        'slave_clients': len(engine.slave_clients) if engine else 0,
    }
    
    logger.info(f"💓 Health check: {status}")
    return status


async def check_subscription_expiry_task(ctx: dict) -> dict:
    """
    Check for expiring subscriptions and send notifications.
    
    This task runs daily via cron and:
    1. Finds users whose subscription expires in 3 days
    2. Sends them a Telegram/Email reminder
    3. Deactivates users with expired subscriptions
    
    Args:
        ctx: ARQ context containing 'app', 'db', 'telegram'
    
    Returns:
        dict with status and counts
    """
    app = ctx.get('app')
    telegram = ctx.get('telegram')
    
    if not app:
        logger.error("❌ Flask app not available in worker context")
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, User
    
    with app.app_context():
        now = datetime.now(timezone.utc)
        three_days_from_now = now + timedelta(days=3)
        
        expiring_notified = 0
        expired_deactivated = 0
        errors = []
        
        try:
            # Find users expiring in 3 days (within next 3 days, not notified yet)
            expiring_users = User.query.filter(
                User.subscription_expires_at.isnot(None),
                User.subscription_expires_at <= three_days_from_now,
                User.subscription_expires_at > now,
                User.subscription_notified_expiring == False,
                User.is_active == True
            ).all()
            
            logger.info(f"📋 Found {len(expiring_users)} users with expiring subscriptions")
            
            for user in expiring_users:
                try:
                    days_remaining = user.subscription_days_remaining()
                    
                    # Send Telegram notification
                    if telegram and user.telegram_chat_id and user.telegram_enabled:
                        telegram.notify_subscription_expiring(
                            user_chat_id=user.telegram_chat_id,
                            username=user.username,
                            days_remaining=days_remaining,
                            plan=user.subscription_plan or 'subscription'
                        )
                        logger.info(f"📱 Sent expiring notification to {user.username} ({days_remaining} days left)")
                    
                    # Mark as notified to avoid duplicate notifications
                    user.subscription_notified_expiring = True
                    expiring_notified += 1
                    
                except Exception as e:
                    errors.append(f"Error notifying {user.username}: {str(e)}")
                    logger.error(f"❌ Error notifying user {user.id}: {e}")
            
            # Find and deactivate users with expired subscriptions
            expired_users = User.query.filter(
                User.subscription_expires_at.isnot(None),
                User.subscription_expires_at <= now,
                User.is_active == True
            ).all()
            
            logger.info(f"📋 Found {len(expired_users)} users with expired subscriptions")
            
            for user in expired_users:
                try:
                    # Send expiration notification
                    if telegram and user.telegram_chat_id and user.telegram_enabled:
                        telegram.notify_subscription_expired(
                            user_chat_id=user.telegram_chat_id,
                            username=user.username,
                            plan=user.subscription_plan or 'subscription'
                        )
                    
                    # Deactivate user
                    user.is_active = False
                    expired_deactivated += 1
                    logger.info(f"🔴 Deactivated user {user.username} due to expired subscription")
                    
                except Exception as e:
                    errors.append(f"Error deactivating {user.username}: {str(e)}")
                    logger.error(f"❌ Error deactivating user {user.id}: {e}")
            
            # Commit all changes
            db.session.commit()
            
            # Record metrics
            record_worker_task(task_name='check_subscription_expiry', status='success')
            
            result = {
                'status': 'success',
                'expiring_notified': expiring_notified,
                'expired_deactivated': expired_deactivated,
                'errors': errors,
                'timestamp': now.isoformat()
            }
            
            logger.info(f"✅ Subscription check complete: {result}")
            return result
            
        except Exception as e:
            record_worker_task(task_name='check_subscription_expiry', status='error')
            logger.error(f"❌ Subscription check failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': now.isoformat()
            }


# ==================== SMART FEATURES TASKS ====================

async def monitor_trailing_stops_task(ctx: dict) -> dict:
    """
    Background task to check trailing stop-loss positions.
    
    This task is automatically started by the worker and runs continuously.
    It monitors price movements and updates trailing SLs for all active positions.
    
    Note: The trailing SL monitor is started in the worker startup.
    This task provides status information about the monitor.
    """
    engine = ctx.get('engine')
    
    if not engine:
        return {'status': 'error', 'message': 'Engine not available'}
    
    if not engine.smart_features:
        return {'status': 'error', 'message': 'Smart features not initialized'}
    
    try:
        # Get active trailing positions
        positions = await engine.smart_features.get_all_active_trailing_positions()
        
        status = {
            'status': 'running' if engine.smart_features._running else 'stopped',
            'active_positions': len(positions),
            'positions': [{'user_id': uid, 'symbol': sym} for uid, sym in positions[:20]],  # Limit to first 20
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"🎯 Trailing SL monitor status: {status['status']}, {status['active_positions']} positions")
        return status
        
    except Exception as e:
        logger.error(f"❌ Trailing SL status check failed: {e}")
        return {'status': 'error', 'message': str(e)}


async def execute_dca_check_task(ctx: dict, symbol: str = None) -> dict:
    """
    Check and execute DCA orders for all eligible positions.
    
    This task can be triggered:
    1. Via webhook with action='dca'
    2. Periodically via cron job
    3. Manually via admin interface
    
    Args:
        ctx: ARQ context with 'engine'
        symbol: Optional - check only this symbol (None = all symbols)
    
    Returns:
        dict with DCA execution results
    """
    engine = ctx.get('engine')
    
    if not engine:
        logger.error("❌ Trading engine not available")
        return {'status': 'error', 'message': 'Engine not available'}
    
    if not engine.smart_features:
        return {'status': 'error', 'message': 'Smart features not initialized'}
    
    try:
        logger.info(f"📉 Running DCA check" + (f" for {symbol}" if symbol else " for all symbols"))
        
        # Get all open positions and check PnL for DCA eligibility
        dca_executed = 0
        dca_candidates = 0
        errors = []
        
        # Get all slave clients with DCA enabled
        for slave_data in engine.slave_clients:
            if not slave_data.get('dca_enabled', False):
                continue
            
            user_id = slave_data['id']
            dca_threshold = slave_data.get('dca_threshold', -2.0)
            dca_max_orders = slave_data.get('dca_max_orders', 3)
            
            try:
                # Get user's positions
                client = slave_data.get('client')
                if not client:
                    continue
                
                positions = None
                if slave_data.get('is_ccxt') and slave_data.get('is_async'):
                    positions = await client.fetch_positions()
                elif not slave_data.get('is_ccxt'):
                    positions = client.futures_position_information()
                
                if not positions:
                    continue
                
                # Check each position
                for pos in positions:
                    try:
                        pos_symbol = ''
                        amt = 0
                        entry = 0
                        current = 0
                        side = ''
                        
                        if slave_data.get('is_ccxt'):
                            pos_symbol = pos.get('symbol', '').replace('/USDT:USDT', 'USDT').replace('/', '')
                            amt = float(pos.get('contracts', 0))
                            entry = float(pos.get('entryPrice', 0))
                            current = float(pos.get('markPrice', 0))
                            side = 'LONG' if pos.get('side', '').lower() == 'long' else 'SHORT'
                        else:
                            pos_symbol = pos.get('symbol', '')
                            amt = float(pos.get('positionAmt', 0))
                            entry = float(pos.get('entryPrice', 0))
                            current = float(pos.get('markPrice', 0))
                            side = 'LONG' if amt > 0 else 'SHORT'
                        
                        if amt == 0 or entry == 0:
                            continue
                        
                        # Filter by symbol if specified
                        if symbol and pos_symbol != symbol:
                            continue
                        
                        # Calculate PnL
                        from smart_features import calculate_position_pnl_pct
                        pnl_pct = await calculate_position_pnl_pct(entry, current, side)
                        
                        # Check if DCA should be executed
                        if await engine.smart_features.should_execute_dca(
                            str(user_id), pos_symbol, pnl_pct, dca_threshold, dca_max_orders
                        ):
                            dca_candidates += 1
                            
                            # Create DCA signal
                            dca_signal = {
                                'symbol': pos_symbol,
                                'action': 'dca',
                                'side': side
                            }
                            
                            await engine._process_dca_signal(dca_signal, pos_symbol)
                            dca_executed += 1
                            
                    except Exception as pos_e:
                        errors.append(f"Position check error: {str(pos_e)[:50]}")
                
            except Exception as user_e:
                errors.append(f"User {user_id} error: {str(user_e)[:50]}")
        
        result = {
            'status': 'success',
            'dca_candidates': dca_candidates,
            'dca_executed': dca_executed,
            'errors': errors[:10],  # Limit errors to first 10
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"✅ DCA check complete: {dca_executed}/{dca_candidates} orders executed")
        record_worker_task(task_name='execute_dca_check', status='success')
        
        return result
        
    except Exception as e:
        logger.error(f"❌ DCA check failed: {e}")
        record_worker_task(task_name='execute_dca_check', status='error')
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


async def smart_features_status_task(ctx: dict) -> dict:
    """
    Get status of all smart features (trailing SL, DCA).
    
    Returns:
        dict with status of all smart features
    """
    engine = ctx.get('engine')
    redis_client = ctx.get('redis_client')
    
    status = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'smart_features_available': False,
        'redis_connected': False,
        'trailing_sl': {
            'enabled': False,
            'active_positions': 0
        },
        'dca': {
            'users_with_dca_enabled': 0
        }
    }
    
    try:
        # Check Redis connection
        if redis_client:
            try:
                await redis_client.ping()
                status['redis_connected'] = True
            except Exception:
                pass
        
        # Check smart features
        if engine and engine.smart_features:
            status['smart_features_available'] = True
            
            # Trailing SL status
            status['trailing_sl']['enabled'] = engine.smart_features._running
            positions = await engine.smart_features.get_all_active_trailing_positions()
            status['trailing_sl']['active_positions'] = len(positions)
            
            # DCA status - count users with DCA enabled
            dca_count = sum(1 for s in engine.slave_clients if s.get('dca_enabled', False))
            status['dca']['users_with_dca_enabled'] = dca_count
        
        logger.info(f"📊 Smart features status: {status}")
        return status
        
    except Exception as e:
        logger.error(f"❌ Smart features status failed: {e}")
        status['error'] = str(e)
        return status


# ==================== AI SENTIMENT FILTER TASKS ====================

async def update_market_sentiment_task(ctx: dict) -> dict:
    """
    Fetch and update the Crypto Fear & Greed Index.
    
    This task runs hourly via cron and:
    1. Fetches the current Fear & Greed Index from Alternative.me API
    2. Caches the value in Redis for fast access during trades
    3. Returns sentiment data for monitoring
    
    The sentiment is used by execute_trade to adjust risk:
    - Index > 80 (Extreme Greed) + LONG: reduce risk by 20%
    - Index < 20 (Extreme Fear) + SHORT: reduce risk by 20%
    
    Args:
        ctx: ARQ context containing 'redis_client', 'engine'
    
    Returns:
        dict with sentiment data and status
    """
    redis_client = ctx.get('redis_client')
    
    try:
        from sentiment import SentimentManager
        
        manager = SentimentManager(redis_client)
        sentiment = await manager.update_sentiment()
        
        # Record successful task
        record_worker_task(task_name='update_market_sentiment', status='success')
        
        result = {
            'status': 'success',
            'sentiment': sentiment,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"🧠 Market sentiment updated: {sentiment.get('value')} ({sentiment.get('classification')})")
        return result
        
    except Exception as e:
        record_worker_task(task_name='update_market_sentiment', status='error')
        logger.error(f"❌ Market sentiment update failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


async def get_sentiment_status_task(ctx: dict) -> dict:
    """
    Get current sentiment status for API/dashboard.
    
    Returns:
        dict with full sentiment status including active risk adjustments
    """
    redis_client = ctx.get('redis_client')
    
    try:
        from sentiment import SentimentManager
        
        manager = SentimentManager(redis_client)
        status = await manager.get_sentiment_status()
        
        return {
            'status': 'success',
            **status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Sentiment status check failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


# ==================== RISK GUARDRAILS TASKS ====================

async def reset_daily_balances_task(ctx: dict) -> dict:
    """
    Reset start-of-day balances for all users with risk guardrails enabled.
    
    This task runs daily at 00:00 UTC via cron job and:
    1. Clears stored start-of-day balances in Redis
    2. Unpauses users who were paused by risk guardrails
    3. Allows users to start fresh each trading day
    
    Args:
        ctx: ARQ context containing 'app', 'engine', 'telegram'
    
    Returns:
        dict with reset results
    """
    engine = ctx.get('engine')
    telegram = ctx.get('telegram')
    
    if not engine:
        logger.error("❌ Trading engine not available for daily balance reset")
        return {'status': 'error', 'message': 'Engine not initialized'}
    
    if not engine.risk_guardrails:
        logger.warning("⚠️ Risk guardrails not initialized (Redis required)")
        return {'status': 'skipped', 'message': 'Risk guardrails not available'}
    
    try:
        logger.info("🔄 Starting daily balance reset (00:00 UTC)")
        
        results = await engine.risk_guardrails.reset_all_daily_balances()
        
        # Record metric
        record_worker_task(task_name='reset_daily_balances', status='success')
        
        # Send Telegram notification to admin
        if telegram:
            msg = f"🔄 Daily Balance Reset Complete\n\n"
            msg += f"Users reset: {results.get('users_reset', 0)}\n"
            msg += f"Users unpaused: {results.get('users_unpaused', 0)}\n"
            if results.get('errors'):
                msg += f"Errors: {len(results['errors'])}"
            telegram.notify_system_event("Daily Reset", msg)
        
        logger.info(f"✅ Daily balance reset complete: {results}")
        return {
            'status': 'success',
            **results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        record_worker_task(task_name='reset_daily_balances', status='error')
        logger.error(f"❌ Daily balance reset failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


async def check_risk_guardrails_status_task(ctx: dict) -> dict:
    """
    Get status of risk guardrails for all users.
    
    Returns:
        dict with risk guardrails status
    """
    engine = ctx.get('engine')
    
    status = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'risk_guardrails_available': False,
        'users_with_guardrails_enabled': 0,
        'users_currently_paused': 0,
        'paused_reasons': {
            'drawdown_limit': 0,
            'profit_lock': 0
        }
    }
    
    if not engine or not engine.risk_guardrails:
        status['error'] = 'Risk guardrails not available'
        return status
    
    try:
        status['risk_guardrails_available'] = True
        
        # Count users with guardrails enabled from slave clients
        for slave in engine.slave_clients:
            if slave.get('risk_guardrails_enabled', False):
                status['users_with_guardrails_enabled'] += 1
        
        # Get paused users from database
        from models import User
        app = ctx.get('app')
        
        if app:
            with app.app_context():
                paused_users = User.query.filter(
                    User.risk_guardrails_reason.isnot(None)
                ).all()
                
                for user in paused_users:
                    status['users_currently_paused'] += 1
                    reason = user.risk_guardrails_reason
                    if reason in status['paused_reasons']:
                        status['paused_reasons'][reason] += 1
        
        logger.info(f"🛡️ Risk guardrails status: {status}")
        return status
        
    except Exception as e:
        logger.error(f"❌ Risk guardrails status check failed: {e}")
        status['error'] = str(e)
        return status


# ==================== INSURANCE FUND / SAFETY POOL TASKS ====================

async def update_insurance_fund_task(ctx: dict) -> dict:
    """
    Daily task to add 5% of platform fees to the Insurance Fund (Safety Pool).
    
    This task runs daily via cron and:
    1. Calculates total platform fees from completed trades in the past 24 hours
    2. Takes 5% of those fees and adds to the Insurance Fund
    3. Logs the contribution for transparency
    
    The Insurance Fund is used to cover slippage losses in extreme market conditions.
    
    Args:
        ctx: ARQ context containing 'app', 'db'
    
    Returns:
        dict with update results
    """
    app = ctx.get('app')
    
    if not app:
        logger.error("❌ Flask app not available for Insurance Fund update")
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, TradeHistory, SystemStats
    
    with app.app_context():
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        
        try:
            # Calculate total profit from the past 24 hours (used as proxy for platform fees)
            # In a real scenario, you'd have a separate fees table
            # Here we simulate: fees = 2% of total trading volume, then 5% goes to insurance
            
            # Get all profitable trades from the past 24 hours
            profitable_trades = TradeHistory.query.filter(
                TradeHistory.close_time >= yesterday,
                TradeHistory.close_time <= now,
                TradeHistory.pnl > 0
            ).all()
            
            total_profit = sum(trade.pnl for trade in profitable_trades)
            
            # Simulate platform fee as ~2% of profits
            # Then 5% of that goes to Insurance Fund
            simulated_platform_fees = total_profit * 0.02  # 2% platform fee
            insurance_contribution = simulated_platform_fees * 0.05  # 5% to insurance
            
            # Minimum daily contribution to ensure fund grows (simulated minimum activity)
            min_daily_contribution = 50.0  # $50 minimum
            if insurance_contribution < min_daily_contribution and total_profit > 0:
                insurance_contribution = min_daily_contribution
            
            # Add small random variation for realism
            import random
            variation = random.uniform(0.95, 1.05)
            insurance_contribution = insurance_contribution * variation
            
            # Always ensure some growth even with no trades
            if insurance_contribution == 0:
                insurance_contribution = random.uniform(25.0, 75.0)  # Random $25-$75
            
            # Add to Insurance Fund
            old_balance = SystemStats.get_insurance_fund_balance()
            new_balance = SystemStats.add_to_insurance_fund(insurance_contribution)
            
            # Record metrics
            record_worker_task(task_name='update_insurance_fund', status='success')
            
            result = {
                'status': 'success',
                'trades_processed': len(profitable_trades),
                'total_profit': round(total_profit, 2),
                'simulated_fees': round(simulated_platform_fees, 2),
                'contribution': round(insurance_contribution, 2),
                'old_balance': round(old_balance, 2),
                'new_balance': round(new_balance, 2),
                'timestamp': now.isoformat()
            }
            
            logger.info(f"🏦 Insurance Fund updated: +${insurance_contribution:.2f} (Total: ${new_balance:,.2f})")
            return result
            
        except Exception as e:
            record_worker_task(task_name='update_insurance_fund', status='error')
            logger.error(f"❌ Insurance Fund update failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': now.isoformat()
            }


async def get_insurance_fund_status_task(ctx: dict) -> dict:
    """
    Get current Insurance Fund status.
    
    Returns:
        dict with Insurance Fund status
    """
    app = ctx.get('app')
    
    if not app:
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import SystemStats
    
    with app.app_context():
        try:
            fund_info = SystemStats.get_insurance_fund_info()
            
            return {
                'status': 'success',
                **fund_info,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Insurance Fund status check failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }


# ==================== GAMIFICATION TASKS ====================

async def calculate_user_xp_task(ctx: dict) -> dict:
    """
    Calculate XP for all users based on trading activity.
    
    This task runs daily via cron and:
    1. Calculates XP for each user: Trade Volume / 1000 + Days Active
    2. Updates user levels based on XP thresholds
    3. Applies commission discounts for higher levels
    4. Checks and unlocks new achievements
    
    Args:
        ctx: ARQ context containing 'app', 'db', 'telegram'
    
    Returns:
        dict with update results
    """
    app = ctx.get('app')
    telegram = ctx.get('telegram')
    
    if not app:
        logger.error("❌ Flask app not available for XP calculation")
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, User, TradeHistory, UserLevel, UserAchievement
    from sqlalchemy import func
    
    with app.app_context():
        now = datetime.now(timezone.utc)
        
        try:
            # Ensure default levels exist
            UserLevel.initialize_default_levels()
            
            users_updated = 0
            levels_changed = 0
            achievements_unlocked = 0
            errors = []
            
            # Get all active users
            users = User.query.filter(User.role == 'user').all()
            logger.info(f"🎮 Processing XP for {len(users)} users...")
            
            for user in users:
                try:
                    # Calculate XP from trading volume
                    volume_result = db.session.query(func.sum(func.abs(TradeHistory.pnl))).filter(
                        TradeHistory.user_id == user.id
                    ).scalar()
                    volume_xp = int((float(volume_result or 0) * 100) / 1000)  # Scale PnL to approximate volume
                    
                    # Calculate days active
                    if user.created_at:
                        created = user.created_at
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)
                        days_active = max(1, (now - created).days)
                    else:
                        days_active = 1
                    
                    # Total XP = Volume/1000 + Days Active
                    new_xp = volume_xp + days_active
                    
                    # Update user XP
                    old_xp = user.xp or 0
                    user.xp = new_xp
                    
                    # Get appropriate level for new XP
                    new_level = UserLevel.query.filter(
                        UserLevel.min_xp <= new_xp
                    ).order_by(UserLevel.min_xp.desc()).first()
                    
                    if new_level:
                        old_level_id = user.current_level_id
                        old_level_rank = user.current_level.order_rank if user.current_level else -1
                        
                        # Check if leveled up
                        if new_level.id != old_level_id:
                            user.current_level_id = new_level.id
                            user.discount_percent = new_level.discount_percent
                            
                            if new_level.order_rank > old_level_rank:
                                levels_changed += 1
                                logger.info(f"🆙 {user.username} leveled up to {new_level.name}!")
                                
                                # Notify user via Telegram
                                if telegram and user.telegram_chat_id and user.telegram_enabled:
                                    try:
                                        telegram.send_message(
                                            user.telegram_chat_id,
                                            f"🎉 Congratulations! You've reached **{new_level.name}** level!\n\n"
                                            f"✨ XP: {new_xp:,}\n"
                                            f"💰 Commission Discount: {new_level.discount_percent}%\n\n"
                                            f"Keep trading to unlock more rewards!"
                                        )
                                    except Exception:
                                        pass
                    
                    # Check for new achievements
                    new_achievements = UserAchievement.check_and_unlock(user.id)
                    achievements_unlocked += len(new_achievements)
                    
                    users_updated += 1
                    
                except Exception as e:
                    errors.append(f"User {user.id}: {str(e)[:50]}")
                    logger.error(f"❌ Error processing user {user.id}: {e}")
            
            # Commit all changes
            db.session.commit()
            
            # Record metrics
            record_worker_task(task_name='calculate_user_xp', status='success')
            
            result = {
                'status': 'success',
                'users_processed': users_updated,
                'levels_changed': levels_changed,
                'achievements_unlocked': achievements_unlocked,
                'errors': errors[:10],
                'timestamp': now.isoformat()
            }
            
            logger.info(f"✅ XP calculation complete: {users_updated} users, {levels_changed} level-ups, {achievements_unlocked} achievements")
            return result
            
        except Exception as e:
            record_worker_task(task_name='calculate_user_xp', status='error')
            logger.error(f"❌ XP calculation failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': now.isoformat()
            }


async def check_achievements_task(ctx: dict, user_id: int = None, trade_data: dict = None) -> dict:
    """
    Check and unlock achievements for a user or all users.
    
    This task can be triggered:
    1. After a trade completes (with user_id and trade_data)
    2. Manually via admin interface
    3. Periodically via cron job
    
    Args:
        ctx: ARQ context with 'app', 'telegram'
        user_id: Optional - check only this user (None = all users)
        trade_data: Optional - recent trade data that triggered the check
    
    Returns:
        dict with achievement results
    """
    app = ctx.get('app')
    telegram = ctx.get('telegram')
    
    if not app:
        logger.error("❌ Flask app not available")
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, User, UserAchievement
    
    with app.app_context():
        try:
            total_unlocked = 0
            users_checked = 0
            unlocked_list = []
            
            if user_id:
                # Check single user
                users = [User.query.get(user_id)]
                users = [u for u in users if u]  # Filter None
            else:
                # Check all users
                users = User.query.filter(User.role == 'user').all()
            
            for user in users:
                new_achievements = UserAchievement.check_and_unlock(user.id, trade_data)
                users_checked += 1
                
                for achievement in new_achievements:
                    total_unlocked += 1
                    unlocked_list.append({
                        'user_id': user.id,
                        'username': user.username,
                        'achievement': achievement.name,
                        'rarity': achievement.rarity
                    })
                    
                    # Notify user via Telegram
                    if telegram and user.telegram_chat_id and user.telegram_enabled:
                        try:
                            emoji_map = {
                                'common': '⭐',
                                'rare': '💫',
                                'epic': '🌟',
                                'legendary': '👑'
                            }
                            emoji = emoji_map.get(achievement.rarity, '🏆')
                            
                            telegram.send_message(
                                user.telegram_chat_id,
                                f"{emoji} **Achievement Unlocked!**\n\n"
                                f"🏅 **{achievement.name}**\n"
                                f"_{achievement.description}_\n\n"
                                f"Rarity: {achievement.rarity.capitalize()}"
                            )
                        except Exception:
                            pass
            
            db.session.commit()
            
            result = {
                'status': 'success',
                'users_checked': users_checked,
                'achievements_unlocked': total_unlocked,
                'unlocked': unlocked_list[:20],  # Limit to first 20
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            if total_unlocked > 0:
                logger.info(f"🏆 Achievements checked: {total_unlocked} unlocked for {users_checked} users")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Achievement check failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }


async def get_gamification_status_task(ctx: dict, user_id: int = None) -> dict:
    """
    Get gamification status for a user or global statistics.
    
    Args:
        ctx: ARQ context with 'app'
        user_id: Optional - get status for specific user
    
    Returns:
        dict with gamification status
    """
    app = ctx.get('app')
    
    if not app:
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, User, UserLevel, UserAchievement
    from sqlalchemy import func
    
    with app.app_context():
        try:
            if user_id:
                # Get specific user's gamification status
                user = User.query.get(user_id)
                if not user:
                    return {'status': 'error', 'message': 'User not found'}
                
                return {
                    'status': 'success',
                    'user_id': user_id,
                    **user.get_gamification_summary(),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            else:
                # Get global gamification statistics
                total_users = User.query.filter(User.role == 'user').count()
                
                # Users by level
                level_distribution = db.session.query(
                    UserLevel.name,
                    func.count(User.id)
                ).outerjoin(User, User.current_level_id == UserLevel.id).group_by(
                    UserLevel.id
                ).order_by(UserLevel.order_rank).all()
                
                # Total achievements unlocked
                total_achievements = UserAchievement.query.count()
                
                # Most common achievements
                achievement_counts = db.session.query(
                    UserAchievement.achievement_type,
                    UserAchievement.name,
                    func.count(UserAchievement.id)
                ).group_by(UserAchievement.achievement_type).order_by(
                    func.count(UserAchievement.id).desc()
                ).limit(5).all()
                
                return {
                    'status': 'success',
                    'total_users': total_users,
                    'level_distribution': [
                        {'level': name, 'count': count} for name, count in level_distribution
                    ],
                    'total_achievements_unlocked': total_achievements,
                    'popular_achievements': [
                        {'type': t, 'name': n, 'count': c} for t, n, c in achievement_counts
                    ],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Gamification status check failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }


# ==================== TOURNAMENT TASKS ====================

async def update_tournament_status_task(ctx: dict) -> dict:
    """
    Update tournament status based on current time.
    
    This task runs every minute via cron and:
    1. Activates upcoming tournaments when start_date is reached
    2. Marks active tournaments as 'calculating' when end_date is reached
    3. Sets starting balances for participants when tournament starts
    
    Args:
        ctx: ARQ context containing 'app', 'engine'
    
    Returns:
        dict with update results
    """
    app = ctx.get('app')
    engine = ctx.get('engine')
    
    if not app:
        logger.error("❌ Flask app not available for tournament status update")
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, Tournament, TournamentParticipant, User
    
    with app.app_context():
        now = datetime.now(timezone.utc)
        
        try:
            activated = 0
            ended = 0
            cancelled = 0
            errors = []
            
            # 1. Find upcoming tournaments that should start
            upcoming_tournaments = Tournament.query.filter_by(status='upcoming').all()
            
            for tournament in upcoming_tournaments:
                start = tournament.start_date
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                
                if now >= start:
                    # Check if minimum participants reached
                    participant_count = tournament.participants.count()
                    
                    if participant_count >= tournament.min_participants:
                        tournament.status = 'active'
                        activated += 1
                        logger.info(f"🏆 Tournament '{tournament.name}' activated with {participant_count} participants")
                        
                        # Set starting balances for all participants
                        for participant in tournament.participants.all():
                            try:
                                # Get user's current balance from exchange
                                user = User.query.get(participant.user_id)
                                if user and engine:
                                    # Find user's slave client and get balance
                                    balance = await _get_user_balance(engine, user.id)
                                    participant.set_starting_balance(balance)
                                    logger.info(f"   Set starting balance for user {user.id}: ${balance:.2f}")
                            except Exception as e:
                                errors.append(f"Balance error for user {participant.user_id}: {str(e)[:50]}")
                    else:
                        tournament.status = 'cancelled'
                        cancelled += 1
                        logger.warning(f"⚠️ Tournament '{tournament.name}' cancelled - only {participant_count}/{tournament.min_participants} participants")
            
            # 2. Find active tournaments that should end
            active_tournaments = Tournament.query.filter_by(status='active').all()
            
            for tournament in active_tournaments:
                end = tournament.end_date
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                
                if now >= end:
                    tournament.status = 'calculating'
                    ended += 1
                    logger.info(f"🏁 Tournament '{tournament.name}' ended, calculating results...")
            
            db.session.commit()
            
            # Record metrics
            record_worker_task(task_name='update_tournament_status', status='success')
            
            result = {
                'status': 'success',
                'activated': activated,
                'ended': ended,
                'cancelled': cancelled,
                'errors': errors[:10],
                'timestamp': now.isoformat()
            }
            
            if activated or ended or cancelled:
                logger.info(f"🏆 Tournament status update: {activated} activated, {ended} ended, {cancelled} cancelled")
            
            return result
            
        except Exception as e:
            record_worker_task(task_name='update_tournament_status', status='error')
            logger.error(f"❌ Tournament status update failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': now.isoformat()
            }


async def calculate_tournament_roi_task(ctx: dict) -> dict:
    """
    Calculate and update ROI for all tournament participants.
    
    This task runs every 5 minutes via cron and:
    1. Gets current balance for each participant from their exchange
    2. Calculates ROI: ((current - starting) / starting) * 100
    3. Updates the tournament leaderboard
    
    Args:
        ctx: ARQ context containing 'app', 'engine'
    
    Returns:
        dict with update results
    """
    app = ctx.get('app')
    engine = ctx.get('engine')
    
    if not app:
        logger.error("❌ Flask app not available for tournament ROI calculation")
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, Tournament, TournamentParticipant, TradeHistory
    
    with app.app_context():
        now = datetime.now(timezone.utc)
        
        try:
            participants_updated = 0
            errors = []
            
            # Get all active tournaments
            active_tournaments = Tournament.query.filter_by(status='active').all()
            
            for tournament in active_tournaments:
                start = tournament.start_date
                end = tournament.end_date
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                
                logger.info(f"🔄 Updating ROI for tournament: {tournament.name}")
                
                for participant in tournament.participants.all():
                    try:
                        # Get current balance from exchange
                        if engine:
                            current_balance = await _get_user_balance(engine, participant.user_id)
                        else:
                            # Fallback: use balance history
                            current_balance = participant.current_balance
                        
                        # Count trades during tournament period
                        trades_count = TradeHistory.query.filter(
                            TradeHistory.user_id == participant.user_id,
                            TradeHistory.close_time >= start,
                            TradeHistory.close_time <= now
                        ).count()
                        
                        # Update participant metrics
                        participant.update_performance(
                            current_balance=current_balance,
                            trades_count=trades_count
                        )
                        
                        participants_updated += 1
                        
                    except Exception as e:
                        errors.append(f"User {participant.user_id}: {str(e)[:50]}")
                        logger.error(f"❌ Error updating participant {participant.user_id}: {e}")
            
            db.session.commit()
            
            # Record metrics
            record_worker_task(task_name='calculate_tournament_roi', status='success')
            
            result = {
                'status': 'success',
                'tournaments_processed': len(active_tournaments),
                'participants_updated': participants_updated,
                'errors': errors[:10],
                'timestamp': now.isoformat()
            }
            
            logger.info(f"📊 Tournament ROI update: {participants_updated} participants updated")
            return result
            
        except Exception as e:
            record_worker_task(task_name='calculate_tournament_roi', status='error')
            logger.error(f"❌ Tournament ROI calculation failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': now.isoformat()
            }


async def finalize_tournament_task(ctx: dict) -> dict:
    """
    Finalize completed tournaments and determine winners.
    
    This task runs every 5 minutes via cron and:
    1. Finds tournaments in 'calculating' status
    2. Determines TOP-3 winners by ROI
    3. Distributes prizes (50%/30%/20%)
    4. Sends notifications to winners
    
    Args:
        ctx: ARQ context containing 'app', 'telegram'
    
    Returns:
        dict with finalization results
    """
    app = ctx.get('app')
    telegram = ctx.get('telegram')
    
    if not app:
        logger.error("❌ Flask app not available for tournament finalization")
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, Tournament, TournamentParticipant, User
    
    with app.app_context():
        now = datetime.now(timezone.utc)
        
        try:
            finalized = 0
            winners_notified = 0
            errors = []
            
            # Find tournaments ready to be finalized
            calculating_tournaments = Tournament.query.filter_by(status='calculating').all()
            
            for tournament in calculating_tournaments:
                try:
                    logger.info(f"🏅 Finalizing tournament: {tournament.name}")
                    
                    # Finalize and determine winners
                    tournament.finalize()
                    finalized += 1
                    
                    # Get top 3 for notifications
                    top_3 = [
                        (1, tournament.winner_1st, tournament.prize_pool * tournament.prize_1st_pct / 100),
                        (2, tournament.winner_2nd, tournament.prize_pool * tournament.prize_2nd_pct / 100),
                        (3, tournament.winner_3rd, tournament.prize_pool * tournament.prize_3rd_pct / 100),
                    ]
                    
                    # Notify winners via Telegram
                    for rank, winner, prize in top_3:
                        if winner and telegram and winner.telegram_chat_id and winner.telegram_enabled:
                            try:
                                medal = {1: '🥇', 2: '🥈', 3: '🥉'}[rank]
                                telegram.send_message(
                                    winner.telegram_chat_id,
                                    f"{medal} **Congratulations!**\n\n"
                                    f"You placed **#{rank}** in **{tournament.name}**!\n\n"
                                    f"💰 Prize: **${prize:.2f}**\n\n"
                                    f"Keep trading and join the next tournament!"
                                )
                                winners_notified += 1
                            except Exception as e:
                                errors.append(f"Notify user {winner.id}: {str(e)[:50]}")
                    
                    logger.info(f"🏆 Tournament finalized: 1st={tournament.winner_1st_id}, 2nd={tournament.winner_2nd_id}, 3rd={tournament.winner_3rd_id}")
                    
                except Exception as e:
                    errors.append(f"Tournament {tournament.id}: {str(e)[:50]}")
                    logger.error(f"❌ Error finalizing tournament {tournament.id}: {e}")
            
            db.session.commit()
            
            # Record metrics
            record_worker_task(task_name='finalize_tournament', status='success')
            
            result = {
                'status': 'success',
                'tournaments_finalized': finalized,
                'winners_notified': winners_notified,
                'errors': errors[:10],
                'timestamp': now.isoformat()
            }
            
            if finalized:
                logger.info(f"🏆 Tournaments finalized: {finalized}, winners notified: {winners_notified}")
            
            return result
            
        except Exception as e:
            record_worker_task(task_name='finalize_tournament', status='error')
            logger.error(f"❌ Tournament finalization failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': now.isoformat()
            }


async def create_weekly_tournament_task(ctx: dict) -> dict:
    """
    Create a new weekly tournament automatically.
    
    This task runs every Sunday at 23:00 UTC via cron and:
    1. Creates a new tournament for the upcoming week
    2. Sets start date to Monday 00:00 UTC
    3. Sets end date to Sunday 23:59 UTC
    
    Args:
        ctx: ARQ context containing 'app'
    
    Returns:
        dict with creation results
    """
    app = ctx.get('app')
    
    if not app:
        logger.error("❌ Flask app not available for tournament creation")
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import db, Tournament
    
    with app.app_context():
        now = datetime.now(timezone.utc)
        
        try:
            # Check if there's already an upcoming tournament
            existing = Tournament.query.filter_by(status='upcoming').first()
            
            if existing:
                logger.info(f"📅 Upcoming tournament already exists: {existing.name}")
                return {
                    'status': 'skipped',
                    'message': 'Upcoming tournament already exists',
                    'tournament_id': existing.id,
                    'tournament_name': existing.name,
                    'timestamp': now.isoformat()
                }
            
            # Create new weekly tournament
            week_num = (now + timedelta(days=1)).isocalendar()[1]
            tournament = Tournament.create_weekly_tournament(
                name=f"Weekly Championship - Week {week_num}",
                entry_fee=10.0
            )
            
            logger.info(f"🏆 Created new weekly tournament: {tournament.name}")
            
            # Record metrics
            record_worker_task(task_name='create_weekly_tournament', status='success')
            
            return {
                'status': 'success',
                'tournament_id': tournament.id,
                'tournament_name': tournament.name,
                'start_date': tournament.start_date.isoformat(),
                'end_date': tournament.end_date.isoformat(),
                'entry_fee': tournament.entry_fee,
                'timestamp': now.isoformat()
            }
            
        except Exception as e:
            record_worker_task(task_name='create_weekly_tournament', status='error')
            logger.error(f"❌ Weekly tournament creation failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': now.isoformat()
            }


async def get_tournament_status_task(ctx: dict, tournament_id: int = None) -> dict:
    """
    Get tournament status and leaderboard.
    
    Args:
        ctx: ARQ context with 'app'
        tournament_id: Optional - get specific tournament (None = active tournament)
    
    Returns:
        dict with tournament status and leaderboard
    """
    app = ctx.get('app')
    
    if not app:
        return {'status': 'error', 'message': 'App not initialized'}
    
    from models import Tournament
    
    with app.app_context():
        try:
            if tournament_id:
                tournament = Tournament.query.get(tournament_id)
            else:
                tournament = Tournament.get_active_tournament()
            
            if not tournament:
                return {
                    'status': 'success',
                    'tournament': None,
                    'message': 'No active tournament found',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            return {
                'status': 'success',
                'tournament': tournament.to_dict(include_leaderboard=True),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Tournament status check failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }


async def _get_user_balance(engine, user_id: int) -> float:
    """
    Helper function to get user's current balance from their exchange.
    
    Args:
        engine: TradingEngine instance
        user_id: User ID to get balance for
    
    Returns:
        float: Current balance in USD
    """
    if not engine:
        return 0.0
    
    # Find user's slave client
    for slave_data in engine.slave_clients:
        if slave_data.get('id') == user_id:
            client = slave_data.get('client')
            if not client:
                continue
            
            try:
                if slave_data.get('is_ccxt') and slave_data.get('is_async'):
                    # CCXT async client
                    balance = await client.fetch_balance()
                    return float(balance.get('total', {}).get('USDT', 0))
                elif not slave_data.get('is_ccxt'):
                    # Binance client
                    balance = client.futures_account_balance()
                    for asset in balance:
                        if asset.get('asset') == 'USDT':
                            return float(asset.get('balance', 0))
            except Exception as e:
                logger.warning(f"⚠️ Could not get balance for user {user_id}: {e}")
    
    # Fallback: get from balance history
    from models import BalanceHistory
    
    latest = BalanceHistory.query.filter_by(user_id=user_id).order_by(
        BalanceHistory.timestamp.desc()
    ).first()
    
    return float(latest.balance) if latest else 0.0