"""
Brain Capital - Smart Trading Features

This module implements advanced trading features:
1. Trailing Stop-Loss - Dynamic SL stored in Redis, not on exchange (hidden from market makers)
2. DCA (Dollar Cost Averaging) - Automatic position averaging on drawdown
3. Risk Guardrails - Daily equity protection (drawdown stop & profit lock)

Redis Keys Structure:
- trailing_sl:{user_id}:{symbol} -> JSON with {entry_price, current_sl, highest_price, side, qty}
- dca_count:{user_id}:{symbol} -> Integer count of DCA orders placed
- user:{user_id}:start_day_balance -> Float balance at start of day (00:00 UTC)
- user:{user_id}:risk_guardrails_status -> JSON with {paused, reason, paused_at}
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger("SmartFeatures")


@dataclass
class TrailingStopData:
    """Data structure for trailing stop-loss tracking"""
    user_id: str
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    current_sl: float
    highest_price: float  # For LONG - highest since entry
    lowest_price: float   # For SHORT - lowest since entry
    qty: float
    activation_pct: float  # When to start trailing (e.g., 1.0 = 1%)
    callback_pct: float    # Trail distance (e.g., 0.5 = 0.5%)
    activated: bool = False  # Whether trailing has been activated
    created_at: str = ""
    updated_at: str = ""
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> 'TrailingStopData':
        return cls(**json.loads(data))


class SmartFeaturesManager:
    """
    Manages Smart Trading Features:
    - Trailing Stop-Loss with Redis storage
    - DCA (Dollar Cost Averaging)
    
    Designed to run in the ARQ worker context with access to Redis and Trading Engine.
    """
    
    def __init__(self, redis_client=None, trading_engine=None):
        """
        Initialize Smart Features Manager.
        
        Args:
            redis_client: Redis async client for storing trailing SL data
            trading_engine: Reference to TradingEngine for executing orders
        """
        self.redis = redis_client
        self.engine = trading_engine
        self._monitoring_task: Optional[asyncio.Task] = None
        self._websocket_tasks: Dict[str, asyncio.Task] = {}
        self._active_symbols: Set[str] = set()
        self._running = False
        self._lock = asyncio.Lock()
        
        # Default settings (can be overridden per user)
        self.default_trailing_activation = 1.0  # Activate trailing at 1% profit
        self.default_trailing_callback = 0.5    # Trail by 0.5%
        self.default_dca_threshold = -2.0       # DCA when PnL < -2%
        self.default_dca_multiplier = 1.0       # Same size as original
        
        logger.info("🎯 SmartFeaturesManager initialized")
    
    # ==================== REDIS KEYS ====================
    
    def _trailing_sl_key(self, user_id: str, symbol: str) -> str:
        return f"trailing_sl:{user_id}:{symbol}"
    
    def _dca_count_key(self, user_id: str, symbol: str) -> str:
        return f"dca_count:{user_id}:{symbol}"
    
    def _active_trailing_key(self) -> str:
        return "trailing_sl:active_positions"
    
    # ==================== TRAILING STOP-LOSS ====================
    
    async def register_trailing_sl(
        self,
        user_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        qty: float,
        initial_sl: float,
        activation_pct: float = None,
        callback_pct: float = None
    ) -> bool:
        """
        Register a new position for trailing stop-loss monitoring.
        
        Args:
            user_id: User ID (or 'master' for master account)
            symbol: Trading symbol (e.g., 'BTCUSDT')
            side: Position side ('LONG' or 'SHORT')
            entry_price: Entry price of the position
            qty: Position quantity
            initial_sl: Initial stop-loss price
            activation_pct: When to activate trailing (default: 1%)
            callback_pct: Trail distance (default: 0.5%)
        
        Returns:
            True if registered successfully
        """
        if not self.redis:
            logger.warning("Redis not available, cannot register trailing SL")
            return False
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            data = TrailingStopData(
                user_id=str(user_id),
                symbol=symbol,
                side=side.upper(),
                entry_price=entry_price,
                current_sl=initial_sl,
                highest_price=entry_price if side.upper() == 'LONG' else float('inf'),
                lowest_price=entry_price if side.upper() == 'SHORT' else 0,
                qty=qty,
                activation_pct=activation_pct or self.default_trailing_activation,
                callback_pct=callback_pct or self.default_trailing_callback,
                activated=False,
                created_at=now,
                updated_at=now
            )
            
            key = self._trailing_sl_key(user_id, symbol)
            await self.redis.set(key, data.to_json())
            
            # Add to active positions set
            await self.redis.sadd(self._active_trailing_key(), f"{user_id}:{symbol}")
            
            # Track symbol for WebSocket subscription
            async with self._lock:
                self._active_symbols.add(symbol)
            
            logger.info(f"📍 Registered trailing SL: {symbol} {side} for {user_id} @ ${entry_price:.4f}, SL=${initial_sl:.4f}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register trailing SL: {e}")
            return False
    
    async def update_trailing_sl(self, user_id: str, symbol: str, current_price: float) -> Optional[float]:
        """
        Update trailing stop-loss based on current price.
        
        This is called on every price tick from WebSocket.
        
        Args:
            user_id: User ID
            symbol: Trading symbol
            current_price: Current market price
        
        Returns:
            New SL price if updated, None if no change or position not found
        """
        if not self.redis:
            return None
        
        try:
            key = self._trailing_sl_key(user_id, symbol)
            raw_data = await self.redis.get(key)
            
            if not raw_data:
                return None
            
            data = TrailingStopData.from_json(raw_data)
            now = datetime.now(timezone.utc).isoformat()
            updated = False
            new_sl = None
            
            if data.side == 'LONG':
                # For LONG: track highest price, move SL up
                if current_price > data.highest_price:
                    data.highest_price = current_price
                    updated = True
                
                # Calculate profit percentage
                profit_pct = ((current_price - data.entry_price) / data.entry_price) * 100
                
                # Check if trailing should be activated
                if not data.activated and profit_pct >= data.activation_pct:
                    data.activated = True
                    logger.info(f"🎯 Trailing SL ACTIVATED for {symbol} ({user_id}) at {profit_pct:.2f}% profit")
                    updated = True
                
                # If activated, calculate new SL
                if data.activated:
                    new_sl_price = data.highest_price * (1 - data.callback_pct / 100)
                    
                    # Only move SL up, never down
                    if new_sl_price > data.current_sl:
                        old_sl = data.current_sl
                        data.current_sl = new_sl_price
                        new_sl = new_sl_price
                        logger.info(f"📈 Trailing SL moved up: {symbol} ({user_id}) ${old_sl:.4f} -> ${new_sl_price:.4f}")
                        updated = True
            
            else:  # SHORT
                # For SHORT: track lowest price, move SL down
                if current_price < data.lowest_price:
                    data.lowest_price = current_price
                    updated = True
                
                # Calculate profit percentage (inverted for SHORT)
                profit_pct = ((data.entry_price - current_price) / data.entry_price) * 100
                
                # Check if trailing should be activated
                if not data.activated and profit_pct >= data.activation_pct:
                    data.activated = True
                    logger.info(f"🎯 Trailing SL ACTIVATED for {symbol} ({user_id}) at {profit_pct:.2f}% profit")
                    updated = True
                
                # If activated, calculate new SL
                if data.activated:
                    new_sl_price = data.lowest_price * (1 + data.callback_pct / 100)
                    
                    # Only move SL down for SHORT, never up
                    if new_sl_price < data.current_sl:
                        old_sl = data.current_sl
                        data.current_sl = new_sl_price
                        new_sl = new_sl_price
                        logger.info(f"📉 Trailing SL moved down: {symbol} ({user_id}) ${old_sl:.4f} -> ${new_sl_price:.4f}")
                        updated = True
            
            if updated:
                data.updated_at = now
                await self.redis.set(key, data.to_json())
            
            return new_sl
            
        except Exception as e:
            logger.error(f"Error updating trailing SL for {symbol} ({user_id}): {e}")
            return None
    
    async def check_trailing_sl_trigger(self, user_id: str, symbol: str, current_price: float) -> bool:
        """
        Check if trailing SL has been triggered (price hit SL).
        
        Args:
            user_id: User ID
            symbol: Trading symbol
            current_price: Current market price
        
        Returns:
            True if SL triggered, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            key = self._trailing_sl_key(user_id, symbol)
            raw_data = await self.redis.get(key)
            
            if not raw_data:
                return False
            
            data = TrailingStopData.from_json(raw_data)
            
            triggered = False
            if data.side == 'LONG' and current_price <= data.current_sl:
                triggered = True
                logger.warning(f"🔴 TRAILING SL TRIGGERED: {symbol} LONG ({user_id}) @ ${current_price:.4f} <= SL ${data.current_sl:.4f}")
            elif data.side == 'SHORT' and current_price >= data.current_sl:
                triggered = True
                logger.warning(f"🔴 TRAILING SL TRIGGERED: {symbol} SHORT ({user_id}) @ ${current_price:.4f} >= SL ${data.current_sl:.4f}")
            
            if triggered:
                # Execute the close order
                await self._execute_trailing_sl_close(data, current_price)
                # Remove from tracking
                await self.remove_trailing_sl(user_id, symbol)
            
            return triggered
            
        except Exception as e:
            logger.error(f"Error checking trailing SL trigger: {e}")
            return False
    
    async def _execute_trailing_sl_close(self, data: TrailingStopData, trigger_price: float):
        """Execute close order when trailing SL is triggered"""
        if not self.engine:
            logger.error("Trading engine not available, cannot execute trailing SL close")
            return
        
        try:
            # Create a close signal
            close_signal = {
                'symbol': data.symbol,
                'action': 'close',
                'reason': f'Trailing SL triggered @ ${trigger_price:.4f}'
            }
            
            logger.info(f"🔴 Executing trailing SL close: {data.symbol} for {data.user_id}")
            
            # For now, log the action - actual execution would require specific user's exchange client
            # In practice, this would need to find the user's exchange client and close the position
            # The implementation depends on how positions are tracked in the engine
            
            # TODO: Implement actual position close via exchange
            # This would need to:
            # 1. Find the user's exchange client
            # 2. Execute a market close order
            # 3. Log the trade result
            
        except Exception as e:
            logger.error(f"Failed to execute trailing SL close: {e}")
    
    async def remove_trailing_sl(self, user_id: str, symbol: str) -> bool:
        """Remove trailing SL tracking for a position"""
        if not self.redis:
            return False
        
        try:
            key = self._trailing_sl_key(user_id, symbol)
            await self.redis.delete(key)
            await self.redis.srem(self._active_trailing_key(), f"{user_id}:{symbol}")
            
            logger.info(f"🗑️ Removed trailing SL: {symbol} ({user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove trailing SL: {e}")
            return False
    
    async def get_trailing_sl(self, user_id: str, symbol: str) -> Optional[TrailingStopData]:
        """Get trailing SL data for a position"""
        if not self.redis:
            return None
        
        try:
            key = self._trailing_sl_key(user_id, symbol)
            raw_data = await self.redis.get(key)
            
            if raw_data:
                return TrailingStopData.from_json(raw_data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get trailing SL: {e}")
            return None
    
    async def get_all_active_trailing_positions(self) -> List[Tuple[str, str]]:
        """Get all active trailing SL positions as (user_id, symbol) tuples"""
        if not self.redis:
            return []
        
        try:
            members = await self.redis.smembers(self._active_trailing_key())
            positions = []
            for member in members:
                if isinstance(member, bytes):
                    member = member.decode('utf-8')
                parts = member.split(':', 1)
                if len(parts) == 2:
                    positions.append((parts[0], parts[1]))
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get active trailing positions: {e}")
            return []
    
    # ==================== DCA (Dollar Cost Averaging) ====================
    
    async def get_dca_count(self, user_id: str, symbol: str) -> int:
        """Get the number of DCA orders already placed for a position"""
        if not self.redis:
            return 0
        
        try:
            key = self._dca_count_key(user_id, symbol)
            count = await self.redis.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Failed to get DCA count: {e}")
            return 0
    
    async def increment_dca_count(self, user_id: str, symbol: str) -> int:
        """Increment DCA count and return new value"""
        if not self.redis:
            return 0
        
        try:
            key = self._dca_count_key(user_id, symbol)
            new_count = await self.redis.incr(key)
            # Set expiry (7 days - positions usually close before this)
            await self.redis.expire(key, 7 * 24 * 60 * 60)
            return new_count
        except Exception as e:
            logger.error(f"Failed to increment DCA count: {e}")
            return 0
    
    async def reset_dca_count(self, user_id: str, symbol: str) -> bool:
        """Reset DCA count (called when position is closed)"""
        if not self.redis:
            return False
        
        try:
            key = self._dca_count_key(user_id, symbol)
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to reset DCA count: {e}")
            return False
    
    async def should_execute_dca(
        self,
        user_id: str,
        symbol: str,
        current_pnl_pct: float,
        dca_threshold: float = None,
        dca_max_orders: int = 3
    ) -> bool:
        """
        Check if DCA should be executed based on PnL threshold.
        
        Args:
            user_id: User ID
            symbol: Trading symbol
            current_pnl_pct: Current PnL percentage (negative = loss)
            dca_threshold: Threshold to trigger DCA (e.g., -2.0 for -2%)
            dca_max_orders: Maximum DCA orders allowed
        
        Returns:
            True if DCA should be executed
        """
        threshold = dca_threshold or self.default_dca_threshold
        
        # Check if PnL is below threshold (more negative)
        if current_pnl_pct >= threshold:
            return False
        
        # Check if max DCA orders reached
        current_count = await self.get_dca_count(user_id, symbol)
        if current_count >= dca_max_orders:
            logger.info(f"DCA limit reached for {symbol} ({user_id}): {current_count}/{dca_max_orders}")
            return False
        
        return True
    
    # ==================== WEBSOCKET PRICE MONITORING ====================
    
    async def start_price_monitor(self):
        """Start the WebSocket price monitoring for all active trailing positions"""
        if self._running:
            logger.warning("Price monitor already running")
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._price_monitor_loop())
        logger.info("🚀 Started trailing SL price monitor")
    
    async def stop_price_monitor(self):
        """Stop the WebSocket price monitoring"""
        self._running = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        for task in self._websocket_tasks.values():
            task.cancel()
        
        self._websocket_tasks.clear()
        logger.info("🛑 Stopped trailing SL price monitor")
    
    async def _price_monitor_loop(self):
        """Main monitoring loop - polls prices for active positions"""
        logger.info("📊 Price monitor loop started")
        
        while self._running:
            try:
                # Get all active trailing positions
                positions = await self.get_all_active_trailing_positions()
                
                if not positions:
                    await asyncio.sleep(5)
                    continue
                
                # Group by symbol for efficient price fetching
                symbols = set(symbol for _, symbol in positions)
                
                # Fetch current prices (using master client from engine)
                if self.engine and self.engine.master_client:
                    for symbol in symbols:
                        try:
                            ticker = self.engine.master_client.futures_symbol_ticker(symbol=symbol)
                            current_price = float(ticker['price'])
                            
                            # Update all trailing SLs for this symbol
                            for user_id, pos_symbol in positions:
                                if pos_symbol == symbol:
                                    await self.update_trailing_sl(user_id, symbol, current_price)
                                    await self.check_trailing_sl_trigger(user_id, symbol, current_price)
                        
                        except Exception as e:
                            logger.error(f"Error fetching price for {symbol}: {e}")
                
                # Poll every second
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in price monitor loop: {e}")
                await asyncio.sleep(5)
        
        logger.info("📊 Price monitor loop stopped")
    
    async def subscribe_binance_websocket(self, symbols: List[str]):
        """
        Subscribe to Binance WebSocket for real-time price updates.
        
        This provides much faster price updates than polling.
        """
        try:
            from binance import AsyncClient, BinanceSocketManager
            
            # Initialize Binance async client
            client = await AsyncClient.create()
            bsm = BinanceSocketManager(client)
            
            for symbol in symbols:
                # Subscribe to mark price stream (futures)
                socket = bsm.futures_symbol_ticker_socket(symbol)
                
                async def handle_socket(sock, sym):
                    async with sock as stream:
                        while self._running:
                            msg = await stream.recv()
                            if msg:
                                current_price = float(msg['c'])  # Current price
                                
                                # Update all trailing positions for this symbol
                                positions = await self.get_all_active_trailing_positions()
                                for user_id, pos_symbol in positions:
                                    if pos_symbol == sym:
                                        await self.update_trailing_sl(user_id, sym, current_price)
                                        await self.check_trailing_sl_trigger(user_id, sym, current_price)
                
                # Create task for this symbol
                task = asyncio.create_task(handle_socket(socket, symbol))
                self._websocket_tasks[symbol] = task
                logger.info(f"📡 Subscribed to WebSocket for {symbol}")
            
        except ImportError:
            logger.warning("Binance websocket support not available, using polling")
        except Exception as e:
            logger.error(f"Failed to subscribe to Binance WebSocket: {e}")


# ==================== RISK GUARDRAILS ====================

@dataclass
class RiskGuardrailsStatus:
    """Data structure for risk guardrails status"""
    user_id: str
    paused: bool
    reason: Optional[str]  # 'drawdown_limit' or 'profit_lock'
    paused_at: Optional[str]
    start_day_balance: float
    current_equity: float
    drawdown_pct: float
    profit_pct: float
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> 'RiskGuardrailsStatus':
        return cls(**json.loads(data))


class RiskGuardrailsManager:
    """
    Manages Risk Guardrails for users:
    - Daily Drawdown Stop: Pause trading if equity drops below threshold
    - Daily Profit Lock: Pause trading when profit target is reached
    
    Uses Redis to track start-of-day balance (resets at 00:00 UTC).
    """
    
    def __init__(self, redis_client=None, trading_engine=None):
        """
        Initialize Risk Guardrails Manager.
        
        Args:
            redis_client: Redis async client for storing daily balances
            trading_engine: Reference to TradingEngine for panic close
        """
        self.redis = redis_client
        self.engine = trading_engine
        self._lock = asyncio.Lock()
        
        logger.info("🛡️ RiskGuardrailsManager initialized")
    
    # ==================== REDIS KEYS ====================
    
    def _start_day_balance_key(self, user_id: str) -> str:
        """Key for user's start-of-day balance"""
        return f"user:{user_id}:start_day_balance"
    
    def _guardrails_status_key(self, user_id: str) -> str:
        """Key for user's guardrails status"""
        return f"user:{user_id}:risk_guardrails_status"
    
    # ==================== START DAY BALANCE ====================
    
    async def set_start_day_balance(self, user_id: str, balance: float) -> bool:
        """
        Set the start-of-day balance for a user.
        Called at 00:00 UTC via cron job.
        
        Args:
            user_id: User ID
            balance: Current equity/balance at start of day
        
        Returns:
            True if set successfully
        """
        if not self.redis:
            logger.warning("Redis not available, cannot set start day balance")
            return False
        
        try:
            key = self._start_day_balance_key(user_id)
            await self.redis.set(key, str(balance))
            # Set TTL of 25 hours (ensures it persists through the day + buffer)
            await self.redis.expire(key, 25 * 60 * 60)
            
            logger.info(f"📊 Set start day balance for user {user_id}: ${balance:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set start day balance for {user_id}: {e}")
            return False
    
    async def get_start_day_balance(self, user_id: str) -> Optional[float]:
        """
        Get the start-of-day balance for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Start day balance or None if not set
        """
        if not self.redis:
            return None
        
        try:
            key = self._start_day_balance_key(user_id)
            value = await self.redis.get(key)
            
            if value:
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                return float(value)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get start day balance for {user_id}: {e}")
            return None
    
    async def initialize_start_day_balance_if_missing(
        self, 
        user_id: str, 
        current_balance: float
    ) -> float:
        """
        Initialize start day balance if not already set.
        Called before first trade of the day.
        
        Args:
            user_id: User ID
            current_balance: Current equity to use if not set
        
        Returns:
            The start day balance (existing or newly set)
        """
        existing = await self.get_start_day_balance(user_id)
        
        if existing is not None:
            return existing
        
        # Set current balance as start day balance
        await self.set_start_day_balance(user_id, current_balance)
        return current_balance
    
    # ==================== RISK CHECKS ====================
    
    async def check_risk_guardrails(
        self,
        user_id: str,
        current_equity: float,
        drawdown_limit_perc: float = 10.0,
        profit_target_perc: float = 20.0
    ) -> Tuple[bool, Optional[str], dict]:
        """
        Check if risk guardrails should trigger.
        
        This should be called BEFORE every trade execution.
        
        Args:
            user_id: User ID
            current_equity: Current account equity/balance
            drawdown_limit_perc: Max daily drawdown % (e.g., 10 = -10%)
            profit_target_perc: Daily profit target % (e.g., 20 = +20%)
        
        Returns:
            Tuple of (should_pause, reason, stats_dict)
            - should_pause: True if trading should be stopped
            - reason: 'drawdown_limit' or 'profit_lock' or None
            - stats_dict: Dict with balance stats for logging
        """
        # Get or initialize start day balance
        start_balance = await self.initialize_start_day_balance_if_missing(
            user_id, current_equity
        )
        
        if start_balance <= 0:
            # Safety: avoid division by zero
            return False, None, {'error': 'Invalid start balance'}
        
        # Calculate daily P&L percentage
        pnl_pct = ((current_equity - start_balance) / start_balance) * 100
        
        stats = {
            'user_id': user_id,
            'start_balance': round(start_balance, 2),
            'current_equity': round(current_equity, 2),
            'pnl_pct': round(pnl_pct, 2),
            'drawdown_limit': drawdown_limit_perc,
            'profit_target': profit_target_perc
        }
        
        # Check DRAWDOWN LIMIT (equity stop loss)
        if pnl_pct <= -drawdown_limit_perc:
            reason = 'drawdown_limit'
            stats['trigger'] = f"Equity ${current_equity:.2f} < threshold ${start_balance * (1 - drawdown_limit_perc/100):.2f}"
            logger.warning(f"🔴 DRAWDOWN LIMIT HIT for user {user_id}: {pnl_pct:.2f}% (limit: -{drawdown_limit_perc}%)")
            return True, reason, stats
        
        # Check PROFIT LOCK (take profit for day)
        if pnl_pct >= profit_target_perc:
            reason = 'profit_lock'
            stats['trigger'] = f"Equity ${current_equity:.2f} > target ${start_balance * (1 + profit_target_perc/100):.2f}"
            logger.info(f"🟢 PROFIT LOCK HIT for user {user_id}: {pnl_pct:.2f}% (target: +{profit_target_perc}%)")
            return True, reason, stats
        
        return False, None, stats
    
    async def pause_user_with_guardrails(
        self,
        user_id: int,
        reason: str,
        panic_close: bool = False
    ) -> bool:
        """
        Pause a user due to risk guardrails trigger.
        
        Args:
            user_id: User ID (integer)
            reason: 'drawdown_limit' or 'profit_lock'
            panic_close: If True, close all positions first (for drawdown)
        
        Returns:
            True if user was paused successfully
        """
        try:
            # Import here to avoid circular imports
            from models import db, User
            from datetime import datetime, timezone
            
            # Get Flask app context if available
            try:
                from flask import current_app
                with current_app.app_context():
                    return await self._do_pause_user(user_id, reason, panic_close)
            except RuntimeError:
                # No app context, try to get from engine
                if self.engine and self.engine.app:
                    with self.engine.app.app_context():
                        return await self._do_pause_user(user_id, reason, panic_close)
                else:
                    logger.error(f"No Flask app context available to pause user {user_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to pause user {user_id}: {e}")
            return False
    
    async def _do_pause_user(
        self,
        user_id: int,
        reason: str,
        panic_close: bool
    ) -> bool:
        """Internal method to pause user (requires app context)"""
        from models import db, User
        from datetime import datetime, timezone
        
        user = User.query.get(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return False
        
        now = datetime.now(timezone.utc)
        
        # Update user status
        user.is_paused = True
        user.risk_guardrails_paused_at = now
        user.risk_guardrails_reason = reason
        
        db.session.commit()
        
        logger.warning(f"⏸️ User {user.username} (ID: {user_id}) PAUSED due to {reason}")
        
        # If drawdown limit hit, perform panic close
        if panic_close and self.engine:
            logger.warning(f"🚨 PANIC CLOSE: Closing all positions for user {user_id}")
            await self.panic_close_all_positions(user_id)
        
        # Store status in Redis for quick access
        if self.redis:
            status = RiskGuardrailsStatus(
                user_id=str(user_id),
                paused=True,
                reason=reason,
                paused_at=now.isoformat(),
                start_day_balance=0,
                current_equity=0,
                drawdown_pct=0,
                profit_pct=0
            )
            await self.redis.set(
                self._guardrails_status_key(str(user_id)),
                status.to_json(),
                ex=25 * 60 * 60  # 25 hour TTL
            )
        
        # Send Telegram notification
        if self.engine and self.engine.telegram:
            emoji = "🔴" if reason == 'drawdown_limit' else "🟢"
            msg = f"{emoji} Risk Guardrails Triggered\n\n"
            msg += f"User: {user.username}\n"
            msg += f"Reason: {reason.replace('_', ' ').title()}\n"
            if panic_close:
                msg += f"Action: All positions closed\n"
            msg += f"Time: {now.strftime('%H:%M:%S UTC')}"
            
            # Notify user if they have Telegram enabled
            if user.telegram_chat_id and user.telegram_enabled:
                self.engine.telegram.send_message(user.telegram_chat_id, msg)
            
            # Notify admin
            self.engine.telegram.notify_system_event(
                "Risk Guardrails", 
                f"User {user.username} paused: {reason}"
            )
        
        return True
    
    async def panic_close_all_positions(self, user_id: int) -> dict:
        """
        Close all open positions for a user.
        Called when drawdown limit is hit.
        
        Args:
            user_id: User ID
        
        Returns:
            Dict with close results
        """
        if not self.engine:
            logger.error("Trading engine not available for panic close")
            return {'error': 'No trading engine'}
        
        results = {
            'user_id': user_id,
            'positions_closed': 0,
            'errors': []
        }
        
        try:
            # Find user's client in slave_clients
            user_client = None
            for slave in self.engine.slave_clients:
                if slave.get('id') == user_id:
                    user_client = slave
                    break
            
            if not user_client:
                logger.warning(f"User {user_id} client not found in slave_clients")
                return {'error': 'User client not found'}
            
            client = user_client.get('client')
            is_ccxt = user_client.get('is_ccxt', False)
            is_async = user_client.get('is_async', False)
            exchange_type = user_client.get('exchange_type', 'binance')
            
            # Get all open positions
            positions = []
            if is_ccxt and is_async:
                positions = await client.fetch_positions()
            elif is_ccxt:
                positions = client.fetch_positions()
            else:
                # Binance client
                positions = client.futures_position_information()
            
            # Close each position
            for pos in positions:
                try:
                    if is_ccxt:
                        contracts = float(pos.get('contracts', 0))
                        if contracts == 0:
                            continue
                        
                        symbol = pos.get('symbol')
                        side = 'sell' if pos.get('side', '').lower() == 'long' else 'buy'
                        
                        if is_async:
                            await client.create_order(
                                symbol, 'market', side,
                                abs(contracts),
                                params={'reduceOnly': True}
                            )
                        else:
                            client.create_order(
                                symbol, 'market', side,
                                abs(contracts),
                                params={'reduceOnly': True}
                            )
                    else:
                        # Binance client
                        amt = float(pos.get('positionAmt', 0))
                        if amt == 0:
                            continue
                        
                        symbol = pos.get('symbol')
                        side = 'SELL' if amt > 0 else 'BUY'
                        
                        client.futures_create_order(
                            symbol=symbol,
                            side=side,
                            type='MARKET',
                            quantity=abs(amt),
                            reduceOnly=True
                        )
                    
                    results['positions_closed'] += 1
                    logger.info(f"🔴 Panic closed position: {symbol} for user {user_id}")
                    
                except Exception as e:
                    error_msg = f"Failed to close {pos.get('symbol', 'unknown')}: {str(e)[:50]}"
                    results['errors'].append(error_msg)
                    logger.error(f"Panic close error for user {user_id}: {e}")
            
            logger.warning(f"🚨 Panic close complete for user {user_id}: {results['positions_closed']} positions closed")
            return results
            
        except Exception as e:
            logger.error(f"Panic close failed for user {user_id}: {e}")
            return {'error': str(e)}
    
    async def reset_user_guardrails(self, user_id: int) -> bool:
        """
        Reset risk guardrails for a user (unpause).
        Called by admin or automatically at start of new day.
        
        Args:
            user_id: User ID
        
        Returns:
            True if reset successfully
        """
        try:
            from models import db, User
            
            # Try to get Flask app context
            try:
                from flask import current_app
                app = current_app._get_current_object()
            except RuntimeError:
                if self.engine and self.engine.app:
                    app = self.engine.app
                else:
                    logger.error("No Flask app context for reset")
                    return False
            
            with app.app_context():
                user = User.query.get(user_id)
                if not user:
                    return False
                
                user.is_paused = False
                user.risk_guardrails_paused_at = None
                user.risk_guardrails_reason = None
                
                db.session.commit()
                
                # Clear Redis status
                if self.redis:
                    await self.redis.delete(self._guardrails_status_key(str(user_id)))
                
                logger.info(f"✅ Reset risk guardrails for user {user.username} (ID: {user_id})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to reset guardrails for user {user_id}: {e}")
            return False
    
    async def reset_all_daily_balances(self) -> dict:
        """
        Reset start-of-day balances for all users.
        Called by cron job at 00:00 UTC.
        
        Returns:
            Dict with results
        """
        results = {
            'users_reset': 0,
            'users_unpaused': 0,
            'errors': []
        }
        
        try:
            from models import User
            
            # Get Flask app context
            try:
                from flask import current_app
                app = current_app._get_current_object()
            except RuntimeError:
                if self.engine and self.engine.app:
                    app = self.engine.app
                else:
                    return {'error': 'No Flask app context'}
            
            with app.app_context():
                # Get all users with risk guardrails enabled
                users = User.query.filter(
                    User.risk_guardrails_enabled == True
                ).all()
                
                for user in users:
                    try:
                        # Clear start day balance (will be re-initialized on first trade)
                        if self.redis:
                            await self.redis.delete(self._start_day_balance_key(str(user.id)))
                        
                        # Unpause users that were paused by guardrails
                        if user.risk_guardrails_reason:
                            await self.reset_user_guardrails(user.id)
                            results['users_unpaused'] += 1
                        
                        results['users_reset'] += 1
                        
                    except Exception as e:
                        results['errors'].append(f"User {user.id}: {str(e)[:50]}")
                
                logger.info(f"🔄 Daily balance reset complete: {results}")
                return results
                
        except Exception as e:
            logger.error(f"Failed to reset daily balances: {e}")
            return {'error': str(e)}


# ==================== HELPER FUNCTIONS ====================

async def calculate_position_pnl_pct(
    entry_price: float,
    current_price: float,
    side: str
) -> float:
    """Calculate PnL percentage for a position"""
    if entry_price <= 0:
        return 0.0
    
    if side.upper() == 'LONG':
        return ((current_price - entry_price) / entry_price) * 100
    else:  # SHORT
        return ((entry_price - current_price) / entry_price) * 100

