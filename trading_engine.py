"""
Brain Capital Trading Engine
Handles copy trading execution with Binance Futures API
Fully async implementation using asyncio and ccxt.async_support

Prometheus Metrics:
- trade_execution_latency_seconds: Histogram for trade latency
- active_positions_count: Gauge for open positions
- failed_orders_total: Counter for failed order attempts
"""

import time
import re
import math
import logging
import asyncio
import threading
import socket
from collections import defaultdict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from binance.client import Client
from binance.exceptions import BinanceAPIException
from models import User, db, TradeHistory, BalanceHistory, UserExchange, ExchangeConfig, Strategy, StrategySubscription
from config import Config
import ccxt.async_support as ccxt_async  # Async CCXT
import ccxt as ccxt_sync  # Sync CCXT for class lookups
from service_validator import SUPPORTED_EXCHANGES, PASSPHRASE_EXCHANGES
from http.client import RemoteDisconnected
import urllib3.exceptions
import urllib3.util.connection

# ============================================================================
# GLOBAL IPv4 ENFORCEMENT
# ============================================================================
# Force all outgoing connections to use IPv4 to prevent -2015 API errors
# when Binance API keys are bound to a specific IPv4 address (e.g., 38.180.147.102)
# but the server might prefer IPv6 for DNS resolution.
#
# This monkey-patch ensures urllib3 (used by requests, aiohttp, ccxt) only uses IPv4.
# ============================================================================

_original_allowed_gai_family = urllib3.util.connection.allowed_gai_family


def _force_ipv4_family():
    """Force IPv4 (AF_INET) for all urllib3 connections."""
    return socket.AF_INET


# Apply the patch globally at module load time
urllib3.util.connection.allowed_gai_family = _force_ipv4_family
logger_ipv4 = logging.getLogger("TradingEngine.IPv4")
logger_ipv4.info("🔒 IPv4 enforced globally for all HTTP connections (urllib3 patched)")

# Prometheus metrics
from metrics import (
    TRADE_LATENCY, ACTIVE_POSITIONS, FAILED_ORDERS, SUCCESSFUL_ORDERS,
    ACTIVE_USERS, TOTAL_AUM, RATE_LIMIT_HITS, SIGNALS_RECEIVED,
    track_trade_execution, update_positions, update_aum, update_active_users,
    record_rate_limit, record_signal, record_signal_processed, update_pnl
)

# Smart Features (Trailing SL, DCA, Risk Guardrails)
from smart_features import SmartFeaturesManager, RiskGuardrailsManager, calculate_position_pnl_pct

logger = logging.getLogger("TradingEngine")


def verify_outgoing_ip() -> str:
    """
    Verify the outgoing IP address that Binance sees for API requests.
    
    This helps diagnose APIError(code=-2015) which means:
    - Invalid API-key, IP, or permissions for action
    
    Note: This module enforces IPv4 globally via urllib3 patch.
    
    Returns:
        The detected outgoing IP address (IPv4)
    """
    import requests
    
    detected_ip = None

    # Debug print to confirm IPv4-only endpoint is reachable
    try:
        print(requests.get('https://api4.ipify.org').text)
    except Exception as e:
        logger.debug(f"IPv4 debug print failed: {e}")
    
    # Confirm IPv4 enforcement is active
    current_family = urllib3.util.connection.allowed_gai_family()
    if current_family == socket.AF_INET:
        logger.info("✅ IPv4 enforcement is ACTIVE (socket.AF_INET)")
    else:
        logger.warning(f"⚠️ IPv4 enforcement may not be active! Family: {current_family}")
    
    # Method 1: Use ipify.org (most reliable, IPv4 only endpoint)
    try:
        response = requests.get('https://api4.ipify.org', timeout=10)  # api4 = IPv4 only
        if response.status_code == 200:
            detected_ip = response.text.strip()
            logger.info(f"🌐 Outgoing IPv4 (api4.ipify.org): {detected_ip}")
    except Exception as e:
        logger.debug(f"api4.ipify.org check failed: {e}")
    
    # Method 2: Fallback to generic ipify
    if not detected_ip:
        try:
            response = requests.get('https://api.ipify.org', timeout=10)
            if response.status_code == 200:
                detected_ip = response.text.strip()
                logger.info(f"🌐 Outgoing IP (ipify.org): {detected_ip}")
        except Exception as e:
            logger.debug(f"ipify.org check failed: {e}")
    
    # Method 3: Use ipinfo.io as backup
    if not detected_ip:
        try:
            response = requests.get('https://ipinfo.io/ip', timeout=10)
            if response.status_code == 200:
                detected_ip = response.text.strip()
                logger.info(f"🌐 Outgoing IP (ipinfo.io): {detected_ip}")
        except Exception as e:
            logger.debug(f"ipinfo.io check failed: {e}")
    
    if detected_ip:
        logger.info(f"✅ Detected outgoing IP for Binance API: {detected_ip}")
        # Check if it looks like IPv6 (shouldn't happen with patch)
        if ':' in detected_ip:
            logger.error(f"❌ CRITICAL: Outgoing IP is IPv6 despite IPv4 enforcement!")
            logger.error(f"❌ This WILL cause -2015 errors if API key is IPv4-restricted!")
        else:
            logger.info(f"✅ IPv4 confirmed: {detected_ip}")
    else:
        logger.warning("⚠️ Could not determine outgoing IP address")
    
    return detected_ip


def create_binance_client_with_ipv4(api_key: str, api_secret: str, testnet: bool = False):
    """
    Create a Binance client that uses IPv4.
    
    Note: IPv4 is now enforced globally at module load via urllib3 patch.
    This function simply creates the client - no additional patching needed.
    
    This helps avoid -2015 errors when:
    - Server has both IPv4 and IPv6 available
    - Binance API key is restricted to a specific IPv4 address
    
    Args:
        api_key: Binance API key
        api_secret: Binance API secret
        testnet: Whether to use testnet
        
    Returns:
        Configured Binance Client
    """
    # Verify IPv4 enforcement is still active
    current_family = urllib3.util.connection.allowed_gai_family()
    if current_family != socket.AF_INET:
        logger.warning("⚠️ IPv4 enforcement not active, re-applying patch...")
        urllib3.util.connection.allowed_gai_family = _force_ipv4_family
    
    client = Client(api_key, api_secret, testnet=testnet)
    logger.info("✅ Binance client created (IPv4 enforced globally)")
    return client


class RateLimiter:
    """Async-safe rate limiter for API calls using asyncio.Lock"""
    def __init__(self, max_calls: int = 10, period: int = 1):
        self.max_calls = max_calls
        self.period = period
        self.calls = defaultdict(list)
        self._lock = asyncio.Lock()
        self._sync_lock = threading.Lock()  # For sync contexts
    
    async def can_proceed_async(self, key: str = "default") -> bool:
        """Async version of can_proceed"""
        async with self._lock:
            now = time.time()
            # Clean old calls
            self.calls[key] = [t for t in self.calls[key] if now - t < self.period]
            
            if len(self.calls[key]) < self.max_calls:
                self.calls[key].append(now)
                return True
            return False
    
    async def wait_and_proceed_async(self, key: str = "default"):
        """Async version of wait_and_proceed"""
        while not await self.can_proceed_async(key):
            await asyncio.sleep(0.1)
    
    def can_proceed(self, key: str = "default") -> bool:
        """Sync version for backward compatibility"""
        with self._sync_lock:
            now = time.time()
            self.calls[key] = [t for t in self.calls[key] if now - t < self.period]
            
            if len(self.calls[key]) < self.max_calls:
                self.calls[key].append(now)
                return True
            return False
    
    def wait_and_proceed(self, key: str = "default"):
        """Sync version for backward compatibility"""
        while not self.can_proceed(key):
            time.sleep(0.1)


class ProxyPool:
    """
    Manages proxy rotation for CCXT exchange instances.
    
    Features:
    - Round-robin proxy assignment (N users per proxy)
    - Automatic proxy disabling on 429 errors with cooldown
    - Thread-safe and async-safe operations
    - Fallback to no proxy when all proxies are disabled
    """
    
    def __init__(self, proxies: list = None, users_per_proxy: int = 50, 
                 cooldown_seconds: int = 60, max_retries: int = 3):
        """
        Initialize proxy pool.
        
        Args:
            proxies: List of proxy URLs (http://host:port or socks5://host:port)
            users_per_proxy: Number of users to assign per proxy (round-robin)
            cooldown_seconds: Time to disable a proxy after 429 error
            max_retries: Maximum retry attempts when switching proxies
        """
        self.proxies = proxies or []
        self.users_per_proxy = users_per_proxy
        self.cooldown_seconds = cooldown_seconds
        self.max_retries = max_retries
        
        # Track disabled proxies with their disable time
        self._disabled_proxies = {}  # {proxy_url: disable_timestamp}
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        
        # Assignment counter for round-robin
        self._assignment_counter = 0
        self._user_proxy_map = {}  # {user_id: proxy_url}
        
        if self.proxies:
            logger.info(f"🔄 ProxyPool initialized with {len(self.proxies)} proxies, "
                       f"{users_per_proxy} users/proxy, {cooldown_seconds}s cooldown")
        else:
            logger.info("🔄 ProxyPool initialized (no proxies configured - direct connection)")
    
    def get_proxy_for_user(self, user_id: int) -> str:
        """
        Get assigned proxy for a user (round-robin assignment).
        
        Returns proxy URL or None if no proxy available/configured.
        """
        if not self.proxies:
            return None
        
        with self._lock:
            # Return existing assignment if user already has one
            if user_id in self._user_proxy_map:
                assigned = self._user_proxy_map[user_id]
                # Check if assigned proxy is still available
                if self._is_proxy_available(assigned):
                    return assigned
                # Otherwise, reassign
            
            # Find next available proxy using round-robin
            proxy = self._get_next_available_proxy()
            if proxy:
                self._user_proxy_map[user_id] = proxy
                self._assignment_counter += 1
            return proxy
    
    def _get_next_available_proxy(self) -> str:
        """Get next available proxy in round-robin order."""
        if not self.proxies:
            return None
        
        # Try each proxy in round-robin order
        for i in range(len(self.proxies)):
            idx = (self._assignment_counter + i) % len(self.proxies)
            proxy = self.proxies[idx]
            if self._is_proxy_available(proxy):
                return proxy
        
        # All proxies disabled, try to find one with expired cooldown
        self._cleanup_expired_cooldowns()
        for proxy in self.proxies:
            if self._is_proxy_available(proxy):
                return proxy
        
        # All proxies still disabled
        logger.warning("⚠️ All proxies are disabled! Using direct connection")
        return None
    
    def _is_proxy_available(self, proxy_url: str) -> bool:
        """Check if proxy is available (not in cooldown)."""
        if proxy_url not in self._disabled_proxies:
            return True
        
        disable_time = self._disabled_proxies[proxy_url]
        if time.time() - disable_time > self.cooldown_seconds:
            # Cooldown expired, remove from disabled list
            del self._disabled_proxies[proxy_url]
            logger.info(f"✅ Proxy {self._mask_proxy(proxy_url)} cooldown expired, re-enabled")
            return True
        
        return False
    
    def _cleanup_expired_cooldowns(self):
        """Remove proxies with expired cooldowns."""
        now = time.time()
        expired = [p for p, t in self._disabled_proxies.items() 
                   if now - t > self.cooldown_seconds]
        for proxy in expired:
            del self._disabled_proxies[proxy]
            logger.info(f"✅ Proxy {self._mask_proxy(proxy)} cooldown expired, re-enabled")
    
    def disable_proxy(self, proxy_url: str, reason: str = "429 Too Many Requests"):
        """
        Temporarily disable a proxy after error.
        
        Args:
            proxy_url: The proxy URL to disable
            reason: Reason for disabling (for logging)
        """
        if not proxy_url:
            return
        
        with self._lock:
            self._disabled_proxies[proxy_url] = time.time()
            active_count = len(self.proxies) - len(self._disabled_proxies)
            logger.warning(f"🚫 Proxy {self._mask_proxy(proxy_url)} disabled for {self.cooldown_seconds}s "
                          f"(reason: {reason}). Active proxies: {active_count}/{len(self.proxies)}")
    
    async def disable_proxy_async(self, proxy_url: str, reason: str = "429 Too Many Requests"):
        """Async version of disable_proxy."""
        async with self._async_lock:
            self._disabled_proxies[proxy_url] = time.time()
            active_count = len(self.proxies) - len(self._disabled_proxies)
            logger.warning(f"🚫 Proxy {self._mask_proxy(proxy_url)} disabled for {self.cooldown_seconds}s "
                          f"(reason: {reason}). Active proxies: {active_count}/{len(self.proxies)}")
    
    def get_alternative_proxy(self, current_proxy: str) -> str:
        """
        Get an alternative proxy when current one fails.
        
        Args:
            current_proxy: The proxy that just failed
            
        Returns:
            Alternative proxy URL or None
        """
        if not self.proxies:
            return None
        
        with self._lock:
            for proxy in self.proxies:
                if proxy != current_proxy and self._is_proxy_available(proxy):
                    return proxy
            
            # Try to find one with expired cooldown
            self._cleanup_expired_cooldowns()
            for proxy in self.proxies:
                if proxy != current_proxy and self._is_proxy_available(proxy):
                    return proxy
            
            return None
    
    async def get_alternative_proxy_async(self, current_proxy: str) -> str:
        """Async version of get_alternative_proxy."""
        if not self.proxies:
            return None
        
        async with self._async_lock:
            for proxy in self.proxies:
                if proxy != current_proxy and self._is_proxy_available(proxy):
                    return proxy
            
            self._cleanup_expired_cooldowns()
            for proxy in self.proxies:
                if proxy != current_proxy and self._is_proxy_available(proxy):
                    return proxy
            
            return None
    
    def get_proxy_config_for_ccxt(self, proxy_url: str) -> dict:
        """
        Generate CCXT-compatible proxy configuration.
        
        Args:
            proxy_url: Proxy URL (http://host:port or socks5://host:port)
            
        Returns:
            Dict with 'proxies' key for CCXT or empty dict
        """
        if not proxy_url:
            return {}
        
        # CCXT uses aiohttp/requests format for proxies
        return {
            'proxies': {
                'http': proxy_url,
                'https': proxy_url,
            },
            'aiohttp_proxy': proxy_url,  # For async CCXT
        }
    
    def get_proxy_config_for_binance(self, proxy_url: str) -> dict:
        """
        Generate python-binance compatible proxy configuration.
        
        Args:
            proxy_url: Proxy URL
            
        Returns:
            Dict with 'proxies' key for requests or empty dict
        """
        if not proxy_url:
            return {}
        
        return {
            'proxies': {
                'http': proxy_url,
                'https': proxy_url,
            }
        }
    
    def reassign_user_proxy(self, user_id: int) -> str:
        """
        Force reassign a new proxy for a user (after 429 error).
        
        Returns:
            New proxy URL or None
        """
        with self._lock:
            current = self._user_proxy_map.get(user_id)
            
            # Find alternative proxy
            new_proxy = None
            for proxy in self.proxies:
                if proxy != current and self._is_proxy_available(proxy):
                    new_proxy = proxy
                    break
            
            if new_proxy:
                self._user_proxy_map[user_id] = new_proxy
                logger.info(f"🔄 Reassigned user {user_id} from {self._mask_proxy(current)} "
                           f"to {self._mask_proxy(new_proxy)}")
            return new_proxy
    
    def _mask_proxy(self, proxy_url: str) -> str:
        """Mask proxy credentials for logging."""
        if not proxy_url:
            return "None"
        # Mask password if present: http://user:pass@host:port -> http://user:***@host:port
        import re
        masked = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', proxy_url)
        return masked
    
    def get_stats(self) -> dict:
        """Get proxy pool statistics."""
        with self._lock:
            active = [p for p in self.proxies if self._is_proxy_available(p)]
            return {
                'total_proxies': len(self.proxies),
                'active_proxies': len(active),
                'disabled_proxies': len(self._disabled_proxies),
                'assigned_users': len(self._user_proxy_map),
                'users_per_proxy': self.users_per_proxy,
                'cooldown_seconds': self.cooldown_seconds,
            }


class TradingEngine:
    """
    Brain Capital Trading Engine
    
    HARDENED FOR PRODUCTION:
    - Thread-safe operations with proper locking
    - Rate limiting to prevent API bans
    - Graceful error handling
    - Position tracking with race condition prevention
    """
    
    # Safety limits
    MAX_POSITION_VALUE = 1000000  # $1M max single position
    MAX_LEVERAGE = 125  # Maximum allowed leverage
    MIN_ORDER_VALUE = 1.0  # Minimum order value in USDT
    
    def __init__(self, app_context, socketio_instance=None, telegram_notifier=None):
        self.app = app_context
        self.socketio = socketio_instance 
        self.telegram = telegram_notifier
        self.master_client = None  # Legacy: Primary Binance client
        self.master_clients = []   # NEW: All master exchange clients (multi-exchange)
        self.slave_clients = []
        
        # Async locks for thread-safe operations
        self._async_lock = asyncio.Lock()
        self._async_master_lock = asyncio.Lock()
        self._async_positions_lock = asyncio.Lock()
        self._async_pending_lock = asyncio.Lock()
        
        # Sync locks for backward compatibility with sync code paths
        self.lock = threading.RLock()
        self.master_lock = threading.Lock()
        self.symbol_precision = {}
        self.is_paused = False
        self.slippage_tolerance = 0.015  # 1.5% max slippage
        self.log_error_callback = None
        self.min_order_cost = 5.0  # Minimum order cost in USDT
        
        # Rate limiters - TUNED FOR HIGH VOLUME (now async-safe)
        self.api_limiter = RateLimiter(max_calls=15, period=1)
        self.order_limiter = RateLimiter(max_calls=8, period=1)
        
        # Proxy pool for handling high-volume trading (1000+ users)
        self.proxy_pool = ProxyPool(
            proxies=Config.PROXY_LIST if Config.PROXY_ENABLED else [],
            users_per_proxy=Config.PROXY_USERS_PER_PROXY,
            cooldown_seconds=Config.PROXY_COOLDOWN_SECONDS,
            max_retries=Config.PROXY_MAX_RETRIES
        )
        
        # Position tracking for sync
        self.master_positions = {}  # {symbol: {'amount': float, 'entry': float, 'side': str}}
        self.positions_lock = threading.Lock()
        
        # Pending trades tracking (prevents race conditions)
        self.pending_trades = {}  # {user_id: set(symbols)}
        self.pending_lock = threading.Lock()
        # Per-user async locks for position checking
        self.user_async_locks = {}  # {user_id: asyncio.Lock()}
        self._user_locks_async_lock = asyncio.Lock()
        
        # Sync per-user locks for backward compatibility
        self.user_locks = {}  # {user_id: Lock()}
        self.user_locks_lock = threading.Lock()
        
        # Background task references (for async monitoring)
        self._background_tasks = []
        self._event_loop = None
        
        # Thread pool executor for background tasks (MUST be initialized before starting threads)
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="TradingWorker")
        
        # Start background threads (will be migrated to async tasks when event loop is available)
        # Note: These threads use self.executor, so it must be initialized first
        threading.Thread(target=self.monitor_balances, daemon=True).start()
        threading.Thread(target=self.monitor_position_closes, daemon=True).start()
        
        # Reference to global settings (will be set by app.py after initialization)
        self._global_settings = None
        
        # Smart Features Manager (Trailing SL, DCA)
        # Will be initialized with Redis when set_redis_client is called
        self.smart_features: SmartFeaturesManager = None
        self._redis_client = None
        self._sync_redis = None
        self._sync_redis_lock = threading.Lock()
        
        # Risk Guardrails Manager (Daily Drawdown/Profit Protection)
        self.risk_guardrails: RiskGuardrailsManager = None
        
        # AI Sentiment Manager (Fear & Greed Index based risk adjustment)
        self.sentiment_manager = None
    
    def set_sentiment_manager(self, sentiment_manager):
        """Set the AI Sentiment Manager for risk adjustment based on Fear & Greed Index"""
        self.sentiment_manager = sentiment_manager
        logger.info("🧠 AI Sentiment Manager initialized")

    def set_redis_client(self, redis_client, redis_url: str = None):
        """Set Redis client for Smart Features (trailing SL, DCA tracking, risk guardrails)"""
        self._redis_client = redis_client
        self.smart_features = SmartFeaturesManager(
            redis_client=redis_client,
            trading_engine=self,
            redis_url=redis_url
        )
        self.risk_guardrails = RiskGuardrailsManager(
            redis_client=redis_client,
            trading_engine=self
        )
        logger.info("🎯 Smart Features initialized with Redis")
        logger.info("🛡️ Risk Guardrails initialized with Redis")

    def set_global_settings(self, settings_dict):
        """Set reference to global settings dict for reading max_positions etc."""
        self._global_settings = settings_dict
        logger.info(f"🔧 Global settings linked: max_positions={settings_dict.get('max_positions', 'N/A')}")

    def is_rate_limit_error(self, exception) -> bool:
        """
        Check if an exception is a rate limit (429) error.
        
        Handles various exception formats from:
        - CCXT (ccxt.RateLimitExceeded)
        - python-binance (BinanceAPIException with code -1015)
        - HTTP 429 responses
        """
        # Check for CCXT rate limit exception
        if hasattr(ccxt_sync, 'RateLimitExceeded'):
            if isinstance(exception, ccxt_sync.RateLimitExceeded):
                return True
        
        # Check for async CCXT rate limit exception
        if hasattr(ccxt_async, 'RateLimitExceeded'):
            if isinstance(exception, ccxt_async.RateLimitExceeded):
                return True
        
        # Check for Binance API exception (code -1015 is rate limit)
        if isinstance(exception, BinanceAPIException):
            if exception.code == -1015:  # Too many new orders
                return True
            if '429' in str(exception) or 'Too Many' in str(exception):
                return True
        
        # Check exception message for common rate limit indicators
        err_str = str(exception).lower()
        if '429' in err_str or 'too many' in err_str or 'rate limit' in err_str:
            return True
        
        return False
    
    def handle_rate_limit_error(self, user_id: int, client_data: dict, exception) -> bool:
        """
        Handle a rate limit error by disabling proxy and reassigning user.
        
        Args:
            user_id: The user ID that encountered the error
            client_data: The client data dict containing proxy info
            exception: The exception that was raised
            
        Returns:
            True if a new proxy was assigned and retry should be attempted
        """
        current_proxy = client_data.get('proxy')
        
        if not current_proxy:
            # No proxy configured, can't rotate
            logger.warning(f"⚠️ Rate limit hit for user {user_id} but no proxy configured")
            return False
        
        # Disable the faulty proxy
        self.proxy_pool.disable_proxy(current_proxy, f"Rate limit error: {str(exception)[:50]}")
        
        # Try to reassign to a new proxy
        new_proxy = self.proxy_pool.reassign_user_proxy(user_id)
        
        if new_proxy:
            # Update client_data with new proxy (caller must recreate exchange instance)
            client_data['proxy'] = new_proxy
            logger.info(f"🔄 User {user_id} reassigned to new proxy after rate limit")
            return True
        else:
            logger.warning(f"⚠️ No alternative proxy available for user {user_id}")
            return False
    
    async def handle_rate_limit_error_async(self, user_id: int, client_data: dict, exception) -> bool:
        """
        Async version of handle_rate_limit_error.
        
        Returns:
            True if a new proxy was assigned and retry should be attempted
        """
        current_proxy = client_data.get('proxy')
        
        if not current_proxy:
            logger.warning(f"⚠️ Rate limit hit for user {user_id} but no proxy configured")
            return False
        
        # Disable the faulty proxy
        await self.proxy_pool.disable_proxy_async(current_proxy, f"Rate limit error: {str(exception)[:50]}")
        
        # Try to get an alternative proxy
        new_proxy = await self.proxy_pool.get_alternative_proxy_async(current_proxy)
        
        if new_proxy:
            client_data['proxy'] = new_proxy
            logger.info(f"🔄 User {user_id} reassigned to new proxy after rate limit")
            return True
        else:
            logger.warning(f"⚠️ No alternative proxy available for user {user_id}")
            return False
    
    async def execute_with_retry_async(self, client_data: dict, operation_name: str, 
                                        coro_factory, max_retries: int = None):
        """
        Execute an async operation with retry logic on rate limit errors.
        
        Args:
            client_data: The client data dict with exchange and proxy info
            operation_name: Name of operation for logging
            coro_factory: Callable that returns the coroutine to execute
            max_retries: Maximum retry attempts (uses proxy_pool default if None)
            
        Returns:
            The result of the operation, or raises the exception if all retries fail
        """
        user_id = client_data['id']
        node_name = client_data.get('fullname', str(user_id))
        max_retries = max_retries or self.proxy_pool.max_retries
        
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return await coro_factory()
            except Exception as e:
                last_exception = e
                
                if self.is_rate_limit_error(e):
                    logger.warning(f"⚠️ Rate limit error for {node_name} ({operation_name}), attempt {attempt + 1}/{max_retries + 1}")
                    
                    if attempt < max_retries:
                        # Try to get a new proxy
                        can_retry = await self.handle_rate_limit_error_async(user_id, client_data, e)
                        
                        if can_retry:
                            # Wait a bit before retry
                            await asyncio.sleep(1 + attempt)
                            # Note: Caller needs to recreate exchange instance with new proxy
                            # For now, we just log and continue - the exchange instance keeps its proxy
                            logger.info(f"🔄 Retrying {operation_name} for {node_name} with new proxy...")
                            continue
                        else:
                            # No alternative proxy, wait longer and retry anyway
                            await asyncio.sleep(5)
                    else:
                        logger.error(f"❌ Max retries ({max_retries}) exhausted for {node_name} ({operation_name})")
                else:
                    # Not a rate limit error, raise immediately
                    raise
        
        # All retries exhausted
        if last_exception:
            raise last_exception

    async def close_async_connections(self):
        """Close all async CCXT exchange connections properly"""
        logger.info("🔒 Closing async exchange connections...")
        
        # Close master clients
        for master_data in self.master_clients:
            if master_data.get('is_async') and master_data.get('is_ccxt'):
                try:
                    exchange = master_data['client']
                    await exchange.close()
                    logger.info(f"   ✅ Closed {master_data.get('fullname', 'Unknown')}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Error closing {master_data.get('fullname', 'Unknown')}: {e}")
        
        # Close slave clients
        for slave_data in self.slave_clients:
            if slave_data.get('is_async') and slave_data.get('is_ccxt'):
                try:
                    exchange = slave_data['client']
                    await exchange.close()
                    logger.info(f"   ✅ Closed {slave_data.get('fullname', 'Unknown')}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Error closing {slave_data.get('fullname', 'Unknown')}: {e}")
        
        logger.info("🔒 All async connections closed")

    def close_connections(self):
        """Close all exchange connections - SYNC WRAPPER"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.close_async_connections())
            else:
                loop.run_until_complete(self.close_async_connections())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.close_async_connections())
            finally:
                loop.close()

    def get_master_max_positions(self) -> int:
        """Get the current max_positions setting for master account (read dynamically from Redis/database)"""
        val = self._get_global_setting('max_positions', getattr(Config, 'GLOBAL_MAX_POSITIONS', 10))
        try:
            return max(1, int(val))
        except (TypeError, ValueError):
            return max(1, getattr(Config, 'GLOBAL_MAX_POSITIONS', 10))

    def _get_global_setting(self, key: str, default):
        """Read global trading settings from Redis/app/module cache with fallback."""
        # Try Redis first (updated immediately when admin changes settings, works across processes)
        try:
            import redis
            if hasattr(self.app, 'config') and self.app.config.get('REDIS_URL'):
                redis_url = self.app.config.get('REDIS_URL')
                sync_redis = redis.from_url(redis_url)
                cached_val = sync_redis.get(f'global_settings:{key}')
                if cached_val is not None:
                    val = cached_val.decode() if isinstance(cached_val, (bytes, bytearray)) else cached_val
                    # Update cached reference for consistency
                    if self._global_settings is not None:
                        self._global_settings[key] = val
                    return val
        except Exception as e:
            logger.debug(f"Could not read global setting {key} from Redis: {e}")

        # Fallback to app module (works for same process, but worker is separate)
        try:
            import app as app_module
            if hasattr(app_module, 'GLOBAL_TRADE_SETTINGS'):
                val = app_module.GLOBAL_TRADE_SETTINGS.get(key, default)
                if self._global_settings is not None:
                    self._global_settings[key] = val
                return val
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not read GLOBAL_TRADE_SETTINGS from app module: {e}")

        # Use cached reference if available
        if self._global_settings is not None:
            return self._global_settings.get(key, default)

        return default

    # ==================== GLOBAL MASTER PENDING (REDIS) ====================

    MASTER_PENDING_REDIS_KEY = "master:pending_symbols"
    MASTER_PENDING_TTL_SECONDS = 30  # Reduced from 180 - individual symbols auto-expire after 30s

    def _get_sync_redis(self):
        """Get a sync Redis client for cross-process master position guarding."""
        if self._sync_redis:
            return self._sync_redis
        redis_url = None
        try:
            if hasattr(self.app, 'config'):
                redis_url = self.app.config.get('REDIS_URL')
        except Exception:
            redis_url = None
        if not redis_url:
            return None
        try:
            import redis
            with self._sync_redis_lock:
                if not self._sync_redis:
                    self._sync_redis = redis.from_url(redis_url)
            return self._sync_redis
        except Exception as e:
            logger.debug(f"Could not initialize sync Redis client: {e}")
            return None

    def _reserve_master_pending_symbol_sync(self, symbol: str, max_pos: int, open_count: int):
        """Atomically reserve a master slot in Redis. Returns 'added', 'max', 'already', or None.
        
        Uses individual keys per symbol with TTL so each symbol auto-expires independently.
        """
        redis_client = self._get_sync_redis()
        if not redis_client:
            return None
        
        pending_key = f"{self.MASTER_PENDING_REDIS_KEY}:{symbol}"
        
        try:
            # Check if already pending
            if redis_client.exists(pending_key):
                return "already"
            
            # Count current pending symbols
            pattern = f"{self.MASTER_PENDING_REDIS_KEY}:*"
            pending_keys = list(redis_client.scan_iter(match=pattern, count=100))
            pending_count = len(pending_keys)
            
            total = open_count + pending_count
            if total >= max_pos:
                return "max"
            
            # Reserve this symbol with TTL (auto-expires if trade fails/hangs)
            redis_client.setex(pending_key, self.MASTER_PENDING_TTL_SECONDS, "1")
            return "added"
            
        except Exception as e:
            logger.debug(f"Redis reserve master pending failed: {e}")
            return None

    async def _reserve_master_pending_symbol_async(self, symbol: str, max_pos: int, open_count: int):
        return await asyncio.to_thread(self._reserve_master_pending_symbol_sync, symbol, max_pos, open_count)

    def _release_master_pending_symbol_sync(self, symbol: str):
        """Release a pending symbol from Redis."""
        redis_client = self._get_sync_redis()
        if not redis_client:
            return
        try:
            pending_key = f"{self.MASTER_PENDING_REDIS_KEY}:{symbol}"
            redis_client.delete(pending_key)
            # Also remove from legacy set if it exists
            redis_client.srem(self.MASTER_PENDING_REDIS_KEY, symbol)
        except Exception as e:
            logger.debug(f"Redis release master pending failed: {e}")

    async def _release_master_pending_symbol_async(self, symbol: str):
        await asyncio.to_thread(self._release_master_pending_symbol_sync, symbol)

    def _get_master_pending_symbols_sync(self) -> set:
        """Get all currently pending symbols from Redis."""
        redis_client = self._get_sync_redis()
        if not redis_client:
            return set()
        try:
            symbols = set()
            
            # Get from new per-symbol keys
            pattern = f"{self.MASTER_PENDING_REDIS_KEY}:*"
            for key in redis_client.scan_iter(match=pattern, count=100):
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                # Extract symbol from key: "master:pending_symbols:BTCUSDT" -> "BTCUSDT"
                symbol = key.split(':')[-1]
                if symbol:
                    symbols.add(symbol)
            
            # Also check legacy set for backward compatibility
            legacy_members = redis_client.smembers(self.MASTER_PENDING_REDIS_KEY)
            for member in legacy_members:
                if isinstance(member, bytes):
                    member = member.decode('utf-8')
                symbols.add(member)
            
            return symbols
        except Exception as e:
            logger.debug(f"Redis get master pending symbols failed: {e}")
            return set()

    async def _get_master_pending_symbols_async(self) -> set:
        return await asyncio.to_thread(self._get_master_pending_symbols_sync)
    
    def clear_all_master_pending_symbols(self):
        """Clear all pending symbols from Redis. Called on startup to reset state."""
        redis_client = self._get_sync_redis()
        if not redis_client:
            return
        try:
            # Clear per-symbol keys
            pattern = f"{self.MASTER_PENDING_REDIS_KEY}:*"
            keys_to_delete = list(redis_client.scan_iter(match=pattern, count=100))
            if keys_to_delete:
                redis_client.delete(*keys_to_delete)
                logger.info(f"🧹 Cleared {len(keys_to_delete)} pending symbol keys from Redis")
            
            # Clear legacy set
            redis_client.delete(self.MASTER_PENDING_REDIS_KEY)
            
            # Clear in-memory pending
            if 'master' in self.pending_trades:
                self.pending_trades['master'].clear()
                
            logger.info("🧹 All master pending symbols cleared")
        except Exception as e:
            logger.warning(f"Failed to clear pending symbols: {e}")

    def get_min_balance_required(self) -> float:
        """Get the minimum balance required for trading (set by admin)"""
        val = self._get_global_setting('min_balance', 1.0)
        try:
            return max(0.0, float(val))  # Allow 0 to disable check
        except (TypeError, ValueError):
            return 1.0

    def init_master(self):
        """Initialize master trading accounts from ALL enabled ExchangeConfigs"""
        self.master_clients = []
        
        with self.app.app_context():
            # Load all enabled and verified exchange configs (admin's exchanges)
            exchange_configs = ExchangeConfig.query.filter_by(
                is_enabled=True,
                is_verified=True
            ).all()
            
            logger.info(f"📊 Found {len(exchange_configs)} enabled & verified exchange configs for MASTER")
            
            for ec in exchange_configs:
                exchange_name = ec.exchange_name.lower()
                api_key = ec.admin_api_key  # Admin's API key
                api_secret = ec.get_admin_api_secret()  # Admin's secret
                passphrase = ec.get_admin_passphrase()  # Admin's passphrase
                
                if not api_key or not api_secret:
                    logger.warning(f"⚠️ Master {exchange_name.upper()} has no API keys configured")
                    continue
                
                try:
                    if exchange_name == 'binance':
                        # Verify outgoing IP for troubleshooting -2015 errors
                        logger.info("🔍 Verifying outgoing IP for Binance API...")
                        outgoing_ip = verify_outgoing_ip()
                        
                        # Use Binance client with IPv4 preference to avoid IP mismatch
                        # This fixes APIError(code=-2015): Invalid API-key, IP, or permissions
                        logger.info("🔗 Connecting to Binance Futures API...")
                        client = create_binance_client_with_ipv4(api_key, api_secret, testnet=Config.IS_TESTNET)
                        
                        # Test connection with detailed error handling
                        try:
                            account_status = client.get_account_status()
                            logger.info(f"✅ Binance account status: {account_status.get('msg', 'OK')}")
                        except BinanceAPIException as e:
                            if e.code == -2015:
                                logger.error("=" * 60)
                                logger.error("❌ BINANCE API ERROR: Invalid API-key, IP, or permissions!")
                                logger.error("=" * 60)
                                logger.error(f"   Error code: {e.code}")
                                logger.error(f"   Error message: {e.message}")
                                logger.error(f"   Detected outgoing IP: {outgoing_ip}")
                                logger.error("")
                                logger.error("   TROUBLESHOOTING:")
                                logger.error("   1. Verify your VPS IP in Binance API settings")
                                logger.error("   2. Ensure API key has Futures permissions enabled")
                                logger.error("   3. Check if server is using IPv6 (API key might be IPv4 only)")
                                logger.error("   4. Try regenerating the API key and re-adding the IP")
                                logger.error("=" * 60)
                            raise
                        
                        # Set one-way position mode
                        try:
                            client.futures_change_position_mode(dualSidePosition=False)
                        except BinanceAPIException as e:
                            if "No need to change position side" not in str(e):
                                logger.warning(f"Position mode warning: {e}")
                        
                        # Keep legacy master_client for backward compatibility
                        self.master_client = client
                        
                        self.master_clients.append({
                            'id': 'master',
                            'name': 'MASTER_BINANCE',
                            'fullname': 'MASTER (Binance)',
                            'client': client,
                            'exchange_type': 'binance',
                            'exchange_name': 'Binance',
                            'is_paused': False,
                            'is_ccxt': False,
                            'lock': threading.Lock()
                        })
                        logger.info(f"✅ Master BINANCE connected")
                    
                    else:
                        # Use async CCXT for other exchanges
                        ccxt_class_name = SUPPORTED_EXCHANGES.get(exchange_name, exchange_name)
                        if not hasattr(ccxt_async, ccxt_class_name):
                            logger.warning(f"⚠️ Master exchange {exchange_name} not supported by CCXT")
                            continue
                        
                        exchange_class = getattr(ccxt_async, ccxt_class_name)
                        config = {
                            'apiKey': api_key,
                            'secret': api_secret,
                            'enableRateLimit': True,
                            'options': {
                                'defaultType': 'swap',  # Use perpetual futures
                                'forcePublicIPv4': True,  # Force IPv4 for CCXT
                            }
                        }
                        
                        # OKX-specific options
                        if exchange_name == 'okx':
                            config['options']['defaultMarginMode'] = 'cross'
                            # Use net position mode (one-way) for OKX
                            config['options']['positionMode'] = 'net_mode'
                        
                        if passphrase and exchange_name in PASSPHRASE_EXCHANGES:
                            config['password'] = passphrase
                        
                        ccxt_client = exchange_class(config)
                        
                        # Test connection (sync for init, will use async in trading)
                        try:
                            # Run async fetch_balance in sync context for initialization
                            loop = asyncio.new_event_loop()
                            balance = loop.run_until_complete(ccxt_client.fetch_balance())
                            loop.close()
                            logger.info(f"📊 Master {exchange_name.upper()} balance fetched successfully")
                        except Exception as e:
                            logger.error(f"⚠️ Master {exchange_name.upper()} connection failed: {e}")
                            try:
                                loop = asyncio.new_event_loop()
                                loop.run_until_complete(ccxt_client.close())
                                loop.close()
                            except:
                                pass
                            continue
                        
                        self.master_clients.append({
                            'id': f'master_{exchange_name}',
                            'name': f'MASTER_{exchange_name.upper()}',
                            'fullname': f'MASTER ({exchange_name.upper()})',
                            'client': ccxt_client,
                            'exchange_type': exchange_name,
                            'exchange_name': exchange_name.upper(),
                            'is_paused': False,
                            'is_ccxt': True,
                            'is_async': True,  # Flag for async client
                            'lock': None  # Will be created on demand in async context
                        })
                        logger.info(f"✅ Master {exchange_name.upper()} connected (async)")
                
                except Exception as e:
                    logger.error(f"❌ Master {exchange_name.upper()} connection failed: {e}")
            
            # Fallback: Try legacy config.ini keys if no exchanges loaded
            if not self.master_clients and Config.BINANCE_MASTER_KEY and Config.BINANCE_MASTER_SECRET:
                try:
                    client = Client(
                        Config.BINANCE_MASTER_KEY, 
                        Config.BINANCE_MASTER_SECRET, 
                        testnet=Config.IS_TESTNET
                    )
                    client.get_account_status()
                    
                    try:
                        client.futures_change_position_mode(dualSidePosition=False)
                    except BinanceAPIException as e:
                        if "No need to change position side" not in str(e):
                            logger.warning(f"Position mode warning: {e}")
                    
                    self.master_client = client
                    self.master_clients.append({
                        'id': 'master',
                        'name': 'MASTER_BINANCE',
                        'fullname': 'MASTER (Binance Legacy)',
                        'client': client,
                        'exchange_type': 'binance',
                        'exchange_name': 'Binance',
                        'is_paused': False,
                        'is_ccxt': False,
                        'lock': threading.Lock()
                    })
                    logger.info("✅ Master Binance connected (from config.ini)")
                except Exception as e:
                    logger.critical(f"❌ Master Binance (legacy) connection failed: {e}")
            
            if self.master_clients:
                logger.info(f"✅ Master Account Connected ({len(self.master_clients)} exchanges)")
                for mc in self.master_clients:
                    logger.info(f"   📌 {mc['fullname']}")
                if self.telegram:
                    exchanges_str = ", ".join([mc['exchange_name'] for mc in self.master_clients])
                    self.telegram.notify_system_event("Master Connected", f"Підключено {len(self.master_clients)} бірж: {exchanges_str}")
                
                # Clear any stale pending symbols from previous run
                self.clear_all_master_pending_symbols()
            else:
                logger.critical("❌ No master exchanges connected!")
                if self.telegram:
                    self.telegram.notify_error("MASTER", "SYSTEM", "Не вдалося підключити жодну біржу")

    def load_slaves(self):
        """Load all active slave accounts from UserExchange table (multi-exchange support)"""
        with self.app.app_context():
            new_slaves = []
            
            # Debug: Show all UserExchange records and their status
            all_user_exchanges = UserExchange.query.all()
            logger.info(f"📊 Total UserExchange records in database: {len(all_user_exchanges)}")
            for ue in all_user_exchanges:
                user = db.session.get(User, ue.user_id)
                username = user.username if user else 'Unknown'
                logger.info(f"   📋 {username} -> {ue.exchange_name.upper()}: status={ue.status}, trading_enabled={ue.trading_enabled}, is_active={ue.is_active}")
            
            # Load from new UserExchange table - active and trading-enabled exchanges
            user_exchanges = UserExchange.query.filter(
                UserExchange.status == 'APPROVED',
                UserExchange.trading_enabled == True,
                UserExchange.is_active == True
            ).all()
            
            logger.info(f"📊 UserExchange records matching criteria (APPROVED + trading_enabled + is_active): {len(user_exchanges)}")
            
            for ue in user_exchanges:
                user = db.session.get(User, ue.user_id)
                if not user or user.role == 'admin' or not user.is_active:
                    continue
                
                exchange_name = ue.exchange_name.lower()
                api_key = ue.api_key
                api_secret = ue.get_api_secret()
                passphrase = ue.get_passphrase()
                
                if not api_key or not api_secret:
                    logger.warning(f"⚠️ User {user.username} exchange {exchange_name} has no API keys")
                    continue
                
                try:
                    # Get proxy for this user (round-robin assignment)
                    user_proxy = self.proxy_pool.get_proxy_for_user(user.id)
                    proxy_config = self.proxy_pool.get_proxy_config_for_ccxt(user_proxy)
                    binance_proxy_config = self.proxy_pool.get_proxy_config_for_binance(user_proxy)
                    
                    # Create client based on exchange type
                    if exchange_name == 'binance':
                        # Use Binance client for Binance
                        # python-binance supports proxies via requests_params
                        client_kwargs = {'testnet': Config.IS_TESTNET}
                        if binance_proxy_config:
                            client_kwargs['requests_params'] = binance_proxy_config
                        
                        cli = Client(api_key, api_secret, **client_kwargs)
                        try:
                            cli.futures_account_balance()
                        except BinanceAPIException as e:
                            if e.code in [-2014, -2015]:
                                logger.error(f"⚠️ User {user.username} Binance API key rejected - skipping")
                                continue
                            raise
                        try:
                            cli.futures_change_position_mode(dualSidePosition=False)
                        except BinanceAPIException:
                            pass
                        
                        new_slaves.append({
                            'id': user.id,
                            'exchange_id': ue.id,
                            'name': user.username,
                            'fullname': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                            'client': cli,
                            'exchange_type': 'binance',
                            'exchange_name': ue.label or 'Binance',
                            'is_paused': user.is_paused,
                            'risk': 0,
                            'leverage': 0,
                            'max_pos': 0,
                            'risk_multiplier': 1.0,
                            'telegram_chat_id': user.telegram_chat_id if user.telegram_enabled else None,
                            'lock': threading.Lock(),
                            'proxy': user_proxy,  # Store assigned proxy for retry logic
                            'subscription_expires_at': user.subscription_expires_at,  # For subscription check
                            # Smart Features settings
                            'dca_enabled': getattr(user, 'dca_enabled', False),
                            'dca_multiplier': getattr(user, 'dca_multiplier', 1.0),
                            'dca_threshold': getattr(user, 'dca_threshold', -2.0),
                            'dca_max_orders': getattr(user, 'dca_max_orders', 3),
                            'trailing_sl_enabled': getattr(user, 'trailing_sl_enabled', False),
                            'trailing_sl_activation': getattr(user, 'trailing_sl_activation', 1.0),
                            'trailing_sl_callback': getattr(user, 'trailing_sl_callback', 0.5),
                            # Risk Guardrails settings
                            'risk_guardrails_enabled': getattr(user, 'risk_guardrails_enabled', False),
                            'daily_drawdown_limit_perc': getattr(user, 'daily_drawdown_limit_perc', 10.0),
                            'daily_profit_target_perc': getattr(user, 'daily_profit_target_perc', 20.0),
                        })
                        if user_proxy:
                            logger.info(f"✅ Loaded Binance for {user.username} (proxy: {self.proxy_pool._mask_proxy(user_proxy)})")
                        else:
                            logger.info(f"✅ Loaded Binance for {user.username}")
                    
                    else:
                        # Use async CCXT for other exchanges
                        ccxt_class_name = SUPPORTED_EXCHANGES.get(exchange_name, exchange_name)
                        if not hasattr(ccxt_async, ccxt_class_name):
                            logger.warning(f"⚠️ Exchange {exchange_name} not supported by CCXT")
                            continue
                        
                        exchange_class = getattr(ccxt_async, ccxt_class_name)
                        config = {
                            'apiKey': api_key,
                            'secret': api_secret,
                            'enableRateLimit': True,
                            'options': {
                                'defaultType': 'swap',  # Use perpetual futures
                                'forcePublicIPv4': True,  # Force IPv4 for CCXT
                            }
                        }
                        if passphrase:
                            config['password'] = passphrase
                        
                        # Add proxy configuration for CCXT
                        if proxy_config:
                            config.update(proxy_config)
                        
                        ccxt_client = exchange_class(config)
                        
                        # Test connection (sync for init)
                        try:
                            loop = asyncio.new_event_loop()
                            loop.run_until_complete(ccxt_client.fetch_balance())
                            loop.close()
                        except Exception as e:
                            logger.error(f"⚠️ User {user.username} {exchange_name} connection failed: {e}")
                            try:
                                loop = asyncio.new_event_loop()
                                loop.run_until_complete(ccxt_client.close())
                                loop.close()
                            except:
                                pass
                            continue
                        
                        new_slaves.append({
                            'id': user.id,
                            'exchange_id': ue.id,
                            'name': user.username,
                            'fullname': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                            'client': ccxt_client,
                            'exchange_type': exchange_name,
                            'exchange_name': ue.label or exchange_name.upper(),
                            'is_paused': user.is_paused,
                            'risk': 0,
                            'leverage': 0,
                            'max_pos': 0,
                            'risk_multiplier': 1.0,
                            'telegram_chat_id': user.telegram_chat_id if user.telegram_enabled else None,
                            'lock': asyncio.Lock(),
                            'is_ccxt': True,  # Flag to use CCXT methods
                            'is_async': True,  # Flag for async client
                            'proxy': user_proxy,  # Store assigned proxy for retry logic
                            'subscription_expires_at': user.subscription_expires_at,  # For subscription check
                            # Smart Features settings
                            'dca_enabled': getattr(user, 'dca_enabled', False),
                            'dca_multiplier': getattr(user, 'dca_multiplier', 1.0),
                            'dca_threshold': getattr(user, 'dca_threshold', -2.0),
                            'dca_max_orders': getattr(user, 'dca_max_orders', 3),
                            'trailing_sl_enabled': getattr(user, 'trailing_sl_enabled', False),
                            'trailing_sl_activation': getattr(user, 'trailing_sl_activation', 1.0),
                            'trailing_sl_callback': getattr(user, 'trailing_sl_callback', 0.5),
                            # Risk Guardrails settings
                            'risk_guardrails_enabled': getattr(user, 'risk_guardrails_enabled', False),
                            'daily_drawdown_limit_perc': getattr(user, 'daily_drawdown_limit_perc', 10.0),
                            'daily_profit_target_perc': getattr(user, 'daily_profit_target_perc', 20.0),
                        })
                        if user_proxy:
                            logger.info(f"✅ Loaded {exchange_name.upper()} for {user.username} (async, proxy: {self.proxy_pool._mask_proxy(user_proxy)})")
                        else:
                            logger.info(f"✅ Loaded {exchange_name.upper()} for {user.username} (async)")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to load {user.username} ({exchange_name}): {e}")
            
            # Also load legacy users with direct API keys (backward compatibility)
            legacy_users = User.query.filter_by(is_active=True).all()
            for u in legacy_users:
                if u.role == 'admin':
                    continue
                # Skip if user already has exchanges loaded
                if any(s['id'] == u.id for s in new_slaves):
                    continue
                    
                ak, ase = u.get_keys()
                if not ak or not ase:
                    continue
                
                try:
                    # Get proxy for this legacy user
                    user_proxy = self.proxy_pool.get_proxy_for_user(u.id)
                    binance_proxy_config = self.proxy_pool.get_proxy_config_for_binance(user_proxy)
                    
                    client_kwargs = {'testnet': Config.IS_TESTNET}
                    if binance_proxy_config:
                        client_kwargs['requests_params'] = binance_proxy_config
                    
                    cli = Client(ak, ase, **client_kwargs)
                    try:
                        cli.futures_account_balance()
                    except BinanceAPIException as e:
                        if e.code in [-2014, -2015]:
                            continue
                        raise
                    try:
                        cli.futures_change_position_mode(dualSidePosition=False)
                    except BinanceAPIException:
                        pass
                    
                    new_slaves.append({
                        'id': u.id,
                        'exchange_id': None,
                        'name': u.username,
                        'fullname': f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username,
                        'client': cli,
                        'exchange_type': 'binance',
                        'exchange_name': 'Binance (Legacy)',
                        'is_paused': u.is_paused,
                        'risk': 0,
                        'leverage': 0,
                        'max_pos': 0,
                        'risk_multiplier': 1.0,
                        'telegram_chat_id': u.telegram_chat_id if u.telegram_enabled else None,
                        'lock': threading.Lock(),
                        'proxy': user_proxy,  # Store assigned proxy for retry logic
                        # Smart Features settings
                        'dca_enabled': getattr(u, 'dca_enabled', False),
                        'dca_multiplier': getattr(u, 'dca_multiplier', 1.0),
                        'dca_threshold': getattr(u, 'dca_threshold', -2.0),
                        'dca_max_orders': getattr(u, 'dca_max_orders', 3),
                        'trailing_sl_enabled': getattr(u, 'trailing_sl_enabled', False),
                        'trailing_sl_activation': getattr(u, 'trailing_sl_activation', 1.0),
                        'trailing_sl_callback': getattr(u, 'trailing_sl_callback', 0.5),
                        # Risk Guardrails settings
                        'risk_guardrails_enabled': getattr(u, 'risk_guardrails_enabled', False),
                        'daily_drawdown_limit_perc': getattr(u, 'daily_drawdown_limit_perc', 10.0),
                        'daily_profit_target_perc': getattr(u, 'daily_profit_target_perc', 20.0),
                    })
                    if user_proxy:
                        logger.info(f"✅ Loaded legacy Binance for {u.username} (proxy: {self.proxy_pool._mask_proxy(user_proxy)})")
                    else:
                        logger.info(f"✅ Loaded legacy Binance for {u.username}")
                except Exception as e:
                    logger.error(f"❌ Failed to load legacy {u.username}: {e}")
            
            with self.lock:
                self.slave_clients = new_slaves
                logger.info(f"🔄 Loaded {len(self.slave_clients)} slave accounts")
                
                # Log proxy pool stats if proxies are configured
                if self.proxy_pool.proxies:
                    stats = self.proxy_pool.get_stats()
                    logger.info(f"🔄 Proxy pool: {stats['total_proxies']} proxies, "
                               f"{stats['assigned_users']} users assigned, "
                               f"{stats['users_per_proxy']} users/proxy")

    def get_proxy_stats(self) -> dict:
        """Get current proxy pool statistics for monitoring."""
        return self.proxy_pool.get_stats()

    def get_precision(self, client, symbol: str) -> dict:
        """Get trading precision for a symbol"""
        if symbol in self.symbol_precision:
            return self.symbol_precision[symbol]
        
        try:
            self.api_limiter.wait_and_proceed("precision")
            info = client.futures_exchange_info()
            
            for s in info['symbols']:
                if s['symbol'] == symbol:
                    filters = {f['filterType']: f for f in s['filters']}
                    tick_size = float(filters.get('PRICE_FILTER', {}).get('tickSize', 0.01))
                    step_size = float(filters.get('LOT_SIZE', {}).get('stepSize', 0.001))
                    min_qty = float(filters.get('LOT_SIZE', {}).get('minQty', 0.001))
                    min_notional = float(filters.get('MIN_NOTIONAL', {}).get('notional', 5.0))
                    
                    self.symbol_precision[symbol] = {
                        'qty_prec': int(s['quantityPrecision']), 
                        'price_prec': int(s['pricePrecision']),
                        'tickSize': tick_size,
                        'stepSize': step_size,
                        'minQty': min_qty,
                        'minNotional': min_notional
                    }
                    return self.symbol_precision[symbol]
                    
        except Exception as e:
            logger.error(f"Failed to get precision for {symbol}: {e}")
            
        # Default fallback
        return {
            'qty_prec': 3, 'price_prec': 2,
            'tickSize': 0.01, 'stepSize': 0.001,
            'minQty': 0.001, 'minNotional': 5.0
        }

    def round_step(self, value: float, step: float) -> float:
        """Round value to step size"""
        if not step or step <= 0:
            return value
        precision = len(str(step).rstrip('0').split('.')[-1]) if '.' in str(step) else 0
        return round(round(value / step) * step, precision)

    def check_slippage(self, client, symbol: str, side: str, master_entry_price: float) -> bool:
        """Check if price slippage is acceptable"""
        if not master_entry_price or master_entry_price <= 0:
            return True
            
        try:
            self.api_limiter.wait_and_proceed("slippage")
            ticker = client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            diff = (current_price - master_entry_price) / master_entry_price
            
            # For LONG: reject if price increased too much
            # For SHORT: reject if price decreased too much
            if side.upper() == 'BUY' and diff > self.slippage_tolerance:
                return False
            if side.upper() == 'SELL' and diff < -self.slippage_tolerance:
                return False
                
            return True
            
        except Exception as e:
            logger.warning(f"Slippage check failed: {e}")
            return True  # Allow trade if check fails

    def log_event(self, user_id, symbol: str, message: str, is_error: bool = False):
        """Log event and notify via callback"""
        if is_error:
            logger.error(f"[{user_id}] {symbol}: {message}")
        else:
            logger.info(f"[{user_id}] {symbol}: {message}")
            
        if self.log_error_callback:
            try:
                self.log_error_callback(user_id, symbol, message, is_error)
            except Exception:
                pass

    async def get_all_master_positions_async(self) -> list:
        """Get positions from ALL master exchanges with exchange info - ASYNC VERSION"""
        all_positions = []
        
        async def fetch_from_master(master_data):
            positions_list = []
            exchange_name = master_data.get('exchange_name', 'Unknown')
            try:
                if master_data.get('is_async') and master_data.get('is_ccxt'):
                    # Async CCXT exchange
                    exchange = master_data['client']
                    positions = await exchange.fetch_positions()
                    for pos in positions:
                        contracts = float(pos.get('contracts', 0) or 0)
                        if contracts != 0:
                            symbol = pos.get('symbol', '').replace('/USDT:USDT', 'USDT').replace('/', '')
                            positions_list.append({
                                'symbol': symbol,
                                'amount': contracts if pos.get('side') == 'long' else -contracts,
                                'entry_price': float(pos.get('entryPrice', 0) or 0),
                                'unrealized_pnl': float(pos.get('unrealizedPnl', 0) or 0),
                                'side': 'LONG' if pos.get('side') == 'long' else 'SHORT',
                                'leverage': int(pos.get('leverage', 1) or 1),
                                'exchange': exchange_name
                            })
                elif not master_data.get('is_ccxt'):
                    # Binance client (sync)
                    client = master_data['client']
                    positions = client.futures_position_information()
                    for p in positions:
                        amt = float(p['positionAmt'])
                        if amt != 0:
                            positions_list.append({
                                'symbol': p['symbol'],
                                'amount': amt,
                                'entry_price': float(p['entryPrice']),
                                'unrealized_pnl': float(p['unRealizedProfit']),
                                'side': 'LONG' if amt > 0 else 'SHORT',
                                'leverage': int(p.get('leverage', 1)),
                                'exchange': exchange_name
                            })
            except BinanceAPIException as e:
                if e.code == -2015:
                    logger.error(f"❌ Binance API Error -2015 fetching positions from {exchange_name}!")
                    logger.error(f"   This means: Invalid API-key, IP, or permissions for action")
                    logger.error(f"   Verify: 1) API key IP whitelist, 2) Futures permissions enabled")
                else:
                    logger.warning(f"Binance API error fetching positions from {exchange_name}: {e}")
            except Exception as e:
                logger.warning(f"Error fetching positions from {exchange_name}: {e}")
            return positions_list
        
        tasks = [fetch_from_master(m) for m in self.master_clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_positions.extend(result)
        
        return all_positions

    def get_all_master_positions(self) -> list:
        """Get positions from ALL master exchanges with exchange info - SYNC WRAPPER"""
        # Check if any master is async
        has_async = any(m.get('is_async') for m in self.master_clients)
        
        if has_async:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Return cached/tracked positions if loop is running
                    with self.positions_lock:
                        return [{'symbol': s, **d} for s, d in self.master_positions.items()]
                return loop.run_until_complete(self.get_all_master_positions_async())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(self.get_all_master_positions_async())
                finally:
                    loop.close()
        
        # Legacy sync implementation
        all_positions = []
        for master_data in self.master_clients:
            exchange_name = master_data.get('exchange_name', 'Unknown')
            try:
                if not master_data.get('is_ccxt'):
                    client = master_data['client']
                    positions = client.futures_position_information()
                    for p in positions:
                        amt = float(p['positionAmt'])
                        if amt != 0:
                            all_positions.append({
                                'symbol': p['symbol'],
                                'amount': amt,
                                'entry_price': float(p['entryPrice']),
                                'unrealized_pnl': float(p['unRealizedProfit']),
                                'side': 'LONG' if amt > 0 else 'SHORT',
                                'leverage': int(p.get('leverage', 1)),
                                'exchange': exchange_name
                            })
            except BinanceAPIException as e:
                if e.code == -2015:
                    logger.error(f"❌ Binance API Error -2015 fetching positions from {exchange_name}!")
                    logger.error(f"   This means: Invalid API-key, IP, or permissions for action")
                    logger.error(f"   Verify: 1) API key IP whitelist, 2) Futures permissions enabled")
                else:
                    logger.warning(f"Binance API error fetching positions from {exchange_name}: {e}")
            except Exception as e:
                logger.warning(f"Error fetching positions from {exchange_name}: {e}")
        
        return all_positions

    async def get_all_master_balances_async(self) -> list:
        """Get balances from ALL master exchanges - ASYNC VERSION"""
        
        async def fetch_balance_from_master(master_data):
            exchange_name = master_data.get('exchange_name', 'Unknown')
            exchange_id = master_data.get('id', exchange_name)
            try:
                if master_data.get('is_async') and master_data.get('is_ccxt'):
                    # Async CCXT exchange
                    exchange = master_data['client']
                    balance = await exchange.fetch_balance()
                    usdt_balance = 0.0
                    for asset in ['USDT', 'USD']:
                        if asset in balance.get('free', {}):
                            usdt_balance = float(balance['free'][asset] or 0)
                            break
                        if asset in balance and isinstance(balance[asset], dict):
                            usdt_balance = float(balance[asset].get('free', 0) or 0)
                            break
                        if asset in balance.get('total', {}):
                            usdt_balance = float(balance['total'][asset] or 0)
                            break
                    return {
                        'id': exchange_id,
                        'exchange': exchange_name,
                        'balance': usdt_balance,
                        'error': None
                    }
                elif not master_data.get('is_ccxt'):
                    # Binance client (sync)
                    client = master_data['client']
                    bal_list = client.futures_account_balance()
                    usdt_balance = 0.0
                    for b in bal_list:
                        if b['asset'] == 'USDT':
                            usdt_balance = float(b.get('balance', 0))
                            break
                    return {
                        'id': exchange_id,
                        'exchange': exchange_name,
                        'balance': usdt_balance,
                        'error': None
                    }
            except Exception as e:
                logger.warning(f"Error fetching balance from {exchange_name}: {e}")
                return {
                    'id': exchange_id,
                    'exchange': exchange_name,
                    'balance': None,
                    'error': str(e)
                }
            return None
        
        tasks = [fetch_balance_from_master(m) for m in self.master_clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        balances = []
        for result in results:
            if isinstance(result, dict):
                balances.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Balance fetch exception: {result}")
        
        return balances

    def _run_async_balances_in_thread(self) -> list:
        """Helper to run async balances in a separate thread with its own event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.get_all_master_balances_async())
        finally:
            loop.close()

    def get_all_master_balances(self) -> list:
        """Get balances from ALL master exchanges - SYNC WRAPPER"""
        has_async = any(m.get('is_async') for m in self.master_clients)
        
        if has_async:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Event loop is running - use thread pool to run async code
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._run_async_balances_in_thread)
                        return future.result(timeout=15)
                return loop.run_until_complete(self.get_all_master_balances_async())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(self.get_all_master_balances_async())
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Error fetching async balances: {e}")
                return []
        
        # Legacy sync implementation for non-async clients
        balances = []
        for master_data in self.master_clients:
            exchange_name = master_data.get('exchange_name', 'Unknown')
            exchange_id = master_data.get('id', exchange_name)
            try:
                if not master_data.get('is_ccxt'):
                    client = master_data['client']
                    bal_list = client.futures_account_balance()
                    usdt_balance = 0.0
                    for b in bal_list:
                        if b['asset'] == 'USDT':
                            usdt_balance = float(b.get('balance', 0))
                            break
                    balances.append({
                        'id': exchange_id,
                        'exchange': exchange_name,
                        'balance': usdt_balance,
                        'error': None
                    })
            except Exception as e:
                logger.warning(f"Error fetching balance from {exchange_name}: {e}")
                balances.append({
                    'id': exchange_id,
                    'exchange': exchange_name,
                    'balance': None,
                    'error': str(e)
                })
        
        return balances

    def push_master_updates(self):
        """Push updates for ALL master exchanges"""
        if not self.socketio:
            return
        
        try:
            # Get all positions from all master exchanges
            positions = self.get_all_master_positions()
            
            # Get all balances from all master exchanges
            balances = self.get_all_master_balances()
            total_balance = sum(b['balance'] for b in balances if b['balance'] is not None)
            
            self.socketio.emit('master_data', {
                'balance': f"{total_balance:,.2f}",
                'positions': positions,
                'exchange_balances': balances
            }, room="admin_room")
            
        except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                urllib3.exceptions.ProtocolError) as e:
            # Client disconnected - this is expected behavior, log as warning only
            logger.warning(f"Could not push master updates: Client disconnected ({type(e).__name__})")
        except Exception as e:
            logger.error(f"Push master updates error: {e}")

    def push_update(self, user_id, client, is_master: bool = False, exchange_name: str = None):
        """Push real-time balance and position updates via WebSocket"""
        try:
            # For master updates with multiple exchanges, use push_master_updates
            if is_master and self.master_clients and len(self.master_clients) > 1:
                self.push_master_updates()
                return
            
            self.api_limiter.wait_and_proceed(f"update_{user_id}")
            
            balances = client.futures_account_balance()
            usdt_bal = "0.00"
            for b in balances:
                if b['asset'] == 'USDT':
                    usdt_bal = f"{float(b['balance']):,.2f}"
                    break
            
            positions_data = []
            positions_info = client.futures_position_information()
            
            for p in positions_info:
                amt = float(p['positionAmt'])
                if amt != 0:
                    pos_data = {
                        'symbol': p['symbol'],
                        'amount': amt,
                        'entry_price': float(p['entryPrice']),
                        'unrealized_pnl': float(p['unRealizedProfit']),
                        'side': 'LONG' if amt > 0 else 'SHORT',
                        'leverage': p.get('leverage', 1)
                    }
                    if exchange_name:
                        pos_data['exchange'] = exchange_name
                    positions_data.append(pos_data)
            
            if self.socketio:
                if is_master:
                    # Build exchange_balances for single master
                    exchange_balances = [{
                        'id': 'master',
                        'exchange': exchange_name or 'Binance',
                        'balance': float(usdt_bal.replace(',', '')),
                        'error': None
                    }]
                    self.socketio.emit('master_data', {
                        'balance': usdt_bal,
                        'positions': positions_data,
                        'exchange_balances': exchange_balances
                    }, room="admin_room")
                else:
                    self.socketio.emit('update_data', {
                        'balance': usdt_bal,
                        'positions': positions_data
                    }, room=f"user_{user_id}")
                    
                    # Also notify admin panel
                    self.socketio.emit('agent_update', {
                        'user_id': user_id,
                        'balance': usdt_bal,
                        'pos_count': len(positions_data)
                    }, room="admin_room")
                    
        except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                urllib3.exceptions.ProtocolError, OSError, BrokenPipeError) as e:
            # Client disconnected - this is expected behavior, log as warning only
            logger.warning(f"Could not push update to user {user_id}: Client disconnected ({type(e).__name__})")
        except Exception as e:
            # Check if this is a connection-related error wrapped in another exception
            err_str = str(e).lower()
            if any(term in err_str for term in ['connection', 'remote', 'disconnected', 'aborted', 'reset', 'broken pipe']):
                logger.warning(f"Network issue pushing update to user {user_id}: {type(e).__name__}")
            else:
                logger.error(f"Push update error for {user_id}: {e}")

    def snapshot_balance(self, user_id, client, retries: int = 2):
        """Save balance snapshot for charts with retry logic"""
        for attempt in range(retries + 1):
            try:
                self.api_limiter.wait_and_proceed(f"snapshot_{user_id}")
                balances = client.futures_account_balance()
                total_bal = 0.0
                
                for b in balances:
                    if b['asset'] == 'USDT':
                        total_bal = float(b.get('balance', 0))
                        break
                
                if total_bal <= 0:
                    return
                    
                with self.app.app_context():
                    db_uid = user_id if isinstance(user_id, int) else None
                    hist = BalanceHistory(user_id=db_uid, balance=total_bal)
                    db.session.add(hist)
                    db.session.commit()
                return  # Success
                    
            except (ConnectionError, ConnectionResetError) as e:
                if attempt < retries:
                    time.sleep(1)  # Wait before retry
                    continue
                logger.warning(f"Snapshot connection issue for {user_id} (retried {retries}x)")
            except Exception as e:
                if "Connection aborted" in str(e) or "RemoteDisconnected" in str(e):
                    if attempt < retries:
                        time.sleep(1)
                        continue
                    logger.warning(f"Snapshot network issue for {user_id}")
                else:
                    logger.error(f"Snapshot error for {user_id}: {e}")
                break

    def monitor_balances(self):
        """Background thread for monitoring balances"""
        tick = 0
        while True:
            try:
                time.sleep(1)
                tick += 1
                
                # Update master every 5 seconds
                if tick % 5 == 0:
                    # Use multi-exchange update if we have multiple master exchanges
                    if self.master_clients and len(self.master_clients) > 0:
                        self.executor.submit(self.push_master_updates)
                    elif self.master_client:
                        self.executor.submit(self.push_update, 'master', self.master_client, True)
                
                # Full update and snapshot every 60 seconds
                if tick % 60 == 0:
                    if self.master_client:
                        self.executor.submit(self.snapshot_balance, 'master', self.master_client)

                    with self.lock:
                        slaves_copy = list(self.slave_clients)
                        
                    for slave in slaves_copy:
                        if not slave['is_paused']:
                            self.executor.submit(self.push_update, slave['id'], slave['client'])
                            self.executor.submit(self.snapshot_balance, slave['id'], slave['client'])
                            time.sleep(0.05)
                            
            except Exception as e:
                logger.error(f"Monitor error: {e}")

    def monitor_position_closes(self):
        """Monitor master positions and sync closes to slaves"""
        while True:
            try:
                time.sleep(3)  # Check every 3 seconds
                
                if not self.master_client:
                    continue
                
                # Get current master positions
                try:
                    self.api_limiter.wait_and_proceed("position_monitor")
                    positions = self.master_client.futures_position_information()
                except Exception as e:
                    logger.debug(f"Position monitor fetch error: {e}")
                    continue
                
                current_positions = {}
                for p in positions:
                    amt = float(p['positionAmt'])
                    if amt != 0:
                        symbol = p['symbol']
                        current_positions[symbol] = {
                            'amount': amt,
                            'entry': float(p['entryPrice']),
                            'side': 'LONG' if amt > 0 else 'SHORT',
                            'pnl': float(p['unRealizedProfit']),
                            'leverage': int(p.get('leverage', 1))
                        }
                
                # Detect closed positions
                with self.positions_lock:
                    for symbol, old_pos in list(self.master_positions.items()):
                        if symbol not in current_positions:
                            # Position was closed!
                            logger.info(f"🔔 Detected CLOSE: {symbol} (was {old_pos['side']})")
                            
                            # Calculate PnL from last known unrealized PnL
                            pnl = old_pos.get('pnl', 0)
                            
                            # Calculate ROI correctly: ROI = (PnL / Margin) * 100
                            # Margin = (Quantity * Entry Price) / Leverage
                            leverage = old_pos.get('leverage', 1)
                            if leverage < 1:
                                leverage = 1
                            margin = (abs(old_pos['amount']) * old_pos['entry']) / leverage
                            roi = (pnl / margin) * 100 if margin > 0 else 0
                            
                            # Record to trade history
                            self._record_trade_close('master', symbol, old_pos['side'], pnl, old_pos['entry'], roi)
                            
                            # Sync close to all slaves
                            self.executor.submit(self._sync_close_to_slaves, symbol)
                            
                            # Notify via Telegram
                            if self.telegram:
                                self.telegram.notify_trade_closed("MASTER", symbol, old_pos['side'], pnl, roi)
                    
                    # Update tracked positions
                    self.master_positions = current_positions
                    
            except Exception as e:
                logger.error(f"Position monitor error: {e}")

    def _sync_close_to_slaves(self, symbol: str):
        """Close position on all slave accounts"""
        with self.lock:
            slaves_copy = list(self.slave_clients)
        
        for slave in slaves_copy:
            if slave['is_paused']:
                continue
                
            try:
                client = slave['client']
                node_name = slave.get('fullname', slave['name'])
                
                # Get slave's position for this symbol
                positions = client.futures_position_information(symbol=symbol)
                
                for p in positions:
                    amt = float(p['positionAmt'])
                    if amt != 0:
                        side = 'SELL' if amt > 0 else 'BUY'
                        pnl = float(p['unRealizedProfit'])
                        entry_price = float(p['entryPrice'])
                        
                        # Cancel existing orders
                        try:
                            client.futures_cancel_all_open_orders(symbol=symbol)
                        except Exception:
                            pass
                        
                        prec = self.get_precision(client, symbol)
                        qty_str = f"{abs(amt):.{prec['qty_prec']}f}"
                        
                        # Close position
                        self.order_limiter.wait_and_proceed(f"sync_{slave['id']}")
                        client.futures_create_order(
                            symbol=symbol,
                            side=side,
                            type='MARKET',
                            quantity=qty_str,
                            reduceOnly=True
                        )
                        
                        logger.info(f"✅ Synced CLOSE {symbol} for {node_name}")
                        self.log_event(slave['id'], symbol, f"SYNC CLOSED (Master closed)")
                        
                        # Record to history
                        margin = (abs(amt) * entry_price) / float(p.get('leverage', 1))
                        roi = (pnl / margin) * 100 if margin > 0 else 0
                        self._record_trade_close(slave['id'], symbol, 'LONG' if amt > 0 else 'SHORT', pnl, entry_price, roi, node_name)
                        
                        if self.telegram:
                            self.telegram.notify_trade_closed(node_name, symbol, 'LONG' if amt > 0 else 'SHORT', pnl, roi)
                            # Notify user's personal Telegram
                            user_tg = slave.get('telegram_chat_id')
                            if user_tg:
                                self.telegram.notify_user_trade_closed(user_tg, symbol, 'LONG' if amt > 0 else 'SHORT', pnl, roi)
                            
            except Exception as e:
                logger.error(f"Sync close error for {slave['name']}: {e}")

    def _record_trade_close(self, user_id, symbol: str, side: str, pnl: float, entry_price: float, roi: float = 0, node_name: str = "MASTER"):
        """Record closed trade to database"""
        try:
            with self.app.app_context():
                db_uid = user_id if isinstance(user_id, int) else None
                
                # ROI should be passed in, calculated as (PnL / Margin) * 100
                # Don't recalculate here as we don't have all needed info
                
                trade = TradeHistory(
                    user_id=db_uid,
                    symbol=symbol,
                    side=side,
                    pnl=pnl,
                    roi=roi,
                    node_name=node_name
                )
                db.session.add(trade)
                db.session.commit()
                
                logger.info(f"📝 Recorded trade: {symbol} {side} PnL: {pnl:.2f}$")
                
                # Emit to WebSocket for live update
                if self.socketio:
                    try:
                        self.socketio.emit('trade_closed', {
                            'symbol': symbol,
                            'side': side,
                            'pnl': round(pnl, 2),
                            'roi': round(roi, 2),
                            'node': node_name,
                            'time': datetime.now().strftime("%H:%M:%S %d/%m")
                        }, room="admin_room")
                    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                            urllib3.exceptions.ProtocolError) as e:
                        # Client disconnected - expected behavior, log as warning only
                        logger.warning(f"Could not emit trade_closed: Client disconnected ({type(e).__name__})")
                
                # Post to Twitter if ROI meets threshold (async, non-blocking)
                if pnl > 0 and roi > 0:
                    try:
                        from post_to_twitter import post_successful_trade
                        post_successful_trade(symbol=symbol, roi=roi, pnl=pnl)
                    except ImportError:
                        pass  # Twitter posting not available
                    except Exception as tw_err:
                        logger.debug(f"Twitter post skipped: {tw_err}")
                    
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")

    def close_all_for_user(self, user_id: int):
        """Emergency close all positions for a user"""
        slave = next((s for s in self.slave_clients if s['id'] == user_id), None)
        if not slave: 
            logger.error(f"Panic close failed: User {user_id} not found")
            return
        
        client = slave['client']
        logger.warning(f"🚨 PANIC CLOSE for user {user_id}")
        
        closed_count = 0
        try:
            positions = client.futures_position_information()
            
            for p in positions:
                amt = float(p['positionAmt'])
                if amt != 0:
                    symbol = p['symbol']
                    side = 'SELL' if amt > 0 else 'BUY'
                    
                    try:
                        # Cancel all orders first
                        try:
                            client.futures_cancel_all_open_orders(symbol=symbol)
                        except Exception:
                            pass

                        prec = self.get_precision(client, symbol)
                        qty_str = f"{abs(amt):.{prec['qty_prec']}f}"
                        
                        self.order_limiter.wait_and_proceed(f"panic_{user_id}")
                        client.futures_create_order(
                            symbol=symbol,
                            side=side,
                            type='MARKET',
                            quantity=qty_str,
                            reduceOnly=True
                        )
                        
                        closed_count += 1
                        self.log_event(user_id, symbol, "PANIC CLOSE EXECUTED", is_error=True)
                        
                    except Exception as e:
                        self.log_event(user_id, symbol, f"Panic fail: {e}", is_error=True)
            
            # Cancel remaining orders
            try:
                open_orders = client.futures_get_open_orders()
                for o in open_orders:
                    client.futures_cancel_order(symbol=o['symbol'], orderId=o['orderId'])
            except Exception:
                pass

            self.push_update(user_id, client)
            
            if self.telegram:
                self.telegram.notify_panic_close(slave['fullname'], closed_count)
                
        except Exception as e:
            logger.error(f"Panic global fail: {e}")

    def close_all_positions_master(self):
        """Emergency close all positions for ALL master exchanges (Binance + OKX + others)"""
        if not self.master_clients and not self.master_client:
            logger.error("Panic close failed: No master exchanges connected")
            return 0
        
        logger.warning("🚨 PANIC CLOSE for ALL MASTER EXCHANGES")
        total_closed = 0
        exchanges_processed = []
        
        # Process all master clients (multi-exchange)
        for master_data in self.master_clients:
            exchange_name = master_data.get('exchange_name', 'Unknown')
            fullname = master_data.get('fullname', exchange_name)
            
            try:
                if master_data.get('is_ccxt'):
                    # CCXT exchange (OKX, Bybit, etc.)
                    closed = self._panic_close_ccxt(master_data)
                    total_closed += closed
                    exchanges_processed.append(f"{fullname}: {closed}")
                    logger.warning(f"🚨 {fullname}: Closed {closed} positions")
                else:
                    # Binance native client
                    client = master_data.get('client')
                    if client:
                        closed = self._panic_close_binance(client, fullname)
                        total_closed += closed
                        exchanges_processed.append(f"{fullname}: {closed}")
                        logger.warning(f"🚨 {fullname}: Closed {closed} positions")
            except Exception as e:
                logger.error(f"Panic close error for {fullname}: {e}")
                exchanges_processed.append(f"{fullname}: ERROR")
        
        # Fallback: legacy master_client if no master_clients processed
        if not self.master_clients and self.master_client:
            try:
                closed = self._panic_close_binance(self.master_client, "MASTER (Legacy)")
                total_closed += closed
                exchanges_processed.append(f"Legacy Binance: {closed}")
            except Exception as e:
                logger.error(f"Legacy master panic fail: {e}")
        
        # Clear all tracked master positions
        with self.positions_lock:
            self.master_positions.clear()
        
        # Notify about positions closed on each exchange
        if self.telegram and total_closed > 0:
            details = ", ".join(exchanges_processed)
            self.telegram.notify_system_event(
                f"PANIC CLOSE: {total_closed} positions",
                details
            )
        
        logger.warning(f"🚨 PANIC CLOSE COMPLETE: {total_closed} total positions closed")
        return total_closed
    
    def _panic_close_binance(self, client, name: str) -> int:
        """Close all positions on a Binance client"""
        closed_count = 0
        try:
            positions = client.futures_position_information()
            
            for p in positions:
                amt = float(p['positionAmt'])
                if amt != 0:
                    symbol = p['symbol']
                    side = 'SELL' if amt > 0 else 'BUY'
                    
                    try:
                        # Cancel all orders first
                        try:
                            client.futures_cancel_all_open_orders(symbol=symbol)
                        except Exception:
                            pass

                        prec = self.get_precision(client, symbol)
                        qty_str = f"{abs(amt):.{prec['qty_prec']}f}"
                        
                        self.order_limiter.wait_and_proceed(f"panic_{name}")
                        client.futures_create_order(
                            symbol=symbol,
                            side=side,
                            type='MARKET',
                            quantity=qty_str,
                            reduceOnly=True
                        )
                        
                        closed_count += 1
                        logger.warning(f"🚨 [{name}] Closed {symbol}")
                        
                        # Notify about this closure
                        if self.telegram:
                            self.telegram.notify_trade_closed(name, symbol, 'LONG' if amt > 0 else 'SHORT', 0, 0)
                        
                    except Exception as e:
                        logger.error(f"[{name}] Panic fail {symbol}: {e}")
            
            # Cancel all remaining orders
            try:
                open_orders = client.futures_get_open_orders()
                for o in open_orders:
                    client.futures_cancel_order(symbol=o['symbol'], orderId=o['orderId'])
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"[{name}] Panic global fail: {e}")
        
        return closed_count
    
    async def _panic_close_ccxt_async(self, master_data: dict) -> int:
        """Close all positions on a CCXT exchange (OKX, Bybit, etc.) - ASYNC VERSION"""
        exchange = master_data.get('client')
        name = master_data.get('fullname', 'CCXT')
        closed_count = 0
        
        try:
            # Fetch all open positions
            positions = await exchange.fetch_positions()
            
            for pos in positions:
                contracts = float(pos.get('contracts', 0) or 0)
                if contracts == 0:
                    continue
                
                symbol = pos.get('symbol')
                side = pos.get('side', 'long')  # 'long' or 'short'
                
                try:
                    # Cancel all orders for this symbol first
                    try:
                        await exchange.cancel_all_orders(symbol)
                    except Exception:
                        pass
                    
                    # Close position with market order
                    close_side = 'sell' if side == 'long' else 'buy'
                    
                    await self.order_limiter.wait_and_proceed_async(f"panic_{name}")
                    await exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=close_side,
                        amount=contracts,
                        params={'reduceOnly': True}
                    )
                    
                    closed_count += 1
                    logger.warning(f"🚨 [{name}] Closed {symbol}")
                    
                    # Notify about this closure
                    if self.telegram:
                        self.telegram.notify_trade_closed(name, symbol, side.upper(), 0, 0)
                    
                except Exception as e:
                    logger.error(f"[{name}] Panic fail {symbol}: {e}")
            
            # Cancel all remaining open orders
            try:
                open_orders = await exchange.fetch_open_orders()
                for order in open_orders:
                    try:
                        await exchange.cancel_order(order['id'], order['symbol'])
                    except Exception:
                        pass
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"[{name}] Panic global fail: {e}")
        
        return closed_count

    def _panic_close_ccxt(self, master_data: dict) -> int:
        """Close all positions on a CCXT exchange - SYNC WRAPPER"""
        if master_data.get('is_async'):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Cannot block, return 0
                    logger.warning(f"Cannot run sync panic close while async loop is running")
                    return 0
                return loop.run_until_complete(self._panic_close_ccxt_async(master_data))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(self._panic_close_ccxt_async(master_data))
                finally:
                    loop.close()
        else:
            # Legacy sync handling
            exchange = master_data.get('client')
            name = master_data.get('fullname', 'CCXT')
            logger.warning(f"[{name}] Sync CCXT panic close not supported for async exchanges")
            return 0

    def close_all_positions_all_accounts(self):
        """Emergency close all positions for ALL accounts (master + all slaves)"""
        logger.warning("🚨🚨🚨 GLOBAL PANIC CLOSE INITIATED 🚨🚨🚨")
        
        results = {
            'master_closed': 0,
            'slaves_closed': 0,
            'errors': []
        }
        
        # Close master positions first
        try:
            results['master_closed'] = self.close_all_positions_master()
            logger.warning(f"✅ Master: {results['master_closed']} positions closed")
        except Exception as e:
            results['errors'].append(f"Master: {e}")
            logger.error(f"Master panic error: {e}")
        
        # Close all slave positions
        for slave in self.slave_clients:
            try:
                self.close_all_for_user(slave['id'])
                results['slaves_closed'] += 1
            except Exception as e:
                results['errors'].append(f"{slave['fullname']}: {e}")
                logger.error(f"Slave {slave['fullname']} panic error: {e}")
        
        # Notify via Telegram
        if self.telegram:
            self.telegram.notify_global_panic(results['master_closed'], results['slaves_closed'])
        
        # Emit to admin
        if self.socketio:
            try:
                self.socketio.emit('panic_complete', results, room="admin_room")
            except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                    urllib3.exceptions.ProtocolError) as e:
                # Client disconnected - expected behavior, log as warning only
                logger.warning(f"Could not emit panic_complete: Client disconnected ({type(e).__name__})")
        
        logger.warning(f"🚨 GLOBAL PANIC COMPLETE: Master={results['master_closed']}, Slaves={results['slaves_closed']}")
        
        return results

    # Whale Alert threshold (profit in USD to trigger alert)
    WHALE_ALERT_THRESHOLD = 100.0  # Trigger whale alert for profits >= $100
    
    def record_closed_trade(self, user_id, node_name: str, symbol: str, side: str, pnl: float, roi: float):
        """Record closed trade to database and create referral commission if applicable"""
        try:
            with self.app.app_context():
                new_trade = TradeHistory(
                    user_id=user_id if isinstance(user_id, int) else None,
                    symbol=symbol,
                    side=side,
                    pnl=pnl,
                    roi=roi,
                    node_name=node_name
                )
                db.session.add(new_trade)
                db.session.commit()
                
                # Create referral commission if user was referred and trade was profitable
                if isinstance(user_id, int) and pnl > 0:
                    try:
                        from models import ReferralCommission
                        commission = ReferralCommission.create_from_profit(
                            referred_user_id=user_id,
                            trade_id=new_trade.id,
                            profit=pnl,
                            commission_rate=0.05  # 5% commission on profits
                        )
                        if commission:
                            db.session.commit()
                            logger.info(f"💰 Referral commission ${commission.amount:.2f} created for trade {new_trade.id}")
                    except Exception as ref_err:
                        logger.warning(f"Could not create referral commission: {ref_err}")
                
                trade_data = new_trade.to_dict()
                
                if self.socketio:
                    try:
                        self.socketio.emit('trade_closed', trade_data, room="admin_room")
                        if isinstance(user_id, int):
                            self.socketio.emit('trade_closed', trade_data, room=f"user_{user_id}")
                    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                            urllib3.exceptions.ProtocolError) as e:
                        # Client disconnected - expected behavior, log as warning only
                        logger.warning(f"Could not emit trade_closed: Client disconnected ({type(e).__name__})")
                
                logger.info(f"✅ Recorded: {node_name} closed {symbol} PnL: {pnl:.2f}")
                
                # Telegram notification
                if self.telegram:
                    self.telegram.notify_trade_closed(node_name, symbol, side, pnl, roi)
                
                # 🐋 WHALE ALERT - Broadcast to live chat when user makes large profit
                if isinstance(user_id, int) and pnl >= self.WHALE_ALERT_THRESHOLD:
                    try:
                        user = User.query.get(user_id)
                        if user:
                            self._broadcast_whale_alert(user.id, user.username, symbol, pnl)
                    except Exception as whale_err:
                        logger.warning(f"Could not broadcast whale alert: {whale_err}")
                
                # 🐦 Post to Twitter if ROI meets threshold (async, non-blocking)
                if pnl > 0 and roi > 0:
                    try:
                        from post_to_twitter import post_successful_trade
                        post_successful_trade(symbol=symbol, roi=roi, pnl=pnl)
                    except ImportError:
                        pass  # Twitter posting not available
                    except Exception as tw_err:
                        logger.debug(f"Twitter post skipped: {tw_err}")
                    
        except Exception as e:
            logger.error(f"❌ DB Save Error: {e}")
    
    def _broadcast_whale_alert(self, user_id: int, username: str, symbol: str, pnl: float, room: str = 'general'):
        """
        Broadcast a whale alert to the live chat when a user makes a large profit.
        
        Args:
            user_id: ID of the trader
            username: Username of the trader
            symbol: Trading pair (e.g., 'BTCUSDT')
            pnl: Profit amount in USD
            room: Chat room to broadcast to
        """
        try:
            from models import ChatMessage
            
            # Mask username for privacy
            if len(username) > 3:
                masked_name = username[0] + '*' * (len(username) - 2) + username[-1]
            else:
                masked_name = username
            
            # Format the whale alert message
            alert_message = f"🐋 {masked_name} just made +${abs(pnl):.2f} on {symbol}!"
            
            # Get admin/system user for the message
            admin_user = User.query.filter_by(role='admin').first()
            if not admin_user:
                admin_user = User.query.first()
            
            if admin_user:
                chat_msg = ChatMessage(
                    user_id=admin_user.id,
                    room=room,
                    message=alert_message,
                    message_type='whale_alert',
                    extra_data={
                        'type': 'whale_alert',
                        'trader_id': user_id,
                        'masked_username': masked_name,
                        'symbol': symbol,
                        'pnl': round(pnl, 2)
                    }
                )
                db.session.add(chat_msg)
                db.session.commit()
                
                # Broadcast to chat room via SocketIO
                if self.socketio:
                    try:
                        self.socketio.emit('new_message', chat_msg.to_dict(), room=f'chat_{room}')
                        self.socketio.emit('whale_alert', {
                            'masked_username': masked_name,
                            'symbol': symbol,
                            'pnl': round(pnl, 2),
                            'message': alert_message
                        }, room=f'chat_{room}')
                    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                            urllib3.exceptions.ProtocolError) as e:
                        # Client disconnected - expected behavior, log as warning only
                        logger.warning(f"Could not emit whale_alert: Client disconnected ({type(e).__name__})")
                    
                logger.info(f"🐋 Whale Alert: {masked_name} made +${pnl:.2f} on {symbol}")
                
        except Exception as e:
            logger.error(f"Whale alert error: {e}")

    async def execute_trade_ccxt_async(self, client_data: dict, signal: dict, master_entry_price: float,
                                        master_balance: float, master_trade_amount: float):
        """Execute trade for CCXT-based exchanges (OKX, Bybit, etc.) - ASYNC VERSION
        
        Instrumented with Prometheus metrics:
        - trade_execution_latency_seconds: Time from signal to order execution
        - failed_orders_total / successful_orders_total: Order outcome counters
        """
        import time as time_module
        trade_start_time = time_module.perf_counter()
        
        user_id = client_data['id']
        exchange = client_data['client']  # Async CCXT exchange instance
        exchange_name = client_data.get('exchange_name', 'Unknown')
        exchange_type = client_data.get('exchange_type', 'unknown')
        symbol = signal['symbol']
        action = signal['action']
        node_name = client_data.get('fullname', client_data['name'])
        is_master = str(user_id).startswith('master')
        
        logger.info(f"🔧 [{node_name}] CCXT execute_trade_ccxt started for {symbol} {action.upper()}")
        
        # Use admin global settings only (ignore per-user and signal overrides)
        risk_percent = float(self._get_global_setting('risk_perc', 3.0))
        leverage = int(float(self._get_global_setting('leverage', 20)))
        
        # SECURITY: Ensure leverage is within safe bounds (1 to MAX_LEVERAGE)
        leverage = max(1, min(int(leverage), self.MAX_LEVERAGE))
        logger.info(f"[{node_name}] {symbol}: Final leverage = {leverage}x (admin global)")
        
        max_pos = self.get_master_max_positions()
        
        if max_pos <= 0:
            max_pos = 1
        if max_pos > 50:
            max_pos = 50
        
        # Convert Binance symbol format to CCXT format (e.g., BTCUSDT -> BTC/USDT:USDT)
        ccxt_symbol = self.convert_symbol_to_ccxt(symbol, exchange_type)
        
        logger.info(f"[{node_name}] ({exchange_type.upper()}) Using max_positions={max_pos} for {symbol}")
        
        try:
            # === CLOSE POSITION ===
            if action == 'close':
                try:
                    positions = await exchange.fetch_positions([ccxt_symbol])
                    for pos in positions:
                        if pos['contracts'] and float(pos['contracts']) != 0:
                            side = 'sell' if pos['side'] == 'long' else 'buy'
                            await exchange.create_order(
                                ccxt_symbol, 'market', side,
                                abs(float(pos['contracts'])),
                                params={'reduceOnly': True}
                            )
                            pnl = float(pos.get('unrealizedPnl', 0))
                            side_text = pos['side'].upper()
                            self.record_closed_trade(user_id, node_name, symbol, side_text, pnl, 0)
                            self.log_event(user_id, symbol, f"({exchange_type.upper()}) CLOSED {side_text} | PnL: {pnl:.2f}$")
                except Exception as e:
                    logger.error(f"[{node_name}] ({exchange_type.upper()}) Close error: {e}")
                return
            
            # === CHECK MAX POSITIONS ===
            is_master_account = str(user_id).startswith('master')
            
            # Get or create user-specific async lock
            async with self._user_locks_async_lock:
                if user_id not in self.user_async_locks:
                    self.user_async_locks[user_id] = asyncio.Lock()
                user_lock = self.user_async_locks[user_id]
            
            async with user_lock:
                async with self._async_pending_lock:
                    if user_id not in self.pending_trades:
                        self.pending_trades[user_id] = set()
                
                # Check pending - for master accounts, check Redis first (source of truth)
                pending_key = f"{symbol}_master" if is_master_account else symbol
                
                # Skip pending check if skip_position_check is True (higher-level function already handled it)
                skip_position_check = client_data.get('skip_position_check', False)
                if not skip_position_check:
                    # For master accounts, check Redis state first (cross-process coordination)
                    if is_master_account:
                        redis_client = self._get_sync_redis()
                        if redis_client:
                            try:
                                redis_pending_key = f"{self.MASTER_PENDING_REDIS_KEY}:{symbol}"
                                if redis_client.exists(redis_pending_key):
                                    # Redis says it's pending - sync in-memory state
                                    async with self._async_pending_lock:
                                        if pending_key not in self.pending_trades[user_id]:
                                            self.pending_trades[user_id].add(pending_key)
                                    error_msg = f"({exchange_type.upper()}) Trade already in progress"
                                    self.log_event(user_id, symbol, error_msg, is_error=True)
                                    if self.telegram:
                                        self.telegram.notify_error(node_name, symbol, error_msg)
                                        chat_id = client_data.get('telegram_chat_id')
                                        if chat_id:
                                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                                    return
                                else:
                                    # Redis says it's not pending - clean up in-memory if stale
                                    async with self._async_pending_lock:
                                        if pending_key in self.pending_trades[user_id]:
                                            self.pending_trades[user_id].discard(pending_key)
                            except Exception as e:
                                logger.debug(f"Redis pending check failed: {e}")
                    
                    # Check in-memory pending state (for non-master or fallback)
                    async with self._async_pending_lock:
                        if pending_key in self.pending_trades[user_id]:
                            error_msg = f"({exchange_type.upper()}) Trade already in progress"
                            self.log_event(user_id, symbol, error_msg, is_error=True)
                            # Send Telegram notification about skipped trade
                            if self.telegram:
                                self.telegram.notify_error(node_name, symbol, error_msg)
                                chat_id = client_data.get('telegram_chat_id')
                                if chat_id:
                                    self.telegram.notify_user_error(chat_id, symbol, error_msg)
                            return
                
                try:
                    # Get open positions on THIS exchange (async)
                    await self.api_limiter.wait_and_proceed_async(f"pos_{user_id}")
                    positions = await exchange.fetch_positions()
                    open_cnt = 0
                    has_position_on_symbol = False
                    
                    for pos in positions:
                        if pos.get('contracts') and float(pos['contracts']) != 0:
                            open_cnt += 1
                            if pos.get('symbol') == ccxt_symbol:
                                has_position_on_symbol = True
                    
                    # Don't open if already have position on this symbol on THIS exchange
                    if has_position_on_symbol:
                        error_msg = f"({exchange_type.upper()}) Already have position on this symbol"
                        self.log_event(user_id, symbol, error_msg, is_error=True)
                        # Send Telegram notification about skipped trade
                        if self.telegram:
                            self.telegram.notify_error(node_name, symbol, error_msg)
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_error(chat_id, symbol, error_msg)
                        return
                    
                    global_open_count = client_data.get('global_open_count')
                    # Enforce max positions limit including pending trades
                    async with self._async_pending_lock:
                        pending_count = len(self.pending_trades[user_id])
                        base_open_count = global_open_count if global_open_count is not None else open_cnt
                        total_positions = base_open_count + pending_count
                        
                        if total_positions >= max_pos:
                            error_msg = f"({exchange_type.upper()}) Max positions reached ({base_open_count} open + {pending_count} pending >= {max_pos})"
                            self.log_event(user_id, symbol, error_msg, is_error=True)
                            # Send Telegram notification about skipped trade
                            if self.telegram:
                                self.telegram.notify_error(node_name, symbol, error_msg)
                                chat_id = client_data.get('telegram_chat_id')
                                if chat_id:
                                    self.telegram.notify_user_error(chat_id, symbol, error_msg)
                            return
                        
                        self.pending_trades[user_id].add(pending_key)
                
                except Exception as e:
                    error_msg = f"({exchange_type.upper()}) Position check failed: {str(e)[:100]}"
                    logger.error(f"[{node_name}] {error_msg}")
                    # Send Telegram notification about error
                    if self.telegram:
                        self.telegram.notify_error(node_name, symbol, error_msg)
                        chat_id = client_data.get('telegram_chat_id')
                        if chat_id:
                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                    return
                
                # === OPEN POSITION ===
                try:
                    # Set margin mode and leverage for OKX
                    try:
                        lev_int = int(float(leverage))  # Ensure it's an integer
                        if lev_int < 1:
                            lev_int = 1
                        
                        # For OKX, set margin mode first (cross or isolated)
                        if exchange_type == 'okx':
                            try:
                                await exchange.set_margin_mode('cross', ccxt_symbol)
                                logger.info(f"[{node_name}] Set margin mode to cross for {ccxt_symbol}")
                            except Exception as margin_err:
                                # Margin mode might already be set or not needed
                                logger.debug(f"[{node_name}] Margin mode note: {margin_err}")
                        
                        await exchange.set_leverage(lev_int, ccxt_symbol)
                        logger.info(f"[{node_name}] Set leverage to {lev_int}x for {ccxt_symbol}")
                    except Exception as lev_err:
                        logger.warning(f"[{node_name}] Could not set leverage: {lev_err}")
                    
                    # Get balance - handle different exchange response structures
                    await self.api_limiter.wait_and_proceed_async(f"bal_{user_id}")
                    balance = await exchange.fetch_balance()
                    available_balance = 0.0
                    
                    # Try multiple ways to get USDT balance (different exchanges structure this differently)
                    for asset in ['USDT', 'USD']:
                        # Method 1: Standard CCXT structure
                        if asset in balance.get('free', {}):
                            available_balance = float(balance['free'][asset] or 0)
                            if available_balance > 0:
                                break
                        # Method 2: Direct asset access
                        if asset in balance and isinstance(balance[asset], dict):
                            available_balance = float(balance[asset].get('free', 0) or 0)
                            if available_balance > 0:
                                break
                        # Method 3: Total balance fallback
                        if asset in balance.get('total', {}):
                            available_balance = float(balance['total'][asset] or 0)
                            if available_balance > 0:
                                break
                    
                    logger.info(f"[{node_name}] ({exchange_type.upper()}) Available balance: ${available_balance:.2f}")
                    
                    if available_balance <= 0:
                        error_msg = f"({exchange_type.upper()}) No funds available"
                        self.log_event(user_id, symbol, error_msg, is_error=True)
                        # Send Telegram notification
                        if self.telegram:
                            self.telegram.notify_error(node_name, symbol, error_msg)
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_error(chat_id, symbol, error_msg)
                        async with self._async_pending_lock:
                            self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master:
                            await self._release_master_pending_symbol_async(symbol)
                        return
                    
                    # Check minimum balance
                    min_balance_required = self.get_min_balance_required()
                    if min_balance_required > 0 and available_balance < min_balance_required:
                        error_msg = f"({exchange_type.upper()}) Balance ${available_balance:.2f} below min ${min_balance_required:.2f}"
                        self.log_event(user_id, symbol, error_msg, is_error=True)
                        # Send Telegram notification
                        if self.telegram:
                            self.telegram.notify_error(node_name, symbol, error_msg)
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_error(chat_id, symbol, error_msg)
                        async with self._async_pending_lock:
                            self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master:
                            await self._release_master_pending_symbol_async(symbol)
                        return
                    
                    # Calculate position size (notional value)
                    # Position size = balance × risk% × leverage × risk_multiplier
                    # margin (collateral) = balance × risk%
                    # notional (position size) = margin × leverage
                    if not is_master and master_balance > 0 and master_trade_amount > 0:
                        # For slaves: copy master's margin ratio
                        master_margin_ratio = master_trade_amount / master_balance
                        margin = available_balance * master_margin_ratio
                    else:
                        # For master: margin is % of balance
                        margin = available_balance * (risk_percent / 100.0)
                    
                    # Apply user's risk multiplier (1.0 = normal, 2.0 = 2x position size, etc.)
                    risk_multiplier = client_data.get('risk_multiplier', 1.0)
                    if risk_multiplier and risk_multiplier > 0:
                        margin = margin * risk_multiplier
                        logger.info(f"   📊 Risk Multiplier: {risk_multiplier}x applied (margin now: ${margin:.2f})")
                    
                    # Apply strategy allocation percentage (for multi-strategy support)
                    allocation_percent = client_data.get('allocation_percent', 100.0)
                    if allocation_percent and allocation_percent < 100.0:
                        margin = margin * (allocation_percent / 100.0)
                        logger.info(f"   📊 Strategy Allocation: {allocation_percent}% applied (margin now: ${margin:.2f})")
                    
                    # === AI SENTIMENT FILTER ===
                    # Adjust risk based on Fear & Greed Index:
                    # - Extreme Greed (>80) + LONG = reduce risk by 20% (prevent buying tops)
                    # - Extreme Fear (<20) + SHORT = reduce risk by 20% (prevent selling bottoms)
                    ai_adjustment_reason = None
                    if self.sentiment_manager and client_data.get('ai_sentiment_enabled', True):
                        try:
                            trade_side = 'LONG' if action == 'long' else 'SHORT'
                            # Calculate the original margin as the base
                            original_margin = margin
                            adjusted_risk, ai_adjustment_reason = await self.sentiment_manager.calculate_risk_adjustment(
                                trade_side, 100.0  # Use 100 as base to get percentage factor
                            )
                            
                            if adjusted_risk != 100.0 and ai_adjustment_reason:
                                # Apply the sentiment-based reduction
                                sentiment_factor = adjusted_risk / 100.0  # e.g., 80% = 0.8
                                margin = margin * sentiment_factor
                                logger.info(f"   🧠 AI SENTIMENT FILTER: {ai_adjustment_reason}")
                                logger.info(f"   🧠 Margin adjusted: ${original_margin:.2f} → ${margin:.2f} ({sentiment_factor*100:.0f}%)")
                        except Exception as sentiment_err:
                            logger.warning(f"   ⚠️ AI Sentiment check failed: {sentiment_err}")
                    
                    if leverage < 1:
                        leverage = 1
                    
                    # Get price (async)
                    await self.api_limiter.wait_and_proceed_async(f"tick_{user_id}")
                    ticker = await exchange.fetch_ticker(ccxt_symbol)
                    price = float(ticker['last'])
                    
                    # notional = margin × leverage (position size includes leverage)
                    notional = margin * leverage
                    min_notional = 5.0  # Default minimum
                    
                    logger.info(f"[{node_name}] {symbol}: POSITION CALCULATION:")
                    logger.info(f"   📊 Balance: ${available_balance:.2f}")
                    logger.info(f"   📊 Risk: {risk_percent}%  →  Margin: ${margin:.2f}")
                    logger.info(f"   📊 Leverage: {leverage}x  →  Notional: ${notional:.2f} (margin × leverage)")
                    logger.info(f"   📊 Price: ${price:.4f}  →  Qty: {notional/price:.6f}")
                    
                    if notional < min_notional:
                        error_msg = f"({exchange_type.upper()}) Position too small: ${notional:.2f} < ${min_notional:.2f} (balance: ${available_balance:.2f}, risk: {risk_percent}%, leverage: {leverage}x, margin: ${margin:.2f})"
                        logger.error(f"❌ [{node_name}] {error_msg}")
                        self.log_event(user_id, symbol, error_msg, is_error=True)
                        # Send Telegram notification
                        if self.telegram:
                            self.telegram.notify_error(node_name, symbol, error_msg)
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_error(chat_id, symbol, error_msg)
                        async with self._async_pending_lock:
                            self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master:
                            await self._release_master_pending_symbol_async(symbol)
                        return
                    
                    qty = notional / price
                    
                    # Round quantity based on exchange precision
                    try:
                        market = exchange.market(ccxt_symbol)
                        # CCXT precision can be either:
                        # - An integer (number of decimal places, e.g., 3)
                        # - A float (step size, e.g., 0.001)
                        precision_info = market.get('precision', {})
                        amount_precision = precision_info.get('amount', 8)
                        
                        if isinstance(amount_precision, float) and amount_precision < 1:
                            # It's a step size (e.g., 0.001), convert to decimal places
                            decimal_places = int(abs(math.log10(amount_precision))) if amount_precision > 0 else 8
                            qty = round(qty, decimal_places)
                        else:
                            # It's decimal places
                            qty = round(qty, int(amount_precision))
                        
                        logger.info(f"[{node_name}] {symbol}: qty={qty}, precision={amount_precision}")
                    except Exception as prec_err:
                        logger.warning(f"[{node_name}] Precision error: {prec_err}, using default 4 decimals")
                        qty = round(qty, 4)
                    
                    if qty <= 0:
                        error_msg = f"({exchange_type.upper()}) Quantity is 0 - trade skipped (balance: ${available_balance:.2f}, margin: ${margin:.2f}, leverage: {leverage}x, notional: ${notional:.2f}, price: ${price:.4f}, qty: {qty})"
                        logger.error(f"❌ [{node_name}] {error_msg}")
                        self.log_event(user_id, symbol, error_msg, is_error=True)
                        # Send Telegram notification
                        if self.telegram:
                            self.telegram.notify_error(node_name, symbol, error_msg)
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_error(chat_id, symbol, error_msg)
                        async with self._async_pending_lock:
                            self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master:
                            await self._release_master_pending_symbol_async(symbol)
                        return

                    # Place order (async)
                    side = 'buy' if action == 'long' else 'sell'
                    
                    logger.info(f"🚀 [{node_name}] PLACING ORDER: {action.upper()} {symbol}")
                    logger.info(f"   💰 Position Size: ${notional:.2f} (margin ${margin:.2f} × {leverage}x leverage)")
                    logger.info(f"   📦 Quantity: {qty} @ ${price:.4f}")
                    
                    # Execute order with retry on rate limit errors
                    order = None
                    max_retries = self.proxy_pool.max_retries
                    for retry_attempt in range(max_retries + 1):
                        try:
                            await self.order_limiter.wait_and_proceed_async(f"order_{user_id}")
                            order = await exchange.create_order(ccxt_symbol, 'market', side, qty)
                            break  # Success, exit retry loop
                        except Exception as order_err:
                            if self.is_rate_limit_error(order_err):
                                # Record rate limit hit metric
                                record_rate_limit(exchange=exchange_type, endpoint='create_order')
                                logger.warning(f"⚠️ [{node_name}] Rate limit on order, attempt {retry_attempt + 1}/{max_retries + 1}")
                                
                                if retry_attempt < max_retries:
                                    # Handle proxy rotation for rate limit
                                    can_retry = await self.handle_rate_limit_error_async(user_id, client_data, order_err)
                                    
                                    # Wait before retry (exponential backoff)
                                    wait_time = 2 ** retry_attempt
                                    logger.info(f"🔄 [{node_name}] Waiting {wait_time}s before retry...")
                                    await asyncio.sleep(wait_time)
                                else:
                                    # Max retries exhausted
                                    raise order_err
                            else:
                                # Not a rate limit error, raise immediately
                                raise order_err
                    
                    if not order:
                        raise Exception("Order placement failed after retries")
                    
                    # Record successful trade metrics
                    trade_duration = time_module.perf_counter() - trade_start_time
                    TRADE_LATENCY.labels(
                        exchange=exchange_type, symbol=symbol, action=action, status='success'
                    ).observe(trade_duration)
                    SUCCESSFUL_ORDERS.labels(
                        exchange=exchange_type, symbol=symbol, action=action
                    ).inc()
                    
                    logger.info(f"✅ {action.upper()} {symbol} for {node_name} ({exchange_type.upper()}) - ${notional:.2f} position (latency: {trade_duration:.3f}s)")
                    self.log_event(user_id, symbol, f"({exchange_type.upper()}) OPENED: {action.upper()} (${notional:.2f})")
                    
                    # CRITICAL: Verify position exists before tracking/notifying/clearing pending
                    await asyncio.sleep(0.1)  # Small delay to allow exchange to update
                    position_found = False
                    try:
                        positions = await exchange.fetch_positions([ccxt_symbol])
                        for pos in positions:
                            if pos.get('symbol') == ccxt_symbol and pos.get('contracts'):
                                contracts = float(pos['contracts'])
                                if contracts != 0:
                                    position_found = True
                                    break
                        
                        if not position_found:
                            logger.warning(f"⚠️ Position {symbol} NOT found on {exchange_type.upper()} after order placement - NOT tracking/notifying")
                            # Keep pending active so trade can retry - DON'T clear it
                            return  # Exit early - don't track/notify if position doesn't exist
                    except Exception as e:
                        logger.error(f"❌ Position verification failed for {symbol} on {exchange_type.upper()}: {e} - NOT tracking/notifying")
                        # Keep pending active - DON'T clear it on verification failure
                        return  # Exit early - don't track/notify if verification fails
                    
                    # Position verified successfully - now safe to track/clear pending
                    
                    # Track master position (for global position counting) - ONLY if verification succeeded
                    if is_master:
                        async with self._async_positions_lock:
                            self.master_positions[symbol] = {
                                'amount': qty if action == 'long' else -qty,
                                'entry': price,
                                'side': action.upper(),
                                'pnl': 0,
                                'leverage': leverage
                            }
                            logger.info(f"📍 Tracked master position ({exchange_type.upper()}): {symbol} {action.upper()}")
                    
                    # Set TP/SL if configured
                    tp_perc = float(signal.get('tp_perc', 0) or 0)
                    sl_perc = float(signal.get('sl_perc', 0) or 0)
                    
                    if tp_perc > 0:
                        try:
                            if action == 'long':
                                tp_price = price * (1 + tp_perc / 100)
                            else:
                                tp_price = price * (1 - tp_perc / 100)
                            
                            # Round TP price to appropriate precision
                            try:
                                market = exchange.market(ccxt_symbol)
                                price_prec = market.get('precision', {}).get('price', 4)
                                if isinstance(price_prec, float) and price_prec < 1:
                                    price_decimals = int(abs(math.log10(price_prec))) if price_prec > 0 else 4
                                else:
                                    price_decimals = int(price_prec)
                                tp_price = round(tp_price, price_decimals)
                            except:
                                tp_price = round(tp_price, 4)
                            
                            # Try with takeProfitPrice param first (OKX style)
                            try:
                                await self.order_limiter.wait_and_proceed_async(f"tp_{user_id}")
                                await exchange.create_order(
                                    ccxt_symbol, 'market', 'sell' if action == 'long' else 'buy',
                                    qty,
                                    params={'takeProfitPrice': tp_price, 'reduceOnly': True}
                                )
                            except Exception:
                                # Fallback to limit order
                                await exchange.create_order(
                                    ccxt_symbol, 'limit', 'sell' if action == 'long' else 'buy',
                                    qty, tp_price,
                                    params={'reduceOnly': True}
                                )
                            logger.info(f"📈 TP set at ${tp_price:.4f} for {symbol} [{node_name}] ({exchange_type.upper()})")
                        except Exception as e:
                            logger.warning(f"[{node_name}] ({exchange_type.upper()}) TP order failed: {e}")
                    
                    if sl_perc > 0:
                        try:
                            if action == 'long':
                                sl_price = price * (1 - sl_perc / 100)
                            else:
                                sl_price = price * (1 + sl_perc / 100)
                            
                            # Different exchanges have different stop order types
                            try:
                                # Try standard stop-market first (async)
                                await self.order_limiter.wait_and_proceed_async(f"sl_{user_id}")
                                await exchange.create_order(
                                    ccxt_symbol, 'market', 'sell' if action == 'long' else 'buy',
                                    qty,
                                    params={'stopLossPrice': sl_price, 'reduceOnly': True}
                                )
                            except Exception:
                                # Fallback for exchanges with different params
                                await exchange.create_order(
                                    ccxt_symbol, 'market', 'sell' if action == 'long' else 'buy',
                                    qty,
                                    params={'stopPrice': sl_price, 'reduceOnly': True, 'type': 'stop'}
                                )
                            logger.info(f"📉 SL set at ${sl_price:.4f} for {symbol} [{node_name}] ({exchange_type.upper()})")
                        except Exception as e:
                            logger.warning(f"[{node_name}] ({exchange_type.upper()}) SL order failed: {e}")
                    
                    # Clear pending (async) - ONLY after position is verified
                    async with self._async_pending_lock:
                        self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master:
                            pending_key = f"{symbol}_master"
                            if 'master' in self.pending_trades:
                                self.pending_trades['master'].discard(pending_key)
                                logger.debug(f"🔓 MASTER: Cleared pending {symbol} after position verified")
                    if is_master:
                        await self._release_master_pending_symbol_async(symbol)
                    
                    # Notify via Telegram - ONLY after position is verified
                    try:
                        if self.telegram:
                            # Always send notification to admin channel
                            self.telegram.notify_trade_opened(
                                f"{node_name} ({exchange_type.upper()})",
                                symbol,
                                'LONG' if action == 'long' else 'SHORT',
                                qty,
                                price
                            )
                            # Also notify user's personal Telegram if available
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_trade_opened(
                                    chat_id, symbol, 'LONG' if action == 'long' else 'SHORT', qty, price
                                )
                    except Exception as tg_err:
                        logger.warning(f"Telegram notification failed: {tg_err}")
                    
                except Exception as e:
                    # Record failed order metrics
                    trade_duration = time_module.perf_counter() - trade_start_time
                    error_type = type(e).__name__
                    TRADE_LATENCY.labels(
                        exchange=exchange_type, symbol=symbol, action=action, status='error'
                    ).observe(trade_duration)
                    FAILED_ORDERS.labels(
                        exchange=exchange_type, symbol=symbol, action=action, error_type=error_type
                    ).inc()
                    
                    error_msg = f"({exchange_type.upper()}) Order failed: {str(e)[:100]}"
                    logger.error(f"❌ [{node_name}] {error_msg}")
                    self.log_event(user_id, symbol, error_msg, is_error=True)
                    
                    # Send Telegram notification about order failure
                    if self.telegram:
                        self.telegram.notify_error(node_name, symbol, error_msg)
                        chat_id = client_data.get('telegram_chat_id')
                        if chat_id:
                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                    
                    async with self._async_pending_lock:
                        self.pending_trades.get(user_id, set()).discard(pending_key)
                    if is_master:
                        await self._release_master_pending_symbol_async(symbol)
                    
        except Exception as e:
            # Record general trade error metrics
            trade_duration = time_module.perf_counter() - trade_start_time
            error_type = type(e).__name__
            TRADE_LATENCY.labels(
                exchange=exchange_type, symbol=symbol, action=action, status='error'
            ).observe(trade_duration)
            FAILED_ORDERS.labels(
                exchange=exchange_type, symbol=symbol, action=action, error_type=error_type
            ).inc()
            
            error_msg = f"({exchange_type.upper()}) Trade error: {str(e)[:100]}"
            logger.error(f"❌ [{node_name}] {error_msg}")
            
            # Send Telegram notification about trade error
            if self.telegram:
                self.telegram.notify_error(node_name, symbol, error_msg)
                chat_id = client_data.get('telegram_chat_id')
                if chat_id:
                    self.telegram.notify_user_error(chat_id, symbol, error_msg)
            # Clear pending on unexpected error
            try:
                async with self._async_pending_lock:
                    self.pending_trades.get(user_id, set()).discard(pending_key)
                if is_master:
                    await self._release_master_pending_symbol_async(symbol)
            except Exception:
                pass
    
    async def _get_user_equity_async(self, client_data: dict) -> float:
        """
        Get user's current equity/balance from their exchange.
        
        Used by Risk Guardrails to check daily P&L.
        
        Args:
            client_data: Client data dict with exchange client
        
        Returns:
            Current equity in USDT, or 0 if failed
        """
        try:
            client = client_data.get('client')
            if not client:
                return 0.0
            
            is_ccxt = client_data.get('is_ccxt', False)
            is_async = client_data.get('is_async', False)
            
            if is_ccxt and is_async:
                # Async CCXT client
                balance = await client.fetch_balance()
                # Get total equity (USDT for futures)
                if 'USDT' in balance:
                    usdt_info = balance['USDT']
                    # Try to get total (including unrealized PnL)
                    equity = usdt_info.get('total', 0) or usdt_info.get('free', 0) + usdt_info.get('used', 0)
                    return float(equity) if equity else 0.0
                elif 'total' in balance and 'USDT' in balance['total']:
                    return float(balance['total']['USDT'] or 0)
                return 0.0
                
            elif is_ccxt:
                # Sync CCXT client - run in executor
                loop = asyncio.get_event_loop()
                balance = await loop.run_in_executor(None, client.fetch_balance)
                if 'USDT' in balance:
                    usdt_info = balance['USDT']
                    equity = usdt_info.get('total', 0) or usdt_info.get('free', 0) + usdt_info.get('used', 0)
                    return float(equity) if equity else 0.0
                return 0.0
                
            else:
                # Binance client (sync) - run in executor
                loop = asyncio.get_event_loop()
                def get_binance_equity():
                    balances = client.futures_account_balance()
                    for b in balances:
                        if b['asset'] == 'USDT':
                            # balance includes unrealized PnL
                            return float(b.get('balance', 0))
                    return 0.0
                return await loop.run_in_executor(None, get_binance_equity)
                
        except Exception as e:
            logger.error(f"Failed to get equity for user {client_data.get('id')}: {e}")
            return 0.0
    
    def convert_symbol_to_ccxt(self, binance_symbol: str, exchange_type: str) -> str:
        """Convert Binance symbol format to CCXT format for perpetual futures"""
        # Remove USDT suffix and create proper format
        base = binance_symbol.replace('USDT', '').replace('PERP', '')
        
        # Different exchanges use different symbol formats
        if exchange_type in ['okx']:
            return f"{base}/USDT:USDT"  # OKX format
        elif exchange_type in ['bybit']:
            return f"{base}/USDT:USDT"  # Bybit uses same format
        elif exchange_type in ['bitget', 'kucoin']:
            return f"{base}/USDT:USDT"
        else:
            # Default CCXT perpetual format
            return f"{base}/USDT:USDT"

    async def execute_trade_async(self, client_data: dict, signal: dict, master_entry_price: float, 
                                   master_balance: float, master_trade_amount: float):
        """Execute trade for a single account - ASYNC VERSION routes to appropriate handler"""
        user_id = client_data['id']
        exchange_name = client_data.get('exchange_name', 'Unknown')
        node_name = client_data.get('fullname', str(user_id))
        symbol = signal.get('symbol', 'UNKNOWN')
        
        if client_data.get('is_paused', False):
            logger.warning(f"⏸️ [{node_name}] User is paused - trade skipped for {symbol}")
            return
        
        # SUBSCRIPTION CHECK: Skip trade if subscription expired
        subscription_expires = client_data.get('subscription_expires_at')
        if subscription_expires:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            # Handle both timezone-aware and naive datetimes
            if subscription_expires.tzinfo is None:
                subscription_expires = subscription_expires.replace(tzinfo=timezone.utc)
            if now >= subscription_expires:
                error_msg = f"Subscription expired - trade skipped (expired: {subscription_expires}, now: {now})"
                logger.warning(f"⏰ [{node_name}] {error_msg}")
                # Send Telegram notification
                if self.telegram:
                    self.telegram.notify_error(node_name, symbol, error_msg)
                    chat_id = client_data.get('telegram_chat_id')
                    if chat_id:
                        self.telegram.notify_user_error(chat_id, symbol, error_msg)
                return
        
        # RISK GUARDRAILS CHECK: Only for opening positions, not closing
        action = signal.get('action', '').lower()
        if action != 'close' and self.risk_guardrails and client_data.get('risk_guardrails_enabled', False):
            try:
                # Get user's current balance from exchange
                current_equity = await self._get_user_equity_async(client_data)
                
                if current_equity and current_equity > 0:
                    drawdown_limit = client_data.get('daily_drawdown_limit_perc', 10.0)
                    profit_target = client_data.get('daily_profit_target_perc', 20.0)
                    
                    should_pause, reason, stats = await self.risk_guardrails.check_risk_guardrails(
                        user_id=str(user_id),
                        current_equity=current_equity,
                        drawdown_limit_perc=drawdown_limit,
                        profit_target_perc=profit_target
                    )
                    
                    if should_pause:
                        pnl_pct = stats.get('pnl_pct', 0)
                        error_msg = f"Risk guardrails: {reason} (P&L: {pnl_pct:.2f}%)"
                        logger.warning(f"🛡️ [{node_name}] {error_msg}")
                        
                        # Send Telegram notification
                        if self.telegram:
                            self.telegram.notify_error(node_name, symbol, error_msg)
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_error(chat_id, symbol, error_msg)
                        
                        # Pause user and optionally panic close (only for drawdown)
                        if isinstance(user_id, int):
                            panic_close = (reason == 'drawdown_limit')
                            await self.risk_guardrails.pause_user_with_guardrails(
                                user_id, reason, panic_close=panic_close
                            )
                            
                            # Update client_data to prevent further trades in this batch
                            client_data['is_paused'] = True
                        
                        return  # Skip this trade
                    else:
                        logger.debug(f"🛡️ Risk check OK for {user_id}: P&L {stats.get('pnl_pct', 0):.2f}%")
                        
            except Exception as e:
                logger.error(f"Risk guardrails check failed for {user_id}: {e}")
                # Continue with trade on check failure (fail-open for UX)
        
        logger.info(f"🔄 execute_trade_async called for {client_data.get('fullname', user_id)} ({exchange_name})")
        
        # Route to appropriate handler based on client type
        if client_data.get('is_ccxt') and client_data.get('is_async'):
            # Async CCXT exchanges (OKX, Bybit, etc.)
            logger.info(f"   ➡️ Routing to async CCXT handler for {exchange_name}")
            return await self.execute_trade_ccxt_async(client_data, signal, master_entry_price, 
                                                       master_balance, master_trade_amount)
        elif client_data.get('is_ccxt'):
            # Legacy sync CCXT - run in executor
            logger.info(f"   ➡️ Routing to sync CCXT handler for {exchange_name}")
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                self._execute_trade_binance_sync, 
                client_data, signal, master_entry_price, master_balance, master_trade_amount
            )
        else:
            # Binance (python-binance) clients - run sync method in executor to avoid blocking
            logger.info(f"   ➡️ Routing to Binance sync handler for {exchange_name}")
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._execute_trade_binance_sync,
                client_data, signal, master_entry_price, master_balance, master_trade_amount
            )
    
    def execute_trade(self, client_data: dict, signal: dict, master_entry_price: float, 
                      master_balance: float, master_trade_amount: float):
        """Execute trade for a single account - routes to appropriate handler (SYNC WRAPPER)"""
        user_id = client_data['id']
        exchange_name = client_data.get('exchange_name', 'Unknown')
        node_name = client_data.get('fullname', str(user_id))
        symbol = signal.get('symbol', 'UNKNOWN')
        
        if client_data.get('is_paused', False):
            logger.warning(f"⏸️ [{node_name}] User is paused - trade skipped for {symbol}")
            return
        
        # SUBSCRIPTION CHECK: Skip trade if subscription expired
        subscription_expires = client_data.get('subscription_expires_at')
        if subscription_expires:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            # Handle both timezone-aware and naive datetimes
            if subscription_expires.tzinfo is None:
                subscription_expires = subscription_expires.replace(tzinfo=timezone.utc)
            if now >= subscription_expires:
                error_msg = f"Subscription expired - trade skipped (expired: {subscription_expires}, now: {now})"
                logger.warning(f"⏰ [{node_name}] {error_msg}")
                # Send Telegram notification
                if self.telegram:
                    self.telegram.notify_error(node_name, symbol, error_msg)
                    chat_id = client_data.get('telegram_chat_id')
                    if chat_id:
                        self.telegram.notify_user_error(chat_id, symbol, error_msg)
                return
        
        logger.info(f"🔄 execute_trade called for {node_name} ({exchange_name})")
        
        # For async clients, run in event loop
        if client_data.get('is_async'):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule as a task if loop is already running
                    asyncio.create_task(self.execute_trade_async(
                        client_data, signal, master_entry_price, master_balance, master_trade_amount
                    ))
                else:
                    loop.run_until_complete(self.execute_trade_async(
                        client_data, signal, master_entry_price, master_balance, master_trade_amount
                    ))
            except RuntimeError:
                # No event loop running, create a new one
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.execute_trade_async(
                    client_data, signal, master_entry_price, master_balance, master_trade_amount
                ))
            return
        
        # Continue with Binance sync execution for non-async clients
        self._execute_trade_binance_sync(client_data, signal, master_entry_price, master_balance, master_trade_amount)
    
    def _execute_trade_binance_sync(self, client_data: dict, signal: dict, master_entry_price: float, 
                                     master_balance: float, master_trade_amount: float):
        """Execute trade for Binance (sync) - internal implementation"""
        user_id = client_data['id']
        exchange_name = client_data.get('exchange_name', 'Unknown')
        
        # Continue with Binance execution below...
        client = client_data['client']
        symbol = signal['symbol'] 
        action = signal['action']
        node_name = client_data.get('fullname', client_data['name'])
        
        # Use admin global settings only (ignore per-user and signal overrides)
        risk_percent = float(self._get_global_setting('risk_perc', 3.0))
        leverage = int(float(self._get_global_setting('leverage', 20)))
        
        # SECURITY: Ensure leverage is within safe bounds (1 to MAX_LEVERAGE)
        leverage = max(1, min(int(leverage), self.MAX_LEVERAGE))
        logger.info(f"[{node_name}] {symbol}: Final leverage = {leverage}x (admin global)")
        
        max_pos = self.get_master_max_positions()
        
        # Validate max_pos is positive and reasonable
        if max_pos <= 0:
            max_pos = 1  # Minimum of 1 position allowed
        if max_pos > 50:
            max_pos = 50  # Maximum cap
        
        # Log max_pos for debugging
        logger.info(f"[{user_id}] Using max_positions={max_pos} for {symbol}")

        try:
            # === CLOSE POSITION ===
            if action == 'close':
                positions = client.futures_position_information(symbol=symbol)
                
                for p in positions:
                    amt = float(p['positionAmt'])
                    if amt != 0:
                        pnl = float(p['unRealizedProfit'])
                        entry_price = float(p['entryPrice'])
                        side_text = 'LONG' if amt > 0 else 'SHORT'
                        margin = (abs(amt) * entry_price) / float(p.get('leverage', 1))
                        roi = (pnl / margin) * 100 if margin > 0 else 0
                        
                        prec = self.get_precision(client, symbol)
                        qty_str = f"{abs(amt):.{prec['qty_prec']}f}"
                        
                        # Cancel all orders
                        try:
                            client.futures_cancel_all_open_orders(symbol=symbol)
                        except Exception:
                            pass

                        self.order_limiter.wait_and_proceed(user_id)
                        client.futures_create_order(
                            symbol=symbol,
                            side='SELL' if amt > 0 else 'BUY',
                            type='MARKET',
                            quantity=qty_str,
                            reduceOnly=True
                        )
                        
                        self.record_closed_trade(user_id, node_name, symbol, side_text, pnl, roi)
                        self.log_event(user_id, symbol, f"CLOSED {side_text} | PnL: {pnl:.2f}$")
                
                self.push_update(user_id, client, is_master=(user_id == 'master'))
                return

            # === CHECK MAX POSITIONS & EXISTING POSITION ===
            is_master_account = str(user_id).startswith('master')
            pending_key = f"{symbol}_master" if is_master_account else symbol
            
            # CRITICAL: Use per-user lock to serialize position checks for this specific user
            # This prevents race conditions where multiple signals for the same user check simultaneously
            # Get or create user-specific lock
            with self.user_locks_lock:
                if user_id not in self.user_locks:
                    self.user_locks[user_id] = threading.Lock()
                user_lock = self.user_locks[user_id]
            
            # Hold user lock for the ENTIRE check-and-order-placement operation
            # This ensures only one signal per user can check and place orders at a time
            with user_lock:
                # Initialize pending trades set if needed
                with self.pending_lock:
                    if user_id not in self.pending_trades:
                        self.pending_trades[user_id] = set()
                
                # Skip pending check if skip_position_check is True (higher-level function already handled it)
                skip_position_check = client_data.get('skip_position_check', False)
                if not skip_position_check:
                    # Check if already pending for this symbol FIRST (before any API calls)
                    # For master accounts, check Redis first (source of truth for cross-process coordination)
                    if is_master_account:
                        redis_client = self._get_sync_redis()
                        if redis_client:
                            try:
                                redis_pending_key = f"{self.MASTER_PENDING_REDIS_KEY}:{symbol}"
                                if redis_client.exists(redis_pending_key):
                                    # Redis says it's pending - sync in-memory state
                                    with self.pending_lock:
                                        if pending_key not in self.pending_trades[user_id]:
                                            self.pending_trades[user_id].add(pending_key)
                                    error_msg = f"Trade already in progress for {symbol}"
                                    self.log_event(user_id, symbol, error_msg, is_error=True)
                                    if self.telegram:
                                        self.telegram.notify_error(node_name, symbol, error_msg)
                                        chat_id = client_data.get('telegram_chat_id')
                                        if chat_id:
                                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                                    return
                                else:
                                    # Redis says it's not pending - clean up in-memory if stale
                                    with self.pending_lock:
                                        if pending_key in self.pending_trades[user_id]:
                                            self.pending_trades[user_id].discard(pending_key)
                            except Exception as e:
                                logger.debug(f"Redis pending check failed: {e}")
                    
                    # Check in-memory pending state (for non-master or fallback)
                    with self.pending_lock:
                        if pending_key in self.pending_trades[user_id]:
                            error_msg = f"Trade already in progress for {symbol}"
                            self.log_event(user_id, symbol, error_msg, is_error=True)
                            # Send Telegram notification
                            if self.telegram:
                                self.telegram.notify_error(node_name, symbol, error_msg)
                                chat_id = client_data.get('telegram_chat_id')
                                if chat_id:
                                    self.telegram.notify_user_error(chat_id, symbol, error_msg)
                            return
                
                # For master accounts with global check already done, only check if we have position on THIS exchange
                # For slave accounts, do full per-account position check
                try:
                    # Get current open positions on THIS exchange
                    positions = client.futures_position_information()
                    open_cnt = 0
                    has_position_on_symbol = False
                    
                    for p in positions:
                        amt = float(p['positionAmt'])
                        if amt != 0:
                            open_cnt += 1
                            if p['symbol'] == symbol:
                                has_position_on_symbol = True
                    
                    # Don't open if already have position on this symbol on THIS exchange
                    if has_position_on_symbol:
                        error_msg = f"Already have position on {symbol}"
                        self.log_event(user_id, symbol, error_msg, is_error=True)
                        # Send Telegram notification
                        if self.telegram:
                            self.telegram.notify_error(node_name, symbol, error_msg)
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_error(chat_id, symbol, error_msg)
                        return
                    
                    global_open_count = client_data.get('global_open_count')
                    # Enforce max positions limit including pending trades
                    with self.pending_lock:
                        pending_count = len(self.pending_trades[user_id])
                        base_open_count = global_open_count if global_open_count is not None else open_cnt
                        total_positions = base_open_count + pending_count
                        
                        # Log the check for debugging
                        logger.debug(f"[{user_id}] Position check for {symbol}: open={base_open_count}, pending={pending_count}, total={total_positions}, max={max_pos}")
                        
                        # Enforce max positions strictly: if max_pos is 1, only allow 1 total position
                        # Use strict comparison: if we're at or above max, reject
                        if total_positions >= max_pos:
                            error_msg = f"Max positions reached ({base_open_count} open + {pending_count} pending >= {max_pos})"
                            self.log_event(user_id, symbol, error_msg, is_error=True)
                            # Send Telegram notification
                            if self.telegram:
                                self.telegram.notify_error(node_name, symbol, error_msg)
                                chat_id = client_data.get('telegram_chat_id')
                                if chat_id:
                                    self.telegram.notify_user_error(chat_id, symbol, error_msg)
                            return
                        
                        # All checks passed - mark as pending IMMEDIATELY to prevent concurrent signals
                        # This MUST happen atomically with the check above, before releasing the lock
                        self.pending_trades[user_id].add(pending_key)
                        
                        # Double-check: After marking as pending, verify we didn't exceed limit
                        # This is a safety net in case of any race condition
                        final_pending_count = len(self.pending_trades[user_id])
                        final_total = base_open_count + final_pending_count
                        if final_total > max_pos:
                            # We exceeded the limit - remove from pending and reject
                            self.pending_trades[user_id].discard(pending_key)
                            if is_master_account:
                                self._release_master_pending_symbol_sync(symbol)
                            error_msg = f"Max positions exceeded ({base_open_count} open + {final_pending_count} pending > {max_pos})"
                            self.log_event(user_id, symbol, error_msg, is_error=True)
                            # Send Telegram notification
                            if self.telegram:
                                self.telegram.notify_error(node_name, symbol, error_msg)
                                chat_id = client_data.get('telegram_chat_id')
                                if chat_id:
                                    self.telegram.notify_user_error(chat_id, symbol, error_msg)
                            return
                        
                except Exception as e:
                    error_msg = f"Position check failed: {str(e)[:100]}"
                    logger.warning(f"[{node_name}] {error_msg}")
                    self.log_event(user_id, symbol, error_msg, is_error=True)
                    # Send Telegram notification
                    if self.telegram:
                        self.telegram.notify_error(node_name, symbol, error_msg)
                        chat_id = client_data.get('telegram_chat_id')
                        if chat_id:
                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                    return

                # === OPEN POSITION ===
                side = 'BUY' if action == 'long' else 'SELL'
                
                # Check slippage for slaves
                if user_id != 'master':
                    if not self.check_slippage(client, symbol, side, master_entry_price):
                        error_msg = "Slippage too high, trade skipped"
                        self.log_event(user_id, symbol, error_msg, is_error=True)
                        # Send Telegram notification
                        if self.telegram:
                            self.telegram.notify_error(node_name, symbol, error_msg)
                            chat_id = client_data.get('telegram_chat_id')
                            if chat_id:
                                self.telegram.notify_user_error(chat_id, symbol, error_msg)
                        # Clear pending trade
                        with self.pending_lock:
                            self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master_account:
                            self._release_master_pending_symbol_sync(symbol)
                        return

                # Set leverage
                try:
                    self.api_limiter.wait_and_proceed(f"lev_{user_id}")
                    client.futures_change_leverage(symbol=symbol, leverage=int(leverage))
                except Exception:
                    pass

                # Get balance
                balances = client.futures_account_balance()
                available_balance = 0.0
                
                for b in balances:
                    if b['asset'] == 'USDT':
                        available_balance = float(b.get('availableBalance', b.get('withdrawAvailable', b['balance'])))
                        break
                
                if available_balance <= 0:
                    error_msg = f"No funds available ({available_balance:.2f}$)"
                    self.log_event(user_id, symbol, error_msg, is_error=True)
                    # Send Telegram notification
                    if self.telegram:
                        self.telegram.notify_error(node_name, symbol, error_msg)
                        chat_id = client_data.get('telegram_chat_id')
                        if chat_id:
                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                    # Clear pending trade
                    with self.pending_lock:
                        self.pending_trades.get(user_id, set()).discard(pending_key)
                    if is_master_account:
                        self._release_master_pending_symbol_sync(symbol)
                    return
                
                # Check minimum balance requirement (set by admin)
                min_balance_required = self.get_min_balance_required()
                if min_balance_required > 0 and available_balance < min_balance_required:
                    error_msg = f"Balance ${available_balance:.2f} is below minimum ${min_balance_required:.2f}"
                    self.log_event(user_id, symbol, error_msg, is_error=True)
                    # Send Telegram notification
                    if self.telegram:
                        self.telegram.notify_error(node_name, symbol, error_msg)
                        chat_id = client_data.get('telegram_chat_id')
                        if chat_id:
                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                    # Clear pending trade
                    with self.pending_lock:
                        self.pending_trades.get(user_id, set()).discard(pending_key)
                    if is_master_account:
                        self._release_master_pending_symbol_sync(symbol)
                    return

                # Calculate position size (notional value)
                # Position size = balance × risk% × leverage × risk_multiplier
                # margin (collateral) = balance × risk%
                # notional (position size) = margin × leverage
                if user_id != 'master' and master_balance > 0 and master_trade_amount > 0:
                    # For slaves: copy master's margin ratio
                    master_margin_ratio = master_trade_amount / master_balance
                    margin = available_balance * master_margin_ratio
                else:
                    # For master: margin is % of balance
                    margin = available_balance * (risk_percent / 100.0)

                # Apply user's risk multiplier (1.0 = normal, 2.0 = 2x position size, etc.)
                risk_multiplier = client_data.get('risk_multiplier', 1.0)
                if risk_multiplier and risk_multiplier > 0:
                    margin = margin * risk_multiplier
                    logger.info(f"   📊 Risk Multiplier: {risk_multiplier}x applied (margin now: ${margin:.2f})")
                
                # Apply strategy allocation percentage (for multi-strategy support)
                allocation_percent = client_data.get('allocation_percent', 100.0)
                if allocation_percent and allocation_percent < 100.0:
                    margin = margin * (allocation_percent / 100.0)
                    logger.info(f"   📊 Strategy Allocation: {allocation_percent}% applied (margin now: ${margin:.2f})")
                
                # === AI SENTIMENT FILTER (SYNC) ===
                # NOTE: Sentiment adjustment is skipped in sync context to avoid event loop conflicts
                # Redis clients are bound to the async worker loop, not the sync executor thread
                # This is a non-critical feature - trades proceed normally without sentiment adjustment in sync context
                if self.sentiment_manager and client_data.get('ai_sentiment_enabled', True):
                    # Skip sentiment adjustment in sync Binance handler to avoid event loop conflicts
                    # Sentiment adjustment works fine in async CCXT handlers
                    logger.debug("   ℹ️ AI Sentiment adjustment skipped in sync context (event loop conflict prevention)")

                # Ensure leverage is valid (must be >= 1)
                if leverage < 1:
                    leverage = 1
                
                # Get precision and price
                prec = self.get_precision(client, symbol)
                
                self.api_limiter.wait_and_proceed(f"price_{user_id}")
                ticker = client.futures_symbol_ticker(symbol=symbol)
                price = float(ticker['price'])

                # notional = margin × leverage (position size includes leverage)
                notional = margin * leverage
                
                logger.info(f"[{node_name}] {symbol}: POSITION CALCULATION:")
                logger.info(f"   📊 Balance: ${available_balance:.2f}")
                logger.info(f"   📊 Risk: {risk_percent}%  →  Margin: ${margin:.2f}")
                logger.info(f"   📊 Leverage: {leverage}x  →  Notional: ${notional:.2f} (margin × leverage)")
                logger.info(f"   📊 Price: ${price:.4f}  →  Qty: {notional/price:.6f}")
                
                # Check Binance minimum notional requirement
                min_notional = prec['minNotional'] if not Config.IS_TESTNET else 0.1
                
                # If calculated position is too small, reject the trade
                # DO NOT use minimum notional as fallback - this would ignore risk settings
                if notional < min_notional:
                    error_msg = f"Position too small: ${notional:.2f} < ${min_notional:.2f} (balance: ${available_balance:.2f}, risk: {risk_percent}%, margin: ${margin:.2f}, leverage: {leverage}x)"
                    logger.error(f"❌ [{node_name}] {error_msg}")
                    self.log_event(user_id, symbol, error_msg, is_error=True)
                    # Send Telegram notification
                    if self.telegram:
                        self.telegram.notify_error(node_name, symbol, error_msg)
                        chat_id = client_data.get('telegram_chat_id')
                        if chat_id:
                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                    # Clear pending trade
                    with self.pending_lock:
                        self.pending_trades.get(user_id, set()).discard(pending_key)
                    if is_master_account:
                        self._release_master_pending_symbol_sync(symbol)
                    return

                # Calculate quantity from notional value
                qty = self.round_step(notional / price, prec['stepSize'])
                qty = max(qty, prec['minQty'])
                
                # CRITICAL: Check if rounded quantity still meets minimum notional
                # If rounding DOWN caused notional to fall below minimum, round UP instead
                actual_notional = qty * price
                if actual_notional < min_notional and prec['stepSize'] > 0:
                    # Round up to next step to meet minimum notional
                    qty = math.ceil((notional / price) / prec['stepSize']) * prec['stepSize']
                    qty = round(qty, prec['qty_prec'])
                    actual_notional = qty * price
                    logger.info(f"[{node_name}] {symbol}: Rounded qty UP to {qty} to meet min notional (${actual_notional:.2f} >= ${min_notional:.2f})")
                
                qty_str = f"{qty:.{prec['qty_prec']}f}"
                
                if qty <= 0:
                    error_msg = f"Quantity is 0 - trade skipped (balance: ${available_balance:.2f}, margin: ${margin:.2f}, leverage: {leverage}x, notional: ${notional:.2f}, price: ${price:.4f}, qty: {qty})"
                    logger.error(f"❌ [{node_name}] {error_msg}")
                    self.log_event(user_id, symbol, error_msg, is_error=True)
                    # Send Telegram notification
                    if self.telegram:
                        self.telegram.notify_error(node_name, symbol, error_msg)
                        chat_id = client_data.get('telegram_chat_id')
                        if chat_id:
                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                    # Clear pending trade
                    with self.pending_lock:
                        self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master_account:
                            self._release_master_pending_symbol_sync(symbol)
                    return

                # === PLACE ORDER ===
                try:
                    logger.info(f"🚀 [{node_name}] PLACING ORDER: {action.upper()} {symbol}")
                    logger.info(f"   💰 Position Size: ${notional:.2f} (margin ${margin:.2f} × {leverage}x leverage)")
                    logger.info(f"   📦 Quantity: {qty_str} @ ${price:.4f}")
                    
                    self.order_limiter.wait_and_proceed(user_id)
                    client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='MARKET',
                        quantity=qty_str
                    )
                    
                    # Order placed successfully
                    logger.info(f"✅ {action.upper()} {symbol} for {node_name} - ${notional:.2f} position")
                    self.log_event(user_id, symbol, f"OPENED: {action.upper()} (${notional:.2f})")
                    
                    # === FETCH ACTUAL ENTRY PRICE FROM POSITION ===
                    # Wait briefly for Binance to register the position
                    time.sleep(0.3)
                    
                    # Get actual entry price from position (more accurate for TP/SL)
                    entry_price = price  # Fallback to ticker price
                    try:
                        pos_info = client.futures_position_information(symbol=symbol)
                        for pos in pos_info:
                            if pos['symbol'] == symbol:
                                pos_amt = float(pos['positionAmt'])
                                if pos_amt != 0:
                                    entry_price = float(pos['entryPrice'])
                                    logger.info(f"📍 [{node_name}] {symbol}: Actual entry price=${entry_price:.4f}")
                                    break
                    except Exception as e:
                        logger.warning(f"[{node_name}] Could not fetch entry price for {symbol}, using ticker: {e}")
                    
                    # === PLACE TP/SL ORDERS IMMEDIATELY AFTER MAIN ORDER ===
                    # This is critical - do this BEFORE any other operations that might fail
                    tp_placed = False
                    sl_placed = False
                    
                    # Get TP/SL percentages from signal with proper defaults
                    tp_perc = float(signal.get('tp_perc', 0) or 0)
                    sl_perc = float(signal.get('sl_perc', 0) or 0)
                    
                    # Debug logging for TP/SL values
                    logger.info(f"📊 [{node_name}] {symbol}: TP%={tp_perc}, SL%={sl_perc}, Entry=${entry_price:.4f}")
                    
                    # Place TP order (TAKE_PROFIT_MARKET for guaranteed execution)
                    if tp_perc > 0 and entry_price > 0:
                        try:
                            tp_mult = 1 + tp_perc/100 if action == 'long' else 1 - tp_perc/100
                            tp_price_raw = entry_price * tp_mult
                            tp_price = self.round_step(tp_price_raw, prec['tickSize'])
                            
                            # If rounding to tick size resulted in 0, use price precision instead
                            if tp_price <= 0 and tp_price_raw > 0:
                                tp_price = round(tp_price_raw, prec['price_prec'])
                                logger.info(f"[{node_name}] {symbol}: Using price_prec rounding for TP (tickSize too large)")
                            
                            logger.info(f"[{node_name}] {symbol} TP calculation: entry=${entry_price:.6f}, mult={tp_mult}, raw=${tp_price_raw:.6f}, tp_price=${tp_price:.6f}")
                            
                            if tp_price > 0:
                                # Format price with appropriate precision (use max of price_prec and 6 for very low prices)
                                tp_price_prec = max(prec['price_prec'], 6) if tp_price < 0.01 else prec['price_prec']
                                tp_price_str = f"{tp_price:.{tp_price_prec}f}"
                                
                                # Try up to 3 times to place TP order
                                for attempt in range(3):
                                    try:
                                        self.order_limiter.wait_and_proceed(f"tp_{user_id}")
                                        client.futures_create_order(
                                            symbol=symbol,
                                            side='SELL' if action == 'long' else 'BUY',
                                            type='TAKE_PROFIT_MARKET',
                                            stopPrice=tp_price_str,
                                            closePosition=True,
                                            workingType='MARK_PRICE'
                                        )
                                        logger.info(f"📈 TP set at ${tp_price:.6f} ({tp_perc}%) for {symbol} [{node_name}]")
                                        self.log_event(user_id, symbol, f"TP: ${tp_price:.6f}")
                                        tp_placed = True
                                        break
                                    except BinanceAPIException as e:
                                        if attempt < 2:
                                            logger.warning(f"[{node_name}] TP order attempt {attempt+1} failed for {symbol}: {e.message}, retrying...")
                                            time.sleep(0.2)
                                        else:
                                            logger.error(f"[{node_name}] TP order FAILED for {symbol} after 3 attempts: {e.message}")
                                            self.log_event(user_id, symbol, f"TP FAILED: {e.message}", is_error=True)
                                    except Exception as e:
                                        logger.error(f"[{node_name}] TP order error for {symbol}: {e}")
                                        break
                            else:
                                logger.warning(f"[{node_name}] {symbol}: TP price invalid (${tp_price})")
                        except Exception as e:
                            logger.error(f"[{node_name}] {symbol}: TP calculation error: {e}")
                    else:
                        if tp_perc <= 0:
                            logger.debug(f"[{node_name}] {symbol}: TP skipped (tp_perc={tp_perc})")

                    # Place SL order (STOP_MARKET for guaranteed execution)
                    if sl_perc > 0 and entry_price > 0:
                        try:
                            sl_mult = 1 - sl_perc/100 if action == 'long' else 1 + sl_perc/100
                            sl_price_raw = entry_price * sl_mult
                            sl_price = self.round_step(sl_price_raw, prec['tickSize'])
                            
                            # If rounding to tick size resulted in 0, use price precision instead
                            if sl_price <= 0 and sl_price_raw > 0:
                                sl_price = round(sl_price_raw, prec['price_prec'])
                                logger.info(f"[{node_name}] {symbol}: Using price_prec rounding for SL (tickSize too large)")
                            
                            logger.info(f"[{node_name}] {symbol} SL calculation: entry=${entry_price:.6f}, mult={sl_mult}, raw=${sl_price_raw:.6f}, sl_price=${sl_price:.6f}")
                            
                            if sl_price > 0:
                                # Format price with appropriate precision (use max of price_prec and 6 for very low prices)
                                sl_price_prec = max(prec['price_prec'], 6) if sl_price < 0.01 else prec['price_prec']
                                sl_price_str = f"{sl_price:.{sl_price_prec}f}"
                                
                                # Try up to 3 times to place SL order
                                for attempt in range(3):
                                    try:
                                        self.order_limiter.wait_and_proceed(f"sl_{user_id}")
                                        client.futures_create_order(
                                            symbol=symbol,
                                            side='SELL' if action == 'long' else 'BUY',
                                            type='STOP_MARKET',
                                            stopPrice=sl_price_str,
                                            closePosition=True,
                                            workingType='MARK_PRICE'
                                        )
                                        logger.info(f"📉 SL set at ${sl_price:.6f} ({sl_perc}%) for {symbol} [{node_name}]")
                                        self.log_event(user_id, symbol, f"SL: ${sl_price:.6f}")
                                        sl_placed = True
                                        break
                                    except BinanceAPIException as e:
                                        if attempt < 2:
                                            logger.warning(f"[{node_name}] SL order attempt {attempt+1} failed for {symbol}: {e.message}, retrying...")
                                            time.sleep(0.2)
                                        else:
                                            logger.error(f"[{node_name}] SL order FAILED for {symbol} after 3 attempts: {e.message}")
                                            self.log_event(user_id, symbol, f"SL FAILED: {e.message}", is_error=True)
                                    except Exception as e:
                                        logger.error(f"[{node_name}] SL order error for {symbol}: {e}")
                                        break
                            else:
                                logger.warning(f"[{node_name}] {symbol}: SL price invalid (${sl_price})")
                        except Exception as e:
                            logger.error(f"[{node_name}] {symbol}: SL calculation error: {e}")
                    else:
                        if sl_perc <= 0:
                            logger.debug(f"[{node_name}] {symbol}: SL skipped (sl_perc={sl_perc})")
                    
                    # Log summary of TP/SL placement
                    if not tp_placed and tp_perc > 0:
                        logger.warning(f"⚠️ [{node_name}] {symbol}: TP was NOT placed! (tp_perc={tp_perc}, entry={entry_price:.6f})")
                    if not sl_placed and sl_perc > 0:
                        logger.warning(f"⚠️ [{node_name}] {symbol}: SL was NOT placed! (sl_perc={sl_perc}, entry={entry_price:.6f})")

                    # === NOW DO NON-CRITICAL OPERATIONS ===
                    
                    # CRITICAL: Verify position is actually open before tracking/notifying/clearing pending
                    position_found = False
                    try:
                        time.sleep(0.1)  # Small delay to allow Binance to update
                        positions = client.futures_position_information()
                        for p in positions:
                            if p['symbol'] == symbol:
                                amt = float(p['positionAmt'])
                                if amt != 0:
                                    position_found = True
                                    break
                        
                        if not position_found:
                            logger.warning(f"⚠️ Position {symbol} NOT found on Binance after order placement - NOT tracking/notifying")
                            # Keep pending active so trade can retry - DON'T clear it
                            return  # Exit early - don't track/notify if position doesn't exist
                    except Exception as e:
                        logger.error(f"❌ Position verification failed for {symbol}: {e} - NOT tracking/notifying")
                        # Keep pending active - DON'T clear it on verification failure
                        return  # Exit early - don't track/notify if verification fails
                    
                    # Position verified successfully - now safe to track/notify/clear pending
                    
                    # Track master position (for any master exchange) - ONLY if verification succeeded
                    if is_master_account:
                        with self.positions_lock:
                            self.master_positions[symbol] = {
                                'amount': qty if action == 'long' else -qty,
                                'entry': price,
                                'side': action.upper(),
                                'pnl': 0,
                                'leverage': leverage
                            }
                            logger.info(f"📍 Tracked master position: {symbol} {action.upper()}")
                    
                    # Clear pending trade now that position is verified and tracked
                    with self.pending_lock:
                        self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master_account:
                            if 'master' in self.pending_trades:
                                self.pending_trades['master'].discard(pending_key)
                                logger.debug(f"🔓 MASTER: Cleared pending {symbol} after position verified")
                    if is_master_account:
                        self._release_master_pending_symbol_sync(symbol)
                    
                    # Telegram notifications - ONLY if position is verified
                    try:
                        if self.telegram:
                            self.telegram.notify_trade_opened(node_name, symbol, action.upper(), qty, price)
                            user_tg = client_data.get('telegram_chat_id')
                            if user_tg:
                                self.telegram.notify_user_trade_opened(user_tg, symbol, action.upper(), qty, price)
                    except Exception as e:
                        logger.warning(f"Telegram notification failed: {e}")

                    self.executor.submit(self.push_update, user_id, client, 
                                        (user_id == 'master'))
                    
                except BinanceAPIException as e:
                    # Clear pending trade on error
                    with self.pending_lock:
                        self.pending_trades.get(user_id, set()).discard(pending_key)
                        if is_master_account:
                            self._release_master_pending_symbol_sync(symbol)
                    error_msg = f"Binance Error: {e.message}"
                    self.log_event(user_id, symbol, error_msg, is_error=True)
                    if self.telegram:
                        self.telegram.notify_error(node_name, symbol, error_msg)
                        chat_id = client_data.get('telegram_chat_id')
                        if chat_id:
                            self.telegram.notify_user_error(chat_id, symbol, error_msg)
                
        except Exception as e:
            # Clear pending trade on error
            with self.pending_lock:
                self.pending_trades.get(user_id, set()).discard(pending_key)
                if is_master_account:
                    self._release_master_pending_symbol_sync(symbol)
            error_msg = f"Engine Error: {str(e)[:100]}"
            self.log_event(user_id, symbol, error_msg, is_error=True)
            if self.telegram:
                self.telegram.notify_error(node_name, symbol, error_msg)
                chat_id = client_data.get('telegram_chat_id')
                if chat_id:
                    self.telegram.notify_user_error(chat_id, symbol, error_msg)

    def get_global_master_position_count(self) -> tuple:
        """
        Count positions GLOBALLY across all master exchanges.
        Returns: (total_unique_symbols, set_of_symbols)
        
        A position is counted once even if open on multiple exchanges.
        This ensures max_positions is global, not per-exchange.
        """
        all_symbols = set()
        
        # Check tracked positions first (faster)
        with self.positions_lock:
            all_symbols.update(self.master_positions.keys())
        
        # Also fetch live positions from all master exchanges to be sure
        for master_data in self.master_clients:
            try:
                if master_data.get('is_ccxt'):
                    # CCXT exchange
                    exchange = master_data['client']
                    positions = exchange.fetch_positions()
                    for pos in positions:
                        if pos.get('contracts') and float(pos['contracts']) != 0:
                            # Convert CCXT symbol back to standard format
                            symbol = pos.get('symbol', '').replace('/USDT:USDT', 'USDT').replace('/', '')
                            if symbol:
                                all_symbols.add(symbol)
                else:
                    # Binance client
                    client = master_data['client']
                    positions = client.futures_position_information()
                    for p in positions:
                        if float(p['positionAmt']) != 0:
                            all_symbols.add(p['symbol'])
            except Exception as e:
                logger.warning(f"Error fetching positions from {master_data.get('fullname')}: {e}")
        
        return len(all_symbols), all_symbols

    async def _get_user_global_open_count_async(self, user_clients: list) -> int:
        """Get total open position count across ALL exchanges for a single user."""
        total_open = 0
        for client_data in user_clients:
            try:
                if client_data.get('is_async'):
                    positions = await client_data['client'].fetch_positions()
                    for pos in positions:
                        if pos.get('contracts') and float(pos['contracts']) != 0:
                            total_open += 1
                else:
                    positions = await asyncio.to_thread(
                        client_data['client'].futures_position_information
                    )
                    for pos in positions:
                        if float(pos.get('positionAmt', 0)) != 0:
                            total_open += 1
            except Exception as e:
                logger.debug(f"User global position check failed: {e}")
        return total_open

    async def process_signal_batch(self, users: list, signal: dict, master_entry_price: float = 0.0,
                                     master_balance: float = 0.0, master_trade_cost: float = 0.0):
        """
        Execute trades for all users concurrently using asyncio.gather().
        
        Args:
            users: List of user/client data dicts to execute trades for
            signal: The trading signal dict
            master_entry_price: Current price from master
            master_balance: Master's available balance
            master_trade_cost: Master's trade cost for risk calculation
        """
        if not users:
            return []
        
        logger.info(f"🚀 process_signal_batch: Executing {signal['symbol']} for {len(users)} accounts concurrently")
        
        # Create async tasks for all users
        tasks = []
        for user_data in users:
            task = self.execute_trade_async(
                user_data, 
                signal.copy(), 
                master_entry_price, 
                master_balance, 
                master_trade_cost
            )
            tasks.append(task)
        
        # Execute all trades concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any exceptions and send Telegram notifications
        symbol = signal.get('symbol', 'UNKNOWN')
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                user_name = users[i].get('fullname', users[i].get('name', 'Unknown'))
                error_msg = f"Trade execution error: {str(result)[:100]}"
                logger.error(f"[{user_name}] {error_msg}")
                # Send Telegram notification
                if self.telegram:
                    self.telegram.notify_error(user_name, symbol, error_msg)
                    chat_id = users[i].get('telegram_chat_id')
                    if chat_id:
                        self.telegram.notify_user_error(chat_id, symbol, error_msg)
        
        return results

    async def process_signal_async(self, signal: dict):
        """Process incoming trading signal - ASYNC VERSION using asyncio.gather
        
        Instrumented with Prometheus metrics for signal tracking.
        """
        if self.is_paused:
            symbol = signal.get('symbol', 'UNKNOWN')
            error_msg = "Engine paused - signal ignored"
            logger.info(f"⏸️ {error_msg}")
            if self.telegram:
                self.telegram.notify_error("SYSTEM", symbol, error_msg)
            return
            
        # Clean symbol
        raw_symbol = signal['symbol']
        clean_symbol = re.sub(r'\.P|\.p|\.S|\.s$', '', raw_symbol).upper()
        signal['symbol'] = clean_symbol
        action = signal['action']

        # Record signal received metric
        record_signal(symbol=clean_symbol, action=action)
        
        logger.info(f"📥 Processing signal (async): {action.upper()} {clean_symbol}")
        
        # === DCA (Dollar Cost Averaging) ACTION HANDLING ===
        if action == 'dca':
            await self._process_dca_signal(signal, clean_symbol)
            return
        
        # Force signal params to admin global settings only
        global_risk = float(self._get_global_setting('risk_perc', 3.0))
        global_lev = int(float(self._get_global_setting('leverage', 20)))
        global_tp = float(self._get_global_setting('tp_perc', 5.0))
        global_sl = float(self._get_global_setting('sl_perc', 2.0))
        signal['risk'] = global_risk
        signal['lev'] = global_lev
        signal['tp_perc'] = global_tp
        signal['sl_perc'] = global_sl
        logger.info(f"📊 Signal params overridden by admin settings: risk={global_risk}%, lev={global_lev}x, TP={global_tp}%, SL={global_sl}%")
        
        # Get max_positions directly from the global settings reference
        max_pos_master = self.get_master_max_positions()
        
        # Initialize for tracking open symbols globally
        open_symbols = set()
        remaining_master_slots = None
        
        # === GLOBAL POSITION CHECK FOR MASTER EXCHANGES ===
        if self.master_clients and action != 'close':
            async with self._async_master_lock:
                # Check pending trades first (prevents race conditions)
                async with self._async_pending_lock:
                    pending_key = f"{clean_symbol}_master"
                    master_pending = self.pending_trades.get('master', set())
                    if pending_key in master_pending:
                        error_msg = f"Master position on {clean_symbol} already in progress"
                        logger.warning(f"⚠️ MASTER: {error_msg}")
                        if self.telegram:
                            self.telegram.notify_error("MASTER", clean_symbol, error_msg)
                        # Continue with slaves, don't return
                    else:
                        # Check current positions
                        global_pos_count, open_symbols = await self.get_global_master_position_count_async()

                        # Include pending positions in count (cross-process via Redis if available)
                        pending_symbols = await self._get_master_pending_symbols_async()
                        if not pending_symbols:
                            pending_symbols = set()
                            for p in master_pending:
                                if '_' in p:
                                    pending_symbols.add(p.split('_')[0])
                                else:
                                    pending_symbols.add(p)
                        all_symbols = open_symbols | pending_symbols
                        total_count = len(all_symbols)

                        logger.info(f"🔧 Master: max_positions={max_pos_master}, current_global={global_pos_count}, pending_symbols={pending_symbols}, open_symbols={open_symbols}, total={total_count}")

                        if clean_symbol in all_symbols:
                            error_msg = f"Already have position or pending on {clean_symbol}"
                            logger.warning(f"⚠️ MASTER: {error_msg}")
                            if self.telegram:
                                self.telegram.notify_error("MASTER", clean_symbol, error_msg)
                            # Continue with slaves, don't return - slaves may need this signal
                        else:
                            # Reserve a global slot in Redis (prevents multi-worker double opens)
                            reserve_result = await self._reserve_master_pending_symbol_async(
                                clean_symbol, max_pos_master, len(open_symbols)
                            )
                            if reserve_result == "max":
                                error_msg = f"Max positions reached ({total_count}/{max_pos_master}) - open: {global_pos_count}, pending: {len(pending_symbols)}"
                                logger.error(f"❌ MASTER: {clean_symbol}: {error_msg}. Open symbols: {open_symbols}, Pending: {pending_symbols}")
                                if self.telegram:
                                    self.telegram.notify_error("MASTER", clean_symbol, error_msg)
                                return
                            if reserve_result == "already":
                                error_msg = f"Already pending on {clean_symbol}"
                                logger.warning(f"⚠️ MASTER: {error_msg}")
                                if self.telegram:
                                    self.telegram.notify_error("MASTER", clean_symbol, error_msg)
                                # Continue with slaves, don't return
                            elif reserve_result is None:
                                if total_count >= max_pos_master:
                                    error_msg = f"Max positions reached ({total_count}/{max_pos_master}) - open: {global_pos_count}, pending: {len(pending_symbols)}"
                                    logger.error(f"❌ MASTER: {clean_symbol}: {error_msg}. Open symbols: {open_symbols}, Pending: {pending_symbols}")
                                    if self.telegram:
                                        self.telegram.notify_error("MASTER", clean_symbol, error_msg)
                                    return
                                # No Redis guard available, fall back to in-process pending
                                if 'master' not in self.pending_trades:
                                    self.pending_trades['master'] = set()
                                self.pending_trades['master'].add(pending_key)
                                logger.debug(f"🔒 MASTER: Marked {clean_symbol} as pending (no Redis guard)")
                                pending_symbols.add(clean_symbol)
                                total_count = len(open_symbols | pending_symbols)
                                remaining_master_slots = max_pos_master - total_count
                            else:
                                # Mark this trade as pending BEFORE opening to prevent race conditions
                                if 'master' not in self.pending_trades:
                                    self.pending_trades['master'] = set()
                                self.pending_trades['master'].add(pending_key)
                                logger.debug(f"🔒 MASTER: Marked {clean_symbol} as pending (preventing race condition)")
                                pending_symbols.add(clean_symbol)
                                total_count = len(open_symbols | pending_symbols)
                                remaining_master_slots = max_pos_master - total_count

        # Get master's current state (from primary Binance if available)
        master_entry_price, master_balance, master_trade_cost = 0.0, 0.0, 0.0
        symbol_is_invalid = False
        
        if self.master_client:
            try:
                self.api_limiter.wait_and_proceed("master_info")
                ticker = self.master_client.futures_symbol_ticker(symbol=clean_symbol)
                master_entry_price = float(ticker['price'])
                
                balances = self.master_client.futures_account_balance()
                for b in balances:
                    if b['asset'] == 'USDT':
                        master_balance = float(b.get('availableBalance', b['balance']))
                        break
                        
                master_trade_cost = master_balance * (global_risk / 100.0)
                
            except Exception as e:
                logger.error(f"⚠️ Master info error: {e}")
                # Check if this is an invalid symbol error
                error_str = str(e).lower()
                if 'invalid symbol' in error_str or '-1121' in str(e):
                    symbol_is_invalid = True
                    logger.warning(f"⚠️ {clean_symbol} is not a valid Binance Futures symbol - releasing pending")
                    # Release pending symbol immediately for invalid symbols
                    await self._release_master_pending_symbol_async(clean_symbol)
                    # Clear in-memory pending too
                    if 'master' in self.pending_trades:
                        pending_key = f"{clean_symbol}_master"
                        self.pending_trades['master'].discard(pending_key)
                    return  # Don't process invalid symbols

        # Collect all users to execute trades for
        all_users = []
        
        logger.info(f"🔧 Master max_positions setting: {max_pos_master}")
        
        # === MASTER EXCHANGES (LIMITED BY REMAINING SLOTS) ===
        if self.master_clients:
            master_clients_to_use = self.master_clients
            if remaining_master_slots is not None:
                master_clients_to_use = self.master_clients[:max(0, remaining_master_slots)]
            logger.info(f"📊 Preparing {clean_symbol} for {len(master_clients_to_use)} MASTER exchanges")
            for master_data in master_clients_to_use:
                master_data_copy = master_data.copy()
                master_data_copy['risk'] = 0
                master_data_copy['leverage'] = 0
                master_data_copy['max_pos'] = max_pos_master
                master_data_copy['skip_position_check'] = True
                master_data_copy['global_open_symbols'] = open_symbols
                all_users.append(master_data_copy)
        elif self.master_client:
            logger.info("📊 Using legacy single master client")
            master_data = {
                'id': 'master', 
                'name': 'MASTER_ACC', 
                'fullname': 'MASTER',
                'client': self.master_client, 
                'is_paused': False, 
                'risk': 0, 
                'leverage': 0, 
                'max_pos': max_pos_master,
                'lock': self.master_lock
            }
            all_users.append(master_data)
        else:
            logger.warning("⚠️ No master exchanges configured!")

        # === SLAVE ACCOUNTS (filtered by strategy subscription) ===
        strategy_id = signal.get('strategy_id')
        
        async with self._async_lock:
            all_slaves = list(self.slave_clients)
        
        # Filter slaves by strategy subscription
        if strategy_id:
            with self.app.app_context():
                # Get all active subscriptions for this strategy
                subscriptions = StrategySubscription.query.filter_by(
                    strategy_id=strategy_id,
                    is_active=True
                ).all()
                
                # Create a map of user_id -> allocation_percent
                subscription_map = {sub.user_id: sub.allocation_percent for sub in subscriptions}
                
                # Filter slaves to only those subscribed to this strategy
                filtered_slaves = []
                for slave in all_slaves:
                    user_id = slave['id']
                    if user_id in subscription_map:
                        # Add allocation_percent to slave data for trade size calculation
                        slave_copy = slave.copy()
                        slave_copy['allocation_percent'] = subscription_map[user_id]
                        filtered_slaves.append(slave_copy)
                
                slaves = filtered_slaves
                logger.info(f"📊 Strategy {strategy_id}: {len(slaves)} subscribed slaves (of {len(all_slaves)} total)")
                if len(slaves) == 0 and len(all_slaves) > 0:
                    logger.warning(f"⚠️ Strategy {strategy_id}: NO SUBSCRIPTIONS FOUND! {len(all_slaves)} total slaves exist but none are subscribed to this strategy!")
        else:
            # No strategy specified - process all slaves with 100% allocation (backward compatibility)
            slaves = []
            for slave in all_slaves:
                slave_copy = slave.copy()
                slave_copy['allocation_percent'] = 100.0
                slaves.append(slave_copy)
            logger.info(f"📊 No strategy specified - preparing all {len(slaves)} slave accounts")
        
        # Pre-compute global open positions per user (across all exchanges)
        if slaves and action != 'close':
            user_groups = {}
            for slave in slaves:
                user_groups.setdefault(slave['id'], []).append(slave)
            tasks = {
                user_id: asyncio.create_task(self._get_user_global_open_count_async(user_clients))
                for user_id, user_clients in user_groups.items()
            }
            for user_id, task in tasks.items():
                try:
                    open_count = await task
                except Exception as e:
                    logger.debug(f"User {user_id} global open count failed: {e}")
                    open_count = 0
                for slave in user_groups[user_id]:
                    slave['global_open_count'] = open_count

        if slaves:
            all_users.extend(slaves)
        
        # CRITICAL: Log if no users to process
        if not all_users:
            error_msg = f"❌ NO USERS TO PROCESS: Signal {action.upper()} {clean_symbol} ignored - no master or slave accounts configured/active"
            logger.error(error_msg)
            logger.error(f"   Master clients: {len(self.master_clients) if self.master_clients else 0}")
            logger.error(f"   Master client (legacy): {1 if self.master_client else 0}")
            logger.error(f"   Slave clients: {len(self.slave_clients)}")
            logger.error(f"   Strategy ID: {strategy_id}")
            if self.telegram:
                self.telegram.notify_error("SYSTEM", clean_symbol, error_msg)
            return
        
        logger.info(f"✅ Processing signal for {len(all_users)} users ({len(self.master_clients) if self.master_clients else 0} master, {len(slaves)} slaves)")
        
        # Execute all trades concurrently using asyncio.gather
        await self.process_signal_batch(
            all_users, signal, master_entry_price, master_balance, master_trade_cost
        )
        
        # Record signal processed metric
        record_signal_processed(symbol=clean_symbol, action=action, status='success')
        
        # Update active users count
        master_count = len(self.master_clients) if self.master_clients else (1 if self.master_client else 0)
        slave_count = len(self.slave_clients)
        update_active_users(exchange='all', user_type='master', count=master_count)
        update_active_users(exchange='all', user_type='slave', count=slave_count)

    def process_signal(self, signal: dict):
        """Process incoming trading signal - SYNC WRAPPER"""
        symbol = signal.get('symbol', 'UNKNOWN')
        if self.is_paused:
            error_msg = "Engine paused - signal ignored"
            logger.info(f"⏸️ {error_msg}")
            if self.telegram:
                self.telegram.notify_error("SYSTEM", symbol, error_msg)
            return
        
        # Try to run async version in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Event loop is running - use thread pool to run async code
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_async_signal_in_thread, signal)
                    try:
                        future.result(timeout=60)  # 60 second timeout for signal processing
                    except concurrent.futures.TimeoutError:
                        error_msg = f"Signal processing timed out for {symbol}"
                        logger.error(error_msg)
                        if self.telegram:
                            self.telegram.notify_error("SYSTEM", symbol, error_msg)
            else:
                loop.run_until_complete(self.process_signal_async(signal))
        except RuntimeError:
            # No event loop running, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.process_signal_async(signal))
            finally:
                loop.close()
    
    def _run_async_signal_in_thread(self, signal: dict):
        """Helper to run async signal processing in a separate thread with its own event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.process_signal_async(signal))
        finally:
            loop.close()
    
    async def get_global_master_position_count_async(self) -> tuple:
        """
        Count positions GLOBALLY across all master exchanges - ASYNC VERSION.
        Returns: (total_unique_symbols, set_of_symbols)
        """
        all_symbols = set()
        
        # Check tracked positions first (faster)
        async with self._async_positions_lock:
            all_symbols.update(self.master_positions.keys())
        
        # Fetch live positions from all master exchanges concurrently
        async def fetch_positions_from_master(master_data):
            symbols = set()
            try:
                if master_data.get('is_async') and master_data.get('is_ccxt'):
                    # Async CCXT exchange
                    exchange = master_data['client']
                    positions = await exchange.fetch_positions()
                    for pos in positions:
                        if pos.get('contracts') and float(pos['contracts']) != 0:
                            symbol = pos.get('symbol', '').replace('/USDT:USDT', 'USDT').replace('/', '')
                            if symbol:
                                symbols.add(symbol)
                elif not master_data.get('is_ccxt'):
                    # Binance client (sync)
                    client = master_data['client']
                    positions = client.futures_position_information()
                    for p in positions:
                        if float(p['positionAmt']) != 0:
                            symbols.add(p['symbol'])
            except Exception as e:
                logger.warning(f"Error fetching positions from {master_data.get('fullname')}: {e}")
            return symbols
        
        # Fetch from all masters concurrently
        tasks = [fetch_positions_from_master(m) for m in self.master_clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, set):
                all_symbols.update(result)
        
        return len(all_symbols), all_symbols
    
    # ==================== DCA (Dollar Cost Averaging) ====================
    
    async def _process_dca_signal(self, signal: dict, symbol: str):
        """
        Process a DCA signal - execute additional buy/sell to average position.
        
        DCA is triggered when:
        1. Signal action is 'dca'
        2. User has existing position on the symbol
        3. Current PnL is below the DCA threshold (e.g., -2%)
        4. DCA count is below max_dca_orders
        
        Args:
            signal: Signal dict with 'symbol', 'action', 'side' (optional), etc.
            symbol: Cleaned symbol name
        """
        if not self.smart_features:
            logger.warning("Smart Features not initialized, cannot process DCA")
            return
        
        logger.info(f"📉 Processing DCA signal for {symbol}")
        
        # Get the original side from signal or try to determine from positions
        target_side = signal.get('side', '').upper()  # 'LONG' or 'SHORT' if specified
        
        # Collect users with DCA enabled and existing positions
        dca_candidates = []
        
        # Check slave clients for DCA eligibility
        async with self._async_lock:
            for slave_data in self.slave_clients:
                user_id = slave_data['id']
                
                # Check if user has DCA enabled
                dca_enabled = slave_data.get('dca_enabled', False)
                if not dca_enabled:
                    continue
                
                # Get DCA settings
                dca_threshold = slave_data.get('dca_threshold', -2.0)
                dca_multiplier = slave_data.get('dca_multiplier', 1.0)
                dca_max_orders = slave_data.get('dca_max_orders', 3)
                
                # Check current DCA count
                current_dca_count = await self.smart_features.get_dca_count(str(user_id), symbol)
                if current_dca_count >= dca_max_orders:
                    logger.debug(f"DCA limit reached for {user_id} on {symbol}: {current_dca_count}/{dca_max_orders}")
                    continue
                
                # Check if user has position and get PnL
                try:
                    client = slave_data.get('client')
                    if not client:
                        continue
                    
                    positions = None
                    if slave_data.get('is_ccxt') and slave_data.get('is_async'):
                        positions = await client.fetch_positions([symbol])
                    elif not slave_data.get('is_ccxt'):
                        positions = client.futures_position_information(symbol=symbol)
                    
                    if not positions:
                        continue
                    
                    # Find position for this symbol
                    for pos in positions:
                        amt = 0
                        entry = 0
                        current = 0
                        side = ''
                        
                        if slave_data.get('is_ccxt'):
                            # CCXT format
                            amt = float(pos.get('contracts', 0))
                            entry = float(pos.get('entryPrice', 0))
                            current = float(pos.get('markPrice', 0))
                            side = 'LONG' if pos.get('side', '').lower() == 'long' else 'SHORT'
                        else:
                            # Binance format
                            amt = float(pos.get('positionAmt', 0))
                            entry = float(pos.get('entryPrice', 0))
                            current = float(pos.get('markPrice', 0))
                            side = 'LONG' if amt > 0 else 'SHORT'
                        
                        if amt == 0 or entry == 0:
                            continue
                        
                        # If target_side specified, check it matches
                        if target_side and side != target_side:
                            continue
                        
                        # Calculate PnL percentage
                        pnl_pct = await calculate_position_pnl_pct(entry, current, side)
                        
                        logger.debug(f"DCA check for {user_id} on {symbol}: PnL={pnl_pct:.2f}%, threshold={dca_threshold}%")
                        
                        # Check if PnL is below threshold
                        if pnl_pct < dca_threshold:
                            dca_candidates.append({
                                'user_data': slave_data,
                                'position': pos,
                                'side': side,
                                'pnl_pct': pnl_pct,
                                'dca_multiplier': dca_multiplier,
                                'entry_price': entry,
                                'current_price': current,
                                'qty': abs(amt)
                            })
                            logger.info(f"✅ DCA candidate: {user_id} on {symbol} (PnL: {pnl_pct:.2f}%)")
                
                except Exception as e:
                    logger.error(f"Error checking DCA eligibility for {user_id}: {e}")
        
        if not dca_candidates:
            logger.info(f"📉 No DCA candidates found for {symbol}")
            return
        
        logger.info(f"📉 Executing DCA for {len(dca_candidates)} candidates on {symbol}")
        
        # Execute DCA for each candidate
        for candidate in dca_candidates:
            await self._execute_dca_order(
                candidate['user_data'],
                symbol,
                candidate['side'],
                candidate['qty'],
                candidate['dca_multiplier'],
                candidate['current_price']
            )
    
    async def _execute_dca_order(
        self,
        user_data: dict,
        symbol: str,
        side: str,
        original_qty: float,
        multiplier: float,
        current_price: float
    ):
        """
        Execute a DCA order for a user.
        
        Args:
            user_data: User's exchange client data
            symbol: Trading symbol
            side: Position side ('LONG' or 'SHORT')
            original_qty: Original position quantity
            multiplier: DCA size multiplier
            current_price: Current market price
        """
        user_id = user_data['id']
        node_name = user_data.get('fullname', str(user_id))
        
        try:
            # Calculate DCA quantity
            dca_qty = original_qty * multiplier
            
            # Determine order side (same as position direction)
            order_side = 'BUY' if side == 'LONG' else 'SELL'
            
            logger.info(f"📉 Executing DCA: {order_side} {dca_qty} {symbol} for {node_name}")
            
            if user_data.get('is_ccxt') and user_data.get('is_async'):
                # Async CCXT
                exchange = user_data['client']
                ccxt_symbol = self.convert_symbol_to_ccxt(symbol, user_data.get('exchange_type', 'binance'))
                
                order = await exchange.create_market_order(
                    ccxt_symbol,
                    order_side.lower(),
                    dca_qty
                )
                logger.info(f"✅ DCA order executed for {node_name}: {order.get('id', 'OK')}")
                
            elif not user_data.get('is_ccxt'):
                # Binance client
                client = user_data['client']
                
                # Get precision
                prec = self.get_precision(client, symbol)
                qty_str = f"{dca_qty:.{prec['qty_prec']}f}"
                
                order = client.futures_create_order(
                    symbol=symbol,
                    side=order_side,
                    type='MARKET',
                    quantity=qty_str
                )
                logger.info(f"✅ DCA order executed for {node_name}: Order ID {order.get('orderId', 'OK')}")
            
            # Increment DCA count
            if self.smart_features:
                new_count = await self.smart_features.increment_dca_count(str(user_id), symbol)
                logger.info(f"📊 DCA count for {user_id} on {symbol}: {new_count}")
            
            # Log event
            self.log_event(user_id, symbol, f"DCA {order_side} executed (qty: {dca_qty:.4f})")
            
            # Telegram notification
            if self.telegram:
                self.telegram.notify_trade_opened(
                    f"{node_name} (DCA)",
                    symbol,
                    f"DCA {side}",
                    dca_qty,
                    current_price
                )
            
        except Exception as e:
            logger.error(f"❌ DCA order failed for {node_name} on {symbol}: {e}")
            self.log_event(user_id, symbol, f"DCA FAILED: {str(e)[:50]}", is_error=True)
    
    # ==================== TRAILING STOP-LOSS ====================
    
    async def register_trailing_sl_for_position(
        self,
        user_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        qty: float,
        sl_price: float,
        activation_pct: float = None,
        callback_pct: float = None
    ) -> bool:
        """
        Register a position for trailing stop-loss monitoring.
        
        Called after a position is opened if user has trailing_sl_enabled.
        
        Args:
            user_id: User ID
            symbol: Trading symbol
            side: 'LONG' or 'SHORT'
            entry_price: Entry price
            qty: Position quantity
            sl_price: Initial stop-loss price
            activation_pct: Activation threshold (%)
            callback_pct: Trail distance (%)
        
        Returns:
            True if registered successfully
        """
        if not self.smart_features:
            logger.warning("Smart Features not available, cannot register trailing SL")
            return False
        
        return await self.smart_features.register_trailing_sl(
            user_id=str(user_id),
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            qty=qty,
            initial_sl=sl_price,
            activation_pct=activation_pct,
            callback_pct=callback_pct
        )
    
    async def start_trailing_sl_monitor(self):
        """Start the trailing stop-loss price monitor"""
        if not self.smart_features:
            logger.warning("Smart Features not available, cannot start trailing SL monitor")
            return
        
        await self.smart_features.start_price_monitor()
        logger.info("🚀 Trailing stop-loss monitor started")
    
    async def stop_trailing_sl_monitor(self):
        """Stop the trailing stop-loss price monitor"""
        if self.smart_features:
            await self.smart_features.stop_price_monitor()
            logger.info("🛑 Trailing stop-loss monitor stopped")

    def shutdown(self):
        """Shutdown background executor to prevent thread leaks."""
        try:
            if getattr(self, "executor", None):
                self.executor.shutdown(wait=False)
        except Exception as e:
            logger.warning(f"⚠️ Error shutting down executor: {e}")
    
    async def cleanup_position_smart_features(self, user_id: str, symbol: str):
        """
        Clean up smart features data when a position is closed.
        
        Called after position close to remove trailing SL tracking and reset DCA count.
        """
        if not self.smart_features:
            return
        
        try:
            # Remove trailing SL tracking
            await self.smart_features.remove_trailing_sl(str(user_id), symbol)
            
            # Reset DCA count
            await self.smart_features.reset_dca_count(str(user_id), symbol)
            
            logger.info(f"🧹 Cleaned up smart features for {user_id} on {symbol}")
            
        except Exception as e:
            logger.error(f"Error cleaning up smart features: {e}")
