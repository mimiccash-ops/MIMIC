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