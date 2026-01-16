"""
Brain Capital - Copy Trading Platform
Main Flask Application with Enhanced Security
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort, g, send_from_directory, Response
from werkzeug.exceptions import HTTPException
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room
from authlib.integrations.flask_client import OAuth
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AttestationConveyancePreference,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    RegistrationCredential,
    AuthenticationCredential,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType
)
from webauthn.helpers.base64url_to_bytes import base64url_to_bytes
from webauthn.helpers.bytes_to_base64url import bytes_to_base64url
from config import Config
from models import db, User, TradeHistory, BalanceHistory, Message, PasswordResetToken, UserExchange, ExchangeConfig, Payment, Strategy, StrategySubscription, ChatMessage, ChatBan, SystemStats, UserLevel, UserAchievement, ApiKey, UserConsent, WebAuthnCredential
from sqlalchemy import text
from trading_engine import TradingEngine
from telegram_notifier import init_notifier, get_notifier, init_email_sender, get_email_sender
from telegram_bot import init_telegram_bot, get_telegram_bot
from metrics import get_metrics, init_flask_metrics, set_app_info
from security import (
    login_tracker, login_limiter, api_limiter, webhook_limiter,
    InputValidator, add_security_headers, get_client_ip,
    init_session_security, verify_session, generate_csrf_token,
    verify_csrf_token, audit, rate_limit, validate_webhook, validate_json_payload, is_safe_redirect_url
)
import asyncio
import threading
from queue import Queue
from datetime import datetime, timedelta, timezone
import random
import html
import logging
import re
import time
import os
import sys
import json
import secrets
from http.client import RemoteDisconnected
import urllib3.exceptions

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BrainCapital")

# Create logs directory
import os
os.makedirs('logs', exist_ok=True)

# Add file handler for all logs
_file_handler = logging.FileHandler('logs/app.log', encoding='utf-8')
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s'
))
logging.getLogger().addHandler(_file_handler)

# Global exception hook to catch unhandled exceptions
def _global_exception_handler(exc_type, exc_value, exc_traceback):
    """Global exception handler that logs unhandled exceptions"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't log keyboard interrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )

sys.excepthook = _global_exception_handler

# ==================== SENTRY ERROR TRACKING ====================
# Optional: Set SENTRY_DSN environment variable to enable error tracking
try:
    from sentry_config import init_sentry
    SENTRY_ENABLED = init_sentry(framework='flask')
except ImportError:
    SENTRY_ENABLED = False
    logger.info("Sentry not configured (optional)")

# Initialize Flask app
app = Flask(__name__)
try:
    app.config.from_object(Config)
except Exception as e:
    logger.critical(f"Failed to load configuration: {e}")
    exit(1)

# ==================== SECURE SESSION CONFIGURATION ====================
# SECURITY HARDENED: Production-ready session settings
import os
IS_PRODUCTION = os.environ.get('FLASK_ENV', 'development') == 'production'

# Check if HTTPS is enforced (only enable secure cookies if SSL is configured)
# This prevents CSRF failures when accessing via HTTP
SSL_ENABLED = bool(os.environ.get('SSL_CERT_PATH')) or bool(os.environ.get('HTTPS_ENABLED', '').lower() == 'true')

app.config.update(
    SESSION_COOKIE_SECURE=SSL_ENABLED,  # Only True when HTTPS is actually configured
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE='Lax',  # Lax allows form submissions, Strict was too restrictive
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  # Reduced to 8 hours for security
    SESSION_REFRESH_EACH_REQUEST=True,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # Max 16MB upload
    WTF_CSRF_TIME_LIMIT=3600,  # CSRF token expires after 1 hour
)

# ==================== OAUTH CONFIGURATION ====================
oauth = OAuth(app)
if Config.GOOGLE_CLIENT_ID and Config.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        client_id=Config.GOOGLE_CLIENT_ID,
        client_secret=Config.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

# Initialize database and login
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Будь ласка, увійдіть для доступу до цієї сторінки.'
login_manager.login_message_category = 'info'

# Initialize SocketIO with secure CORS settings
# SECURITY: Configure your production domain(s) via ALLOWED_ORIGINS environment variable
# Example: ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Production domain from environment (comma-separated for multiple domains)
PRODUCTION_DOMAIN = os.environ.get('PRODUCTION_DOMAIN', '')

if IS_PRODUCTION and PRODUCTION_DOMAIN:
    # In production, only allow the configured domain(s)
    SOCKETIO_ALLOWED_ORIGINS = [origin.strip() for origin in PRODUCTION_DOMAIN.split(',')]
else:
    # Development origins
    SOCKETIO_ALLOWED_ORIGINS = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:5000",
        "http://127.0.0.1",
        "http://127.0.0.1:80",
        "http://127.0.0.1:5000",
        "http://38.180.143.20",
        "http://38.180.143.20:80",
        "https://38.180.143.20",
        "http://38.180.147.102",
        "http://38.180.147.102:80",
        "https://38.180.147.102",
        "http://mimic.cash",
        "https://mimic.cash",
        "http://www.mimic.cash",
        "https://www.mimic.cash",
        "http://mimiccash.com",
        "https://mimiccash.com",
        "http://www.mimiccash.com",
        "https://www.mimiccash.com",
    ]

# Add custom origins from environment if set (for additional origins)
if os.environ.get('ALLOWED_ORIGINS'):
    SOCKETIO_ALLOWED_ORIGINS.extend(os.environ.get('ALLOWED_ORIGINS', '').split(','))

socketio = SocketIO(
    app, 
    async_mode='eventlet',  # MUST match gunicorn --worker-class eventlet
    ping_timeout=60,
    ping_interval=25,  # Keep connections alive
    cors_allowed_origins=SOCKETIO_ALLOWED_ORIGINS,
    cookie='io',  # Fixed: must be string cookie name, not boolean
    manage_session=False,
    logger=False,  # Reduce logging overhead
    engineio_logger=False
)

# Initialize Redis (optional) and ARQ for task queue
redis_client = None
arq_pool = None
signal_queue = Queue()
ARQ_REDIS_SETTINGS = None  # Initialize to None by default

try:
    import redis
    if app.config.get('REDIS_URL'):
        try:
            redis_client = redis.from_url(app.config['REDIS_URL'])
            redis_client.ping()
            logger.info("✅ Redis connected - Persistent queue active")
            
            # Initialize ARQ pool for task queueing
            try:
                from arq import create_pool
                from arq.connections import RedisSettings
                from urllib.parse import urlparse
                
                def get_arq_settings(url: str) -> RedisSettings:
                    """Parse Redis URL into ARQ RedisSettings"""
                    parsed = urlparse(url)
                    return RedisSettings(
                        host=parsed.hostname or 'localhost',
                        port=parsed.port or 6379,
                        database=int(parsed.path.lstrip('/') or 0) if parsed.path else 0,
                        password=parsed.password,
                        ssl=parsed.scheme == 'rediss',
                    )
                
                ARQ_REDIS_SETTINGS = get_arq_settings(app.config['REDIS_URL'])
                logger.info("✅ ARQ task queue configured")
            except ImportError:
                logger.warning("⚠️ ARQ not installed. Tasks will use legacy Redis queue.")
                ARQ_REDIS_SETTINGS = None
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}. Using in-memory queue.")
            redis_client = None
            ARQ_REDIS_SETTINGS = None
except ImportError:
    logger.info("ℹ️ Redis not installed. Using in-memory queue.")
    ARQ_REDIS_SETTINGS = None

# Initialize Telegram notifier
telegram = None
if hasattr(Config, 'TG_ENABLED') and Config.TG_ENABLED:
    telegram = init_notifier(Config.TG_TOKEN, Config.TG_CHAT_ID, True)
    if telegram and telegram.enabled:
        logger.info("✅ Telegram notifications enabled")
        
        # Initialize comprehensive error logging to Telegram
        try:
            from telegram_notifier import setup_comprehensive_error_logging
            error_log_handler = setup_comprehensive_error_logging(
                telegram_notifier=telegram,
                log_dir="logs",
                include_warnings=True  # Send all warnings and errors to admin
            )
            logger.info("✅ Error notifications to Telegram enabled - admin will receive all errors")
        except Exception as e:
            logger.warning(f"⚠️ Could not setup Telegram error logging: {e}")
    else:
        logger.warning("⚠️ Telegram notifications NOT active (check bot token/chat_id)")

# Initialize Email sender
email_sender = None
EMAIL_CONFIGURED = False
if hasattr(Config, 'EMAIL_ENABLED') and Config.EMAIL_ENABLED:
    # Check which SMTP settings are missing and log them for debugging
    smtp_missing = []
    if not getattr(Config, 'SMTP_SERVER', None):
        smtp_missing.append('SMTP_SERVER')
    if not getattr(Config, 'SMTP_USERNAME', None):
        smtp_missing.append('SMTP_USERNAME')
    if not getattr(Config, 'SMTP_PASSWORD', None):
        smtp_missing.append('SMTP_PASSWORD')
    if not getattr(Config, 'SMTP_FROM_EMAIL', None):
        smtp_missing.append('SMTP_FROM_EMAIL')
    
    if smtp_missing:
        logger.warning(f"⚠️ Email sender NOT active - missing settings: {', '.join(smtp_missing)}")
        logger.warning("   Set these in your .env file or config.ini [Email] section")
    else:
        email_sender = init_email_sender(
            smtp_server=Config.SMTP_SERVER,
            smtp_port=Config.SMTP_PORT,
            username=Config.SMTP_USERNAME,
            password=Config.SMTP_PASSWORD,
            from_email=Config.SMTP_FROM_EMAIL,
            from_name=Config.SMTP_FROM_NAME,
            enabled=True
        )
        if email_sender and email_sender.enabled:
            logger.info("✅ Email sender enabled")
            EMAIL_CONFIGURED = True
        else:
            logger.warning("⚠️ Email sender NOT active (SMTP connection failed)")
            logger.warning("   Verify SMTP server, port, username, and password are correct")
else:
    logger.info("ℹ️ Email not configured in config.ini - password reset via email disabled")
    logger.info("   To enable: Set [Email] enabled=true in config.ini and configure SMTP settings")
    email_sender = get_email_sender()  # May be None

# Initialize Trading Engine
engine = TradingEngine(app, socketio, telegram)

# ==================== TELEGRAM BOT (REMOVED FROM WEB SERVER) ====================
# The Telegram Bot now runs as a SEPARATE SERVICE to prevent 409 Conflict errors.
# 
# WHY: When Gunicorn spawns multiple workers, each worker was trying to start the bot,
# causing "409 Conflict" errors because Telegram only allows ONE polling connection.
#
# SOLUTION: Bot runs in complete isolation via run_bot.py
#   - Start with: sudo systemctl start mimic-bot
#   - Logs at: /var/www/mimic/logs/bot_stdout.log
#   - Service file: mimic-bot.service
#
# This ensures:
#   ✓ Only ONE bot instance polls Telegram (no conflicts)
#   ✓ Gunicorn workers scale independently without affecting the bot
#   ✓ Bot can restart without affecting web traffic
#   ✓ Clean separation of concerns
#
# NOTE: The bot can still be accessed by other modules via get_telegram_bot() if needed,
# but it will return None in the web server context since the bot runs separately.
telegram_bot = None
logger.info("ℹ️ Telegram Bot runs as separate service (see mimic-bot.service)")

# Initialize Compliance Middleware (Geo-blocking + TOS Consent)
try:
    from compliance import init_compliance
    init_compliance(app)
except Exception as e:
    logger.warning(f"⚠️ Compliance middleware failed to initialize: {e}")

# Global trade settings
GLOBAL_TRADE_SETTINGS = {
    'risk_perc': 3.0,
    'leverage': 20,
    'tp_perc': 5.0,
    'sl_perc': 2.0,
    'max_positions': 10,
    'min_order_cost': 1.0,  # Lowered to $1
    'min_balance': 1.0  # Minimum balance required to trade (default $1)
}
engine.min_order_cost = GLOBAL_TRADE_SETTINGS['min_order_cost']
engine.set_global_settings(GLOBAL_TRADE_SETTINGS)  # Link settings for live reading


# ==================== HELPER FUNCTIONS ====================

def log_system_event(user_id, symbol, message, is_error=False):
    """Log event and emit to WebSocket"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {
        'time': timestamp,
        'symbol': symbol or 'SYSTEM',
        'message': message,
        'is_error': is_error
    }
    try:
        socketio.emit('new_log', entry, room="admin_room")
        if user_id and user_id != 'master':
            socketio.emit('new_log', entry, room=f"user_{user_id}")
    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
            urllib3.exceptions.ProtocolError):
        # Client disconnected - expected behavior, silently ignore
        pass

engine.log_error_callback = log_system_event


_balance_cache = {}
_balance_cache_lock = threading.Lock()
_balance_cache_inflight = set()
_balance_cache_ttl = int(os.environ.get('BALANCE_CACHE_TTL', '60'))


def _get_json_cache_from_redis(cache_key: str):
    """Fetch JSON cache from Redis if available."""
    if not redis_client:
        return None
    try:
        cached = redis_client.get(cache_key)
        if not cached:
            return None
        return json.loads(cached)
    except Exception as e:
        logger.debug(f"Redis cache read failed for {cache_key}: {e}")
        return None


def _set_json_cache_to_redis(cache_key: str, data: dict, ttl_seconds: int) -> None:
    """Store JSON cache in Redis if available."""
    if not redis_client:
        return
    try:
        redis_client.setex(cache_key, ttl_seconds, json.dumps(data))
    except Exception as e:
        logger.debug(f"Redis cache write failed for {cache_key}: {e}")


def _get_balance_cache_from_redis(user_id: int):
    """Fetch balance cache from Redis if available."""
    key = f"user_balance:{user_id}"
    return _get_json_cache_from_redis(key)


def _set_balance_cache_to_redis(user_id: int, data: dict) -> None:
    """Store balance cache in Redis if available."""
    key = f"user_balance:{user_id}"
    _set_json_cache_to_redis(key, data, _balance_cache_ttl)


_admin_stats_cache = {}
_admin_stats_lock = threading.Lock()
_admin_stats_inflight = set()
_admin_stats_ttl = int(os.environ.get('ADMIN_STATS_CACHE_TTL', '30'))
_public_stats_cache = {}
_public_stats_lock = threading.Lock()
_public_stats_inflight = set()
_public_stats_ttl = int(os.environ.get('PUBLIC_STATS_CACHE_TTL', '60'))


def _refresh_admin_stats_cache(cache_key: str, compute_fn) -> None:
    """Refresh cached admin stats asynchronously."""
    try:
        with app.app_context():
            data = compute_fn()
        with _admin_stats_lock:
            _admin_stats_cache[cache_key] = {
                'data': data,
                'ts': time.time()
            }
        _set_json_cache_to_redis(f"admin_stats:{cache_key}", data, _admin_stats_ttl)
    finally:
        with _admin_stats_lock:
            _admin_stats_inflight.discard(cache_key)


def get_admin_stats_cached(cache_key: str, compute_fn, allow_stale: bool = True, ttl: int = None) -> dict:
    """
    Get cached admin stats with async refresh.
    
    Args:
        cache_key: Unique cache key
        compute_fn: Callable that returns the stats dict
        allow_stale: Return stale data while refreshing in background
        ttl: Optional TTL override in seconds
    """
    now = time.time()
    ttl = ttl if ttl is not None else _admin_stats_ttl

    redis_cached = _get_json_cache_from_redis(f"admin_stats:{cache_key}")
    if redis_cached:
        return redis_cached
    
    with _admin_stats_lock:
        cached = _admin_stats_cache.get(cache_key)
    
    if cached:
        age = now - cached['ts']
        if age <= ttl:
            return cached['data']
        if allow_stale:
            with _admin_stats_lock:
                if cache_key not in _admin_stats_inflight:
                    _admin_stats_inflight.add(cache_key)
                    threading.Thread(
                        target=_refresh_admin_stats_cache,
                        args=(cache_key, compute_fn),
                        daemon=True
                    ).start()
            return cached['data']
    
    data = compute_fn()
    with _admin_stats_lock:
        _admin_stats_cache[cache_key] = {'data': data, 'ts': now}
    _set_json_cache_to_redis(f"admin_stats:{cache_key}", data, ttl)
    return data


def _refresh_public_stats_cache(cache_key: str, compute_fn, ttl: int) -> None:
    """Refresh cached public stats asynchronously."""
    try:
        with app.app_context():
            data = compute_fn()
        with _public_stats_lock:
            _public_stats_cache[cache_key] = {
                'data': data,
                'ts': time.time()
            }
        _set_json_cache_to_redis(f"public_stats:{cache_key}", data, ttl)
    finally:
        with _public_stats_lock:
            _public_stats_inflight.discard(cache_key)


def get_public_stats_cached(cache_key: str, compute_fn, allow_stale: bool = True, ttl: int = None) -> dict:
    """
    Get cached public stats with async refresh.
    """
    now = time.time()
    ttl = ttl if ttl is not None else _public_stats_ttl

    redis_cached = _get_json_cache_from_redis(f"public_stats:{cache_key}")
    if redis_cached:
        return redis_cached

    with _public_stats_lock:
        cached = _public_stats_cache.get(cache_key)

    if cached:
        age = now - cached['ts']
        if age <= ttl:
            return cached['data']
        if allow_stale:
            with _public_stats_lock:
                if cache_key not in _public_stats_inflight:
                    _public_stats_inflight.add(cache_key)
                    threading.Thread(
                        target=_refresh_public_stats_cache,
                        args=(cache_key, compute_fn, ttl),
                        daemon=True
                    ).start()
            return cached['data']

    data = compute_fn()
    with _public_stats_lock:
        _public_stats_cache[cache_key] = {'data': data, 'ts': now}
    _set_json_cache_to_redis(f"public_stats:{cache_key}", data, ttl)
    return data


_cache_warmers_started = False
_balance_warm_offset = 0


def _warm_balance_cache_batch():
    """Warm balance cache for a batch of users."""
    global _balance_warm_offset
    batch_size = int(os.environ.get('BALANCE_WARMER_BATCH', '50'))
    
    with app.app_context():
        users = User.query.filter(
            User.role == 'user',
            User.is_active == True
        ).order_by(User.id.asc()).offset(_balance_warm_offset).limit(batch_size).all()
    
    if not users:
        _balance_warm_offset = 0
        return
    
    for user in users:
        _refresh_balance_cache(user.id)
    
    _balance_warm_offset += len(users)


def _warm_public_leaderboards():
    """Warm public leaderboard caches."""
    with app.app_context():
        get_public_stats_cached('leaderboard_stats', _compute_leaderboard_stats, allow_stale=False)
        get_public_stats_cached('gamification_leaderboard:10', lambda: _compute_gamification_leaderboard(10), allow_stale=False)


def _cache_warmer_loop():
    """Background loop to warm caches periodically."""
    interval = int(os.environ.get('CACHE_WARMER_INTERVAL', '120'))
    while True:
        try:
            _warm_balance_cache_batch()
            _warm_public_leaderboards()
        except Exception as e:
            logger.warning(f"Cache warmer error: {e}")
        time.sleep(interval)


def start_cache_warmers():
    """Start background cache warmers if enabled."""
    global _cache_warmers_started
    if _cache_warmers_started:
        return
    if os.environ.get('DISABLE_CACHE_WARMERS', 'false').lower() == 'true':
        return
    if os.environ.get('ENABLE_CACHE_WARMERS', 'true').lower() != 'true':
        return
    
    _cache_warmers_started = True
    threading.Thread(target=_cache_warmer_loop, daemon=True).start()


def _fetch_user_exchange_balances(user_id: int) -> dict:
    """
    Fetch balances from all connected exchanges for a user using CCXT
    
    Returns:
        dict: {
            'total': float or None,  # Total balance across all exchanges
            'exchanges': [
                {
                    'id': int,
                    'exchange_name': str,
                    'label': str,
                    'balance': float or None,
                    'status': str,
                    'error': str or None
                }
            ]
        }
    """
    import ccxt
    from models import UserExchange
    
    result = {
        'total': 0.0,
        'exchanges': []
    }
    
    # Get all approved/active exchanges for this user
    user_exchanges = UserExchange.query.filter(
        UserExchange.user_id == user_id,
        UserExchange.status.in_(['APPROVED', 'PENDING'])
    ).all()
    
    if not user_exchanges:
        return result
    
    for ue in user_exchanges:
        exchange_info = {
            'id': ue.id,
            'exchange_name': ue.exchange_name,
            'label': ue.label or ue.exchange_name,
            'balance': None,
            'status': ue.status,
            'trading_enabled': ue.trading_enabled,
            'error': None
        }
        
        # Only fetch balance if exchange is approved and has valid credentials
        if ue.status == 'APPROVED' and ue.api_key and ue.api_secret:
            try:
                # Get the CCXT exchange class
                exchange_class_name = ue.exchange_name.lower()
                
                # Map to CCXT class names (import from service_validator for consistency)
                from service_validator import SUPPORTED_EXCHANGES
                ccxt_mapping = SUPPORTED_EXCHANGES
                
                ccxt_class = ccxt_mapping.get(exchange_class_name, exchange_class_name)
                
                if hasattr(ccxt, ccxt_class):
                    exchange_class = getattr(ccxt, ccxt_class)
                    
                    # Configure exchange
                    config = {
                        'apiKey': ue.api_key,
                        'secret': ue.get_api_secret(),
                        'enableRateLimit': True,
                        'options': {
                            'defaultType': 'future',
                        }
                    }
                    
                    # Add passphrase if required
                    passphrase = ue.get_passphrase()
                    if passphrase:
                        config['password'] = passphrase
                    
                    exchange = exchange_class(config)
                    
                    # Fetch balance
                    balance = exchange.fetch_balance()
                    
                    # Try to get USDT balance (most common for futures)
                    usdt_balance = None
                    if 'USDT' in balance and isinstance(balance['USDT'], dict):
                        usdt_balance = balance['USDT'].get('total') or balance['USDT'].get('free', 0)
                    elif 'total' in balance and 'USDT' in balance['total']:
                        usdt_balance = balance['total']['USDT']
                    elif 'free' in balance and 'USDT' in balance['free']:
                        usdt_balance = balance['free']['USDT']
                    
                    if usdt_balance is not None:
                        exchange_info['balance'] = float(usdt_balance)
                        result['total'] += float(usdt_balance)
                    else:
                        # Try to find any stablecoin balance
                        for coin in ['USDT', 'USDC', 'BUSD', 'USD']:
                            if coin in balance:
                                if isinstance(balance[coin], dict):
                                    val = balance[coin].get('total') or balance[coin].get('free', 0)
                                else:
                                    val = balance[coin]
                                if val and float(val) > 0:
                                    exchange_info['balance'] = float(val)
                                    result['total'] += float(val)
                                    break
                else:
                    exchange_info['error'] = f"Exchange {ccxt_class} not supported"
                    
            except ccxt.AuthenticationError as e:
                exchange_info['error'] = "Authentication failed"
                logger.warning(f"Auth error fetching balance for user {user_id} on {ue.exchange_name}: {e}")
            except ccxt.NetworkError as e:
                exchange_info['error'] = "Network error"
                logger.warning(f"Network error fetching balance for user {user_id} on {ue.exchange_name}: {e}")
            except Exception as e:
                exchange_info['error'] = str(e)[:50]
                logger.warning(f"Error fetching balance for user {user_id} on {ue.exchange_name}: {e}")
        
        result['exchanges'].append(exchange_info)
    
    return result


def _refresh_balance_cache(user_id: int) -> None:
    """Refresh cached balances asynchronously."""
    try:
        with app.app_context():
            data = _fetch_user_exchange_balances(user_id)
        with _balance_cache_lock:
            _balance_cache[user_id] = {
                'data': data,
                'ts': time.time()
            }
        _set_balance_cache_to_redis(user_id, data)
    finally:
        with _balance_cache_lock:
            _balance_cache_inflight.discard(user_id)


def get_user_exchange_balances(user_id: int, allow_stale: bool = True) -> dict:
    """
    Get cached balances for user exchanges with async refresh.
    
    Args:
        user_id: User ID
        allow_stale: Return stale cache while refreshing in background
    """
    # Prefer Redis cache if available (persists across restarts)
    redis_cached = _get_balance_cache_from_redis(user_id)
    if redis_cached:
        return redis_cached
    
    now = time.time()
    with _balance_cache_lock:
        cached = _balance_cache.get(user_id)
    
    if cached:
        age = now - cached['ts']
        if age <= _balance_cache_ttl:
            return cached['data']
        if allow_stale:
            with _balance_cache_lock:
                if user_id not in _balance_cache_inflight:
                    _balance_cache_inflight.add(user_id)
                    threading.Thread(
                        target=_refresh_balance_cache,
                        args=(user_id,),
                        daemon=True
                    ).start()
            return cached['data']
    
    # No cache or stale not allowed: refresh synchronously
    data = _fetch_user_exchange_balances(user_id)
    with _balance_cache_lock:
        _balance_cache[user_id] = {'data': data, 'ts': now}
    _set_balance_cache_to_redis(user_id, data)
    return data


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ==================== SECURITY MIDDLEWARE ====================

@app.before_request
def security_checks():
    """Run security checks before each request"""
    ip = get_client_ip()
    
    # Check if IP is blocked
    if login_tracker.is_blocked(ip):
        logger.warning(f"Blocked IP attempted access: {ip}")
        abort(403)
    
    # Store IP in g for later use
    g.client_ip = ip
    
    # Enforce admin access for admin routes
    path = request.path or ''
    is_admin_api = path.startswith('/api/admin')
    if path.startswith('/admin') or is_admin_api:
        if not current_user.is_authenticated:
            if is_admin_api:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            abort(401)
        if not verify_session():
            if is_admin_api:
                return jsonify({'success': False, 'error': 'Invalid session'}), 401
            abort(401)
        if current_user.role != 'admin':
            if is_admin_api:
                return jsonify({'success': False, 'error': 'Admin access required'}), 403
            abort(403)
    
    # Global rate limiting for public API endpoints
    if path.startswith('/api'):
        try:
            max_requests = int(os.environ.get('API_RATE_LIMIT', '120'))
            window = int(os.environ.get('API_RATE_LIMIT_WINDOW', '60'))
        except ValueError:
            max_requests = 120
            window = 60
        if not api_limiter.check(f"api_{ip}", max_requests, window):
            return jsonify({
                'success': False,
                'error': 'Rate limit exceeded',
                'retry_after': window
            }), 429
    
    # Check for injection attempts in request data (query, form, JSON)
    for key, value in request.args.items():
        if isinstance(value, str) and InputValidator.check_injection(value):
            audit.log_security_event("INJECTION_ATTEMPT", f"IP: {ip}, Field: {key}", "CRITICAL")
            login_tracker.block_ip(ip)
            abort(403)
    
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        if request.is_json:
            payload = request.get_json(silent=True)
            raw_body = request.get_data(cache=True)
            if raw_body and payload is None:
                audit.log_security_event("INVALID_JSON", f"IP: {ip}, Error: Malformed JSON", "WARNING")
                return jsonify({'success': False, 'error': 'Invalid input'}), 400
            is_valid, error_msg = validate_json_payload(payload)
            if not is_valid:
                audit.log_security_event("INVALID_JSON", f"IP: {ip}, Error: {error_msg}", "WARNING")
                return jsonify({'success': False, 'error': 'Invalid input'}), 400
        for key, value in request.form.items():
            if isinstance(value, str) and InputValidator.check_injection(value):
                audit.log_security_event("INJECTION_ATTEMPT", f"IP: {ip}, Field: {key}", "CRITICAL")
                login_tracker.block_ip(ip)
                abort(403)


@app.after_request
def apply_security_headers(response):
    """Add security headers to all responses"""
    return add_security_headers(response)


def _is_api_request() -> bool:
    """Determine if request expects JSON response."""
    path = request.path or ''
    if path.startswith('/api'):
        return True
    if request.accept_mimetypes and request.accept_mimetypes.best == 'application/json':
        return True
    return False


def _json_error_response(message: str, code: int):
    """Return a structured JSON error response."""
    return jsonify({
        'success': False,
        'error': message,
        'code': str(code)
    }), code


@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Return JSON errors for API endpoints, HTML for others."""
    if _is_api_request():
        return _json_error_response(e.description, e.code)
    return e


@app.errorhandler(Exception)
def handle_exception(e):
    """Catch-all handler for API errors."""
    if _is_api_request():
        logger.error("Unhandled API error", exc_info=True)
        return _json_error_response("Internal server error", 500)
    return app.handle_exception(e)


@app.context_processor
def inject_csrf_token():
    """Inject CSRF token into templates"""
    return {'csrf_token': generate_csrf_token}


# ==================== SOCKET EVENTS ====================

def _socket_is_connected(sid: str, namespace: str = "/") -> bool:
    """Check if a SocketIO client is still connected."""
    try:
        if not socketio.server or not socketio.server.manager:
            return False
        return socketio.server.manager.is_connected(sid, namespace)
    except Exception:
        return False


@socketio.on('connect')
def handle_connect(auth=None):
    try:
        if not _socket_is_connected(request.sid):
            logger.debug("Connect handler called for stale socket session")
            return
        if current_user.is_authenticated:
            room = f"user_{current_user.id}"
            join_room(room)
            logger.info(f"🔌 Client connected: {current_user.username}")
            
            if current_user.role == 'admin':
                join_room("admin_room")
                if engine.master_client:
                    engine.push_update('master', engine.master_client, is_master=True)
                for slave in engine.slave_clients:
                    engine.push_update(slave['id'], slave['client'])
            else:
                slave = next((s for s in engine.slave_clients if s['id'] == current_user.id), None)
                if slave:
                    engine.push_update(slave['id'], slave['client'])
                else:
                    try:
                        socketio.emit('update_data', {'balance': "0.00", 'positions': []}, room=room)
                    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                            urllib3.exceptions.ProtocolError):
                        # Client disconnected - expected behavior, silently ignore
                        pass
    except KeyError as e:
        # Race condition: client disconnected before join_room completed
        # This is expected when clients rapidly connect/disconnect
        logger.debug(f"Client disconnected during connect handler: {e}")


# ==================== LIVE CHAT SOCKET EVENTS ====================

@socketio.on('join_chat')
def handle_join_chat(data):
    """Handle user joining a chat room"""
    from flask_socketio import join_room as socket_join_room
    from models import ChatBan, ChatMessage
    
    if not current_user.is_authenticated:
        emit('chat_error', {'message': 'Увійдіть, щоб отримати доступ до чату'})
        return
    
    room = data.get('room', 'general')
    
    # Chat is available to all logged-in users (no subscription required)
    
    # Check if user is banned
    is_banned, ban_type, reason, expires_at = ChatBan.is_user_banned(current_user.id)
    if is_banned:
        emit('chat_error', {
            'message': f'You are {ban_type}ed from chat' + (f': {reason}' if reason else ''),
            'ban_type': ban_type,
            'expires_at': expires_at.isoformat() if expires_at else None
        })
        return
    
    try:
        # Join the chat room
        if not _socket_is_connected(request.sid):
            logger.debug("Chat join skipped for stale socket session")
            return
        socket_join_room(f'chat_{room}')
        logger.info(f"💬 {current_user.username} joined chat room: {room}")
        
        # Get recent messages
        messages = ChatMessage.get_recent_messages(room, limit=50)
        messages_data = [msg.to_dict() for msg in reversed(messages)]  # Oldest first
        
        emit('chat_joined', {
            'room': room,
            'messages': messages_data,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'avatar': current_user.avatar,
                'avatar_type': current_user.avatar_type,
                'is_admin': current_user.role == 'admin'
            }
        })
        
        # Notify room that user joined
        emit('user_joined', {
            'username': current_user.username,
            'avatar': current_user.avatar,
            'user_id': current_user.id
        }, room=f'chat_{room}', include_self=False)
    except KeyError as e:
        # Client disconnected before join_room completed
        logger.debug(f"Client disconnected during chat join: {e}")


@socketio.on('leave_chat')
def handle_leave_chat(data):
    """Handle user leaving a chat room"""
    from flask_socketio import leave_room as socket_leave_room
    
    if not current_user.is_authenticated:
        return
    
    room = data.get('room', 'general')
    try:
        socket_leave_room(f'chat_{room}')
    except KeyError as e:
        logger.debug(f"Client disconnected during chat leave: {e}")
    
    emit('user_left', {
        'username': current_user.username,
        'user_id': current_user.id
    }, room=f'chat_{room}', include_self=False)


@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a chat message"""
    from models import ChatBan, ChatMessage
    
    if not current_user.is_authenticated:
        emit('chat_error', {'message': 'Увійдіть, щоб надсилати повідомлення'})
        return
    
    room = data.get('room', 'general')
    message_text = data.get('message', '').strip()
    
    # Validate message
    if not message_text:
        return
    
    if len(message_text) > 500:
        emit('chat_error', {'message': 'Повідомлення занадто довге (макс. 500 символів)'})
        return
    
    # Chat is available to all logged-in users (no subscription required)
    
    # Check if user is banned/muted
    is_banned, ban_type, reason, expires_at = ChatBan.is_user_banned(current_user.id)
    if is_banned:
        emit('chat_error', {
            'message': f'You are {ban_type}ed' + (f': {reason}' if reason else ''),
            'ban_type': ban_type,
            'expires_at': expires_at.isoformat() if expires_at else None
        })
        return
    
    # Sanitize message (basic XSS prevention)
    message_text = message_text.replace('<', '&lt;').replace('>', '&gt;')
    
    # Save message to database
    chat_msg = ChatMessage(
        user_id=current_user.id,
        room=room,
        message=message_text,
        message_type='admin' if current_user.role == 'admin' else 'user'
    )
    db.session.add(chat_msg)
    db.session.commit()
    
    # Broadcast message to room
    emit('new_message', chat_msg.to_dict(), room=f'chat_{room}')


@socketio.on('delete_message')
def handle_delete_message(data):
    """Handle admin deleting a message"""
    from models import ChatMessage
    
    if not current_user.is_authenticated:
        return
    
    if current_user.role != 'admin':
        emit('chat_error', {'message': 'Потрібен доступ адміністратора'})
        return
    
    message_id = data.get('message_id')
    room = data.get('room', 'general')
    
    if not message_id:
        return
    
    message = ChatMessage.query.get(message_id)
    if message:
        message.is_deleted = True
        message.deleted_by_id = current_user.id
        db.session.commit()
        
        emit('message_deleted', {'message_id': message_id}, room=f'chat_{room}')


def broadcast_whale_alert(user_id: int, username: str, symbol: str, pnl: float, room: str = 'general'):
    """
    Broadcast a whale alert to the chat when a user makes a large profit.
    Called from the trading engine when a trade closes.
    """
    from models import ChatMessage, User
    
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
                'pnl': pnl
            }
        )
        db.session.add(chat_msg)
        db.session.commit()
        
        # Broadcast to chat room
        try:
            socketio.emit('new_message', chat_msg.to_dict(), room=f'chat_{room}')
            socketio.emit('whale_alert', {
                'masked_username': masked_name,
                'symbol': symbol,
                'pnl': pnl,
                'message': alert_message
            }, room=f'chat_{room}')
        except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
                urllib3.exceptions.ProtocolError):
            # Client disconnected - expected behavior, silently ignore
            pass


# ==================== SEO ROUTES ====================

@app.route('/manifest.json')
def manifest_json():
    """Serve PWA manifest"""
    return send_from_directory(app.static_folder, 'manifest.json', mimetype='application/json')

@app.route('/service-worker.js')
def service_worker():
    """Serve service worker from root for proper scope"""
    response = send_from_directory(app.static_folder, 'service-worker.js', mimetype='application/javascript')
    # Allow service worker to control the whole site
    response.headers['Service-Worker-Allowed'] = '/'
    return response


# ==================== ROUTES ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/faq')
def faq_page():
    """
    Public FAQ page accessible to all users.
    Renders FAQ.md content as HTML.
    """
    import os
    import re
    
    faq_path = os.path.join(os.path.dirname(__file__), 'FAQ.md')
    
    try:
        with open(faq_path, 'r', encoding='utf-8') as f:
            faq_content = f.read()
        
        # Simple markdown to HTML conversion
        def md_to_html(text):
            # Headers
            text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
            text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
            text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
            
            # Bold
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            
            # Inline code
            text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
            
            # Lists
            text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
            text = re.sub(r'(<li>.+</li>\n?)+', r'<ul>\g<0></ul>', text)
            
            # Code blocks
            text = re.sub(r'```(\w+)?\n(.+?)\n```', r'<pre><code>\2</code></pre>', text, flags=re.DOTALL)
            
            # Horizontal rules
            text = re.sub(r'^---$', r'<hr>', text, flags=re.MULTILINE)
            
            # Links
            text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" target="_blank">\1</a>', text)
            
            # Tables (simple)
            def convert_table(match):
                lines = match.group(0).strip().split('\n')
                html = '<table class="faq-table">'
                for i, line in enumerate(lines):
                    if '---' in line:
                        continue
                    cells = [c.strip() for c in line.split('|') if c.strip()]
                    tag = 'th' if i == 0 else 'td'
                    html += f'<tr>{"".join(f"<{tag}>{c}</{tag}>" for c in cells)}</tr>'
                html += '</table>'
                return html
            
            text = re.sub(r'(\|.+\|\n)+', convert_table, text)
            
            # Paragraphs
            paragraphs = text.split('\n\n')
            for i, p in enumerate(paragraphs):
                if not any(p.startswith(tag) for tag in ['<h', '<ul', '<pre', '<hr', '<table']):
                    paragraphs[i] = f'<p>{p}</p>' if p.strip() else ''
            text = '\n'.join(paragraphs)
            
            return text
        
        faq_html = md_to_html(faq_content)
        
        return render_template('faq.html', faq_content=faq_html)
        
    except FileNotFoundError:
        return render_template('faq.html', faq_content='<p>Вміст FAQ не знайдено.</p>')


# ==================== DYNAMIC SITEMAP ====================

@app.route('/sitemap.xml')
def sitemap():
    """
    Generate dynamic sitemap.xml for SEO.
    Lists all public pages with proper priorities and change frequencies.
    """
    from datetime import datetime
    
    # Base URL from config or default
    base_url = os.environ.get('SITE_URL', 'https://mimic.cash')
    
    # Current timestamp for lastmod
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    # Define public pages with their SEO attributes
    # Format: (path, changefreq, priority)
    public_pages = [
        ('/', 'weekly', '1.0'),          # Homepage - highest priority
        ('/leaderboard', 'hourly', '0.95'),  # Leaderboard - frequently updated
        ('/faq', 'weekly', '0.9'),       # FAQ - important for users
        ('/register', 'monthly', '0.9'),  # Registration - important for conversions
        ('/login', 'monthly', '0.8'),     # Login
        ('/forgot_password', 'yearly', '0.3'),  # Password reset - rarely changed
    ]
    
    # Build XML
    xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"')
    xml_content.append('        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">')
    
    for path, changefreq, priority in public_pages:
        xml_content.append('  <url>')
        xml_content.append(f'    <loc>{base_url}{path}</loc>')
        xml_content.append(f'    <lastmod>{now}</lastmod>')
        xml_content.append(f'    <changefreq>{changefreq}</changefreq>')
        xml_content.append(f'    <priority>{priority}</priority>')
        
        # Add image for homepage
        if path == '/':
            xml_content.append('    <image:image>')
            xml_content.append(f'      <image:loc>{base_url}/static/mimic-logo.svg</image:loc>')
            xml_content.append('      <image:title>MIMIC Copy Trading Logo</image:title>')
            xml_content.append('      <image:caption>MIMIC - Automated Crypto Copy Trading Platform</image:caption>')
            xml_content.append('    </image:image>')
        
        xml_content.append('  </url>')
    
    xml_content.append('</urlset>')
    
    return Response(
        '\n'.join(xml_content),
        mimetype='application/xml',
        headers={'Cache-Control': 'public, max-age=3600'}  # Cache for 1 hour
    )


@app.route('/robots.txt')
def robots():
    """Serve robots.txt with dynamic sitemap URL"""
    base_url = os.environ.get('SITE_URL', 'https://mimic.cash')
    robots_content = f"""User-agent: *
Allow: /
Allow: /leaderboard
Allow: /login
Allow: /register
Disallow: /dashboard
Disallow: /api/
Disallow: /admin/
Disallow: /webhook/

# Sitemap
Sitemap: {base_url}/sitemap.xml

# Crawl-delay for politeness
Crawl-delay: 1
"""
    return Response(robots_content, mimetype='text/plain')


# ==================== PUBLIC LEADERBOARD ====================

def _compute_leaderboard_stats() -> dict:
    """Compute leaderboard stats payload."""
    # Calculate time periods
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    last_7_days = datetime.now(timezone.utc) - timedelta(days=7)
    last_30_days = datetime.now(timezone.utc) - timedelta(days=30)
    
    # ===== GLOBAL STATS =====
    total_users = User.query.filter(User.role == 'user').count()
    active_users = User.query.filter(User.role == 'user', User.is_active == True).count()
    
    total_profit = db.session.query(db.func.sum(TradeHistory.pnl)).filter(
        TradeHistory.pnl > 0
    ).scalar() or 0
    
    total_volume = db.session.query(db.func.sum(db.func.abs(TradeHistory.pnl))).scalar() or 0
    total_volume = total_volume * 15  # Assume average 15x leverage
    
    total_trades = TradeHistory.query.count()
    
    # ===== TOP COPIERS TODAY (by ROE%) =====
    top_copiers_query = db.session.query(
        TradeHistory.user_id,
        db.func.sum(TradeHistory.pnl).label('total_pnl'),
        db.func.avg(TradeHistory.roi).label('avg_roe'),
        db.func.count(TradeHistory.id).label('trade_count')
    ).filter(
        TradeHistory.user_id.isnot(None),
        TradeHistory.close_time >= today
    ).group_by(
        TradeHistory.user_id
    ).order_by(
        db.func.sum(TradeHistory.pnl).desc()
    ).limit(10).all()
    
    top_copiers = []
    for row in top_copiers_query:
        user = db.session.get(User, row.user_id)
        if user:
            username = user.username
            if len(username) > 2:
                masked = f"User {username[0]}***{username[-1]}"
            else:
                masked = f"User {username[0]}***"
            
            top_copiers.append({
                'masked_name': masked,
                'roe': round(float(row.avg_roe or 0), 2),
                'pnl': round(float(row.total_pnl or 0), 2),
                'trades': int(row.trade_count)
            })
    
    if not top_copiers:
        top_copiers_query = db.session.query(
            TradeHistory.user_id,
            db.func.sum(TradeHistory.pnl).label('total_pnl'),
            db.func.avg(TradeHistory.roi).label('avg_roe'),
            db.func.count(TradeHistory.id).label('trade_count')
        ).filter(
            TradeHistory.user_id.isnot(None),
            TradeHistory.close_time >= last_7_days
        ).group_by(
            TradeHistory.user_id
        ).order_by(
            db.func.sum(TradeHistory.pnl).desc()
        ).limit(10).all()
        
        for row in top_copiers_query:
            user = db.session.get(User, row.user_id)
            if user:
                username = user.username
                if len(username) > 2:
                    masked = f"User {username[0]}***{username[-1]}"
                else:
                    masked = f"User {username[0]}***"
                
                top_copiers.append({
                    'masked_name': masked,
                    'roe': round(float(row.avg_roe or 0), 2),
                    'pnl': round(float(row.total_pnl or 0), 2),
                    'trades': int(row.trade_count)
                })
    
    # ===== MASTER TRADER STATS =====
    master_trades_30d = TradeHistory.query.filter(
        TradeHistory.user_id == None,
        TradeHistory.close_time >= last_30_days
    ).all()
    
    master_pnl = sum(t.pnl for t in master_trades_30d) if master_trades_30d else 0
    master_trades_count = len(master_trades_30d)
    master_winning = len([t for t in master_trades_30d if t.pnl > 0])
    master_winrate = (master_winning / master_trades_count * 100) if master_trades_count > 0 else 0
    master_avg_roi = sum(t.roi for t in master_trades_30d) / len(master_trades_30d) if master_trades_30d else 0
    
    master_balance_history = BalanceHistory.query.filter(
        BalanceHistory.user_id == None,
        BalanceHistory.timestamp >= last_30_days
    ).order_by(BalanceHistory.timestamp.asc()).all()
    
    balance_chart_data = [{
        'time': h.timestamp.strftime('%d/%m'),
        'balance': round(h.balance, 2)
    } for h in master_balance_history]
    
    master_roe = 0
    if master_balance_history and len(master_balance_history) >= 2:
        start_balance = master_balance_history[0].balance
        end_balance = master_balance_history[-1].balance
        if start_balance > 0:
            master_roe = ((end_balance - start_balance) / start_balance) * 100
    
    return {
        'success': True,
        'global_stats': {
            'total_users': total_users,
            'active_users': active_users,
            'total_profit': round(float(total_profit), 2),
            'total_volume': round(float(total_volume), 2),
            'total_trades': total_trades
        },
        'top_copiers': top_copiers,
        'master_stats': {
            'pnl_30d': round(float(master_pnl), 2),
            'trades_30d': master_trades_count,
            'winrate': round(float(master_winrate), 1),
            'avg_roi': round(float(master_avg_roi), 2),
            'roe_30d': round(float(master_roe), 2)
        },
        'balance_chart': balance_chart_data,
        'generated_at': datetime.now(timezone.utc).isoformat()
    }


def _compute_gamification_leaderboard(limit: int) -> dict:
    """Compute gamification leaderboard payload."""
    top_users = User.query.filter(
        User.role == 'user',
        User.xp > 0
    ).order_by(User.xp.desc()).limit(limit).all()
    
    leaderboard = []
    for i, user in enumerate(top_users, 1):
        leaderboard.append({
            'rank': i,
            'username': user.username[:3] + '*' * max(0, len(user.username) - 4) + user.username[-1:] if len(user.username) > 4 else user.username,
            'avatar': user.avatar,
            'avatar_type': user.avatar_type,
            'xp': user.xp or 0,
            'level_name': user.current_level.name if user.current_level else 'Novice',
            'level_icon': user.current_level.icon if user.current_level else 'fa-seedling',
            'level_color': user.current_level.color if user.current_level else '#888888',
            'badge_count': user.achievements.count()
        })
    
    return {
        'success': True,
        'leaderboard': leaderboard,
        'total_participants': User.query.filter(User.role == 'user', User.xp > 0).count()
    }


@app.route('/leaderboard')
def leaderboard():
    """Public leaderboard page - SEO optimized landing page showing trading stats"""
    return render_template('leaderboard.html')


@app.route('/api/leaderboard/stats')
def get_leaderboard_stats():
    """Public API endpoint for leaderboard statistics - no auth required"""
    try:
        data = get_public_stats_cached('leaderboard_stats', _compute_leaderboard_stats)
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"Error getting leaderboard stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося завантажити дані лідерборду'
        }), 500


# ==================== TOURNAMENT SYSTEM ====================

@app.route('/tournament')
def tournament_page():
    """
    Public tournament page showing:
    - Active tournament with countdown timer
    - Real-time leaderboard
    - Registration form for logged-in users
    - Prize pool and distribution info
    """
    return render_template('tournament.html')


@app.route('/api/tournament/active')
def get_active_tournament():
    """
    Get the currently active tournament with leaderboard.
    
    Public API endpoint - no auth required for viewing.
    """
    try:
        from models import Tournament
        
        # Get active tournament
        tournament = Tournament.get_active_tournament()
        
        if not tournament:
            # Check for upcoming tournament
            upcoming = Tournament.get_upcoming_tournaments(limit=1)
            if upcoming:
                return jsonify({
                    'success': True,
                    'tournament': upcoming[0].to_dict(include_leaderboard=False),
                    'status': 'upcoming',
                    'message': 'Tournament starting soon!'
                })
            return jsonify({
                'success': True,
                'tournament': None,
                'status': 'none',
                'message': 'Немає активного турніру. Повертайся пізніше!'
            })
        
        return jsonify({
            'success': True,
            'tournament': tournament.to_dict(include_leaderboard=True),
            'status': 'active'
        })
        
    except Exception as e:
        logger.error(f"Error getting active tournament: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося завантажити дані турніру'
        }), 500


@app.route('/api/tournament/<int:tournament_id>')
def get_tournament_by_id(tournament_id):
    """
    Get a specific tournament by ID.
    
    Public API endpoint.
    """
    try:
        from models import Tournament
        
        tournament = Tournament.query.get(tournament_id)
        
        if not tournament:
            return jsonify({
                'success': False,
                'error': 'Турнір не знайдено'
            }), 404
        
        return jsonify({
            'success': True,
            'tournament': tournament.to_dict(include_leaderboard=True)
        })
        
    except Exception as e:
        logger.error(f"Error getting tournament {tournament_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося завантажити дані турніру'
        }), 500


@app.route('/api/tournament/<int:tournament_id>/leaderboard')
def get_tournament_leaderboard(tournament_id):
    """
    Get the leaderboard for a specific tournament.
    
    Public API endpoint - refreshes automatically via JS.
    """
    try:
        from models import Tournament
        
        tournament = Tournament.query.get(tournament_id)
        
        if not tournament:
            return jsonify({
                'success': False,
                'error': 'Турнір не знайдено'
            }), 404
        
        return jsonify({
            'success': True,
            'tournament_id': tournament_id,
            'tournament_name': tournament.name,
            'status': tournament.status,
            'prize_pool': tournament.prize_pool,
            'time_remaining': tournament.get_time_remaining(),
            'leaderboard': tournament.get_leaderboard(limit=50),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting tournament leaderboard: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося завантажити лідерборд'
        }), 500


@app.route('/api/tournament/join', methods=['POST'])
@login_required
def join_tournament():
    """
    Join the active tournament.
    
    Requires authentication. Deducts entry fee from user's balance.
    """
    try:
        from models import Tournament, TournamentParticipant
        
        # Get active or upcoming tournament
        tournament = Tournament.get_active_tournament()
        if not tournament:
            upcoming = Tournament.get_upcoming_tournaments(limit=1)
            if upcoming:
                tournament = upcoming[0]
            else:
                return jsonify({
                    'success': False,
                    'error': 'Немає доступного турніру для приєднання'
                }), 400
        
        # Check if registration is open
        if not tournament.is_registration_open():
            return jsonify({
                'success': False,
                'error': 'Реєстрація закрита для цього турніру'
            }), 400
        
        # Check if user already joined
        existing = TournamentParticipant.query.filter_by(
            tournament_id=tournament.id,
            user_id=current_user.id
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': 'Ти вже приєднався до цього турніру'
            }), 400
        
        # Add participant
        try:
            participant = tournament.add_participant(current_user.id)
            
            return jsonify({
                'success': True,
                'message': f'Successfully joined {tournament.name}!',
                'tournament': tournament.to_dict(),
                'participant': participant.to_dict()
            })
            
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        
    except Exception as e:
        logger.error(f"Error joining tournament: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося приєднатися до турніру'
        }), 500


@app.route('/api/tournament/my-participation')
@login_required
def get_my_tournament_participation():
    """
    Get current user's tournament participation status.
    """
    try:
        from models import Tournament, TournamentParticipant
        
        # Get active tournament
        tournament = Tournament.get_active_tournament()
        
        if not tournament:
            # Check upcoming
            upcoming = Tournament.get_upcoming_tournaments(limit=1)
            if upcoming:
                tournament = upcoming[0]
            else:
                return jsonify({
                    'success': True,
                    'participating': False,
                    'tournament': None,
                    'message': 'Немає активного турніру'
                })
        
        # Check if user is participating
        participant = TournamentParticipant.query.filter_by(
            tournament_id=tournament.id,
            user_id=current_user.id
        ).first()
        
        if participant:
            # Get user's current rank
            rank = TournamentParticipant.query.filter(
                TournamentParticipant.tournament_id == tournament.id,
                TournamentParticipant.current_roi > participant.current_roi
            ).count() + 1
            
            return jsonify({
                'success': True,
                'participating': True,
                'tournament': tournament.to_dict(),
                'participation': {
                    **participant.to_dict(),
                    'current_rank': rank,
                    'total_participants': tournament.participants.count()
                }
            })
        else:
            return jsonify({
                'success': True,
                'participating': False,
                'tournament': tournament.to_dict(),
                'can_join': tournament.is_registration_open()
            })
        
    except Exception as e:
        logger.error(f"Error getting tournament participation: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося завантажити дані участі'
        }), 500


@app.route('/api/tournament/history')
def get_tournament_history():
    """
    Get list of past tournaments with winners.
    
    Public API endpoint.
    """
    try:
        from models import Tournament
        
        # Get completed tournaments
        completed = Tournament.query.filter_by(status='completed').order_by(
            Tournament.finalized_at.desc()
        ).limit(10).all()
        
        return jsonify({
            'success': True,
            'tournaments': [t.to_dict() for t in completed]
        })
        
    except Exception as e:
        logger.error(f"Error getting tournament history: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося завантажити історію турнірів'
        }), 500


# Admin endpoints for tournament management

@app.route('/api/admin/tournament/create', methods=['POST'])
@login_required
def admin_create_tournament():
    """
    Create a new tournament (admin only).
    """
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Tournament
        
        data = request.get_json()
        
        name = data.get('name', 'Weekly Championship')
        entry_fee = float(data.get('entry_fee', 10.0))
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            # Custom dates provided
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            tournament = Tournament(
                name=name,
                description=f"Entry: ${entry_fee}. Prizes: 50%/30%/20% for TOP-3.",
                start_date=start,
                end_date=end,
                entry_fee=entry_fee,
                status='upcoming'
            )
            db.session.add(tournament)
            db.session.commit()
        else:
            # Create weekly tournament
            tournament = Tournament.create_weekly_tournament(
                name=name,
                entry_fee=entry_fee
            )
        
        logger.info(f"Admin created tournament: {tournament.name}")
        
        return jsonify({
            'success': True,
            'message': f'Tournament "{tournament.name}" created successfully',
            'tournament': tournament.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error creating tournament: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/tournament/<int:tournament_id>/cancel', methods=['POST'])
@login_required
def admin_cancel_tournament(tournament_id):
    """
    Cancel a tournament (admin only).
    """
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Tournament
        
        tournament = Tournament.query.get(tournament_id)
        
        if not tournament:
            return jsonify({
                'success': False,
                'error': 'Турнір не знайдено'
            }), 404
        
        if tournament.status == 'completed':
            return jsonify({
                'success': False,
                'error': 'Неможливо скасувати завершений турнір'
            }), 400
        
        tournament.status = 'cancelled'
        db.session.commit()
        
        logger.info(f"Admin cancelled tournament: {tournament.name}")
        
        return jsonify({
            'success': True,
            'message': f'Tournament "{tournament.name}" cancelled'
        })
        
    except Exception as e:
        logger.error(f"Error cancelling tournament: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== TASK/CHALLENGE SYSTEM ====================

@app.route('/api/tasks')
def get_tasks():
    """
    Get all active tasks available for participation.
    
    Query params:
    - type: Filter by task type (social, trading, referral, community, custom)
    - featured: true/false - only show featured tasks
    """
    try:
        from models import Task
        
        task_type = request.args.get('type')
        featured_only = request.args.get('featured', '').lower() == 'true'
        
        tasks = Task.get_active_tasks(task_type=task_type, featured_only=featured_only)
        
        # Add user participation status if logged in
        tasks_data = []
        for task in tasks:
            task_dict = task.to_dict()
            
            if current_user.is_authenticated:
                from models import TaskParticipation
                participation = TaskParticipation.query.filter_by(
                    task_id=task.id,
                    user_id=current_user.id
                ).order_by(TaskParticipation.joined_at.desc()).first()
                
                task_dict['user_participation'] = participation.to_dict() if participation else None
                can_participate, reason = task.can_user_participate(current_user)
                task_dict['can_participate'] = can_participate
                task_dict['participation_reason'] = reason
            
            tasks_data.append(task_dict)
        
        return jsonify({
            'success': True,
            'tasks': tasks_data,
            'task_types': Task.get_task_types(),
            'reward_types': Task.get_reward_types()
        })
        
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>')
def get_task(task_id):
    """Get a specific task by ID"""
    try:
        from models import Task, TaskParticipation
        
        task = Task.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Завдання не знайдено'}), 404
        
        task_dict = task.to_dict()
        
        if current_user.is_authenticated:
            participation = TaskParticipation.query.filter_by(
                task_id=task.id,
                user_id=current_user.id
            ).order_by(TaskParticipation.joined_at.desc()).first()
            
            task_dict['user_participation'] = participation.to_dict() if participation else None
            can_participate, reason = task.can_user_participate(current_user)
            task_dict['can_participate'] = can_participate
            task_dict['participation_reason'] = reason
        
        return jsonify({'success': True, 'task': task_dict})
        
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/join', methods=['POST'])
@login_required
def join_task(task_id):
    """Join a task/challenge"""
    try:
        from models import Task, TaskParticipation
        
        task = Task.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Завдання не знайдено'}), 404
        
        can_participate, reason = task.can_user_participate(current_user)
        if not can_participate:
            return jsonify({'success': False, 'error': reason}), 400
        
        # Create participation
        participation = TaskParticipation(
            task_id=task_id,
            user_id=current_user.id,
            status='in_progress'
        )
        db.session.add(participation)
        
        # Update task stats
        task.total_participants += 1
        
        db.session.commit()
        
        logger.info(f"User {current_user.username} joined task: {task.title}")
        
        return jsonify({
            'success': True,
            'message': f'You joined the task: {task.title}',
            'participation': participation.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error joining task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/submit', methods=['POST'])
@login_required
def submit_task(task_id):
    """Submit task completion for review"""
    try:
        from models import Task, TaskParticipation
        
        task = Task.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Завдання не знайдено'}), 404
        
        # Find user's active participation
        participation = TaskParticipation.query.filter_by(
            task_id=task_id,
            user_id=current_user.id
        ).filter(TaskParticipation.status.in_(['pending', 'in_progress'])).first()
        
        if not participation:
            return jsonify({'success': False, 'error': 'Ти не приєднався до цього завдання'}), 400
        
        data = request.get_json() or {}
        submission_text = data.get('text', '')
        submission_url = data.get('url', '')
        
        participation.submit(text=submission_text, url=submission_url)
        
        logger.info(f"User {current_user.username} submitted task: {task.title}")
        
        return jsonify({
            'success': True,
            'message': 'Task submitted for review!' if task.requires_approval else 'Task completed!',
            'participation': participation.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error submitting task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tasks/my-participations')
@login_required
def get_my_task_participations():
    """Get current user's task participations"""
    try:
        from models import TaskParticipation
        
        status = request.args.get('status')
        participations = TaskParticipation.get_user_participations(
            current_user.id, 
            status=status
        )
        
        return jsonify({
            'success': True,
            'participations': [p.to_dict() for p in participations]
        })
        
    except Exception as e:
        logger.error(f"Error getting participations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== TASK ADMIN ROUTES ====================

@app.route('/api/admin/tasks')
@login_required
def admin_get_tasks():
    """Get all tasks (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Task
        
        status = request.args.get('status', 'all')
        
        query = Task.query
        if status != 'all':
            query = query.filter_by(status=status)
        
        tasks = query.order_by(Task.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'tasks': [t.to_dict(include_participations=False) for t in tasks],
            'task_types': Task.get_task_types(),
            'reward_types': Task.get_reward_types()
        })
        
    except Exception as e:
        logger.error(f"Error getting admin tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tasks', methods=['POST'])
@login_required
def admin_create_task():
    """Create a new task (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Task
        
        data = request.get_json()
        
        if not data.get('title'):
            return jsonify({'success': False, 'error': 'Потрібен заголовок'}), 400
        
        task = Task(
            title=data.get('title'),
            description=data.get('description', ''),
            instructions=data.get('instructions', ''),
            task_type=data.get('task_type', 'custom'),
            category=data.get('category'),
            icon=data.get('icon', 'fa-tasks'),
            color=data.get('color', '#00f5ff'),
            image_url=data.get('image_url'),
            reward_type=data.get('reward_type', 'money'),
            reward_amount=float(data.get('reward_amount', 0)),
            reward_description=data.get('reward_description'),
            max_participants=int(data['max_participants']) if data.get('max_participants') else None,
            max_completions_per_user=int(data.get('max_completions_per_user', 1)),
            min_user_level=int(data.get('min_user_level', 0)),
            requires_subscription=data.get('requires_subscription', False),
            required_subscription_plans=data.get('required_subscription_plans'),
            requires_approval=data.get('requires_approval', True),
            status=data.get('status', 'active'),
            is_featured=data.get('is_featured', False),
            created_by_id=current_user.id
        )
        
        # Parse dates if provided
        if data.get('start_date'):
            task.start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
        if data.get('end_date'):
            task.end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f"Admin created task: {task.title}")
        
        return jsonify({
            'success': True,
            'message': f'Task "{task.title}" created successfully',
            'task': task.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tasks/<int:task_id>', methods=['PUT'])
@login_required
def admin_update_task(task_id):
    """Update a task (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Task
        
        task = Task.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Завдання не знайдено'}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'title' in data:
            task.title = data['title']
        if 'description' in data:
            task.description = data['description']
        if 'instructions' in data:
            task.instructions = data['instructions']
        if 'task_type' in data:
            task.task_type = data['task_type']
        if 'category' in data:
            task.category = data['category']
        if 'icon' in data:
            task.icon = data['icon']
        if 'color' in data:
            task.color = data['color']
        if 'image_url' in data:
            task.image_url = data['image_url']
        if 'reward_type' in data:
            task.reward_type = data['reward_type']
        if 'reward_amount' in data:
            task.reward_amount = float(data['reward_amount'])
        if 'reward_description' in data:
            task.reward_description = data['reward_description']
        if 'max_participants' in data:
            task.max_participants = int(data['max_participants']) if data['max_participants'] else None
        if 'max_completions_per_user' in data:
            task.max_completions_per_user = int(data['max_completions_per_user'])
        if 'min_user_level' in data:
            task.min_user_level = int(data['min_user_level'])
        if 'requires_subscription' in data:
            task.requires_subscription = data['requires_subscription']
        if 'required_subscription_plans' in data:
            task.required_subscription_plans = data['required_subscription_plans']
        if 'requires_approval' in data:
            task.requires_approval = data['requires_approval']
        if 'status' in data:
            task.status = data['status']
        if 'is_featured' in data:
            task.is_featured = data['is_featured']
        if 'start_date' in data:
            task.start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00')) if data['start_date'] else None
        if 'end_date' in data:
            task.end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00')) if data['end_date'] else None
        
        db.session.commit()
        
        logger.info(f"Admin updated task: {task.title}")
        
        return jsonify({
            'success': True,
            'message': f'Task "{task.title}" updated successfully',
            'task': task.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def admin_delete_task(task_id):
    """Delete a task (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Task
        
        task = Task.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Завдання не знайдено'}), 404
        
        title = task.title
        db.session.delete(task)
        db.session.commit()
        
        logger.info(f"Admin deleted task: {title}")
        
        return jsonify({
            'success': True,
            'message': f'Task "{title}" deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tasks/pending-reviews')
@login_required
def admin_get_pending_reviews():
    """Get all task submissions awaiting review (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import TaskParticipation
        
        pending = TaskParticipation.get_pending_reviews()
        
        return jsonify({
            'success': True,
            'pending_count': len(pending),
            'submissions': [p.to_dict() for p in pending]
        })
        
    except Exception as e:
        logger.error(f"Error getting pending reviews: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tasks/participation/<int:participation_id>/approve', methods=['POST'])
@login_required
def admin_approve_participation(participation_id):
    """Approve a task submission (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import TaskParticipation
        
        participation = TaskParticipation.query.get(participation_id)
        if not participation:
            return jsonify({'success': False, 'error': 'Подання не знайдено'}), 404
        
        if participation.status != 'submitted':
            return jsonify({'success': False, 'error': 'Подання не очікує перевірки'}), 400
        
        data = request.get_json() or {}
        notes = data.get('notes', '')
        
        participation.approve(current_user, notes=notes)
        
        logger.info(f"Admin approved task submission for user {participation.user.username}")
        
        return jsonify({
            'success': True,
            'message': f'Submission approved! Reward given: {participation.reward_amount}',
            'participation': participation.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving submission: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tasks/participation/<int:participation_id>/reject', methods=['POST'])
@login_required
def admin_reject_participation(participation_id):
    """Reject a task submission (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import TaskParticipation
        
        participation = TaskParticipation.query.get(participation_id)
        if not participation:
            return jsonify({'success': False, 'error': 'Подання не знайдено'}), 404
        
        if participation.status != 'submitted':
            return jsonify({'success': False, 'error': 'Подання не очікує перевірки'}), 400
        
        data = request.get_json() or {}
        reason = data.get('reason', 'Submission did not meet requirements')
        notes = data.get('notes', '')
        
        participation.reject(current_user, reason=reason, notes=notes)
        
        logger.info(f"Admin rejected task submission for user {participation.user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Submission rejected',
            'participation': participation.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting submission: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/tasks/<int:task_id>/participations')
@login_required
def admin_get_task_participations(task_id):
    """Get all participations for a specific task (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Task, TaskParticipation
        
        task = Task.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Завдання не знайдено'}), 404
        
        status = request.args.get('status')
        query = TaskParticipation.query.filter_by(task_id=task_id)
        
        if status:
            query = query.filter_by(status=status)
        
        participations = query.order_by(TaskParticipation.updated_at.desc()).all()
        
        return jsonify({
            'success': True,
            'task': task.to_dict(),
            'participations': [p.to_dict() for p in participations]
        })
        
    except Exception as e:
        logger.error(f"Error getting task participations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== INSURANCE FUND (SAFETY POOL) ====================

@app.route('/api/insurance-fund')
def get_insurance_fund():
    """
    Public API endpoint for Insurance Fund (Safety Pool) information.
    
    The Insurance Fund accumulates 5% of platform fees and is used to
    cover slippage losses in extreme market conditions.
    
    This endpoint is public to promote transparency and build trust.
    """
    try:
        fund_info = SystemStats.get_insurance_fund_info()
        
        return jsonify({
            'success': True,
            'insurance_fund': {
                'balance': fund_info['balance'],
                'formatted_balance': fund_info['formatted_balance'],
                'contribution_rate': fund_info['contribution_rate'],
                'description': fund_info['description'],
                'is_verified': fund_info['is_verified'],
                'last_updated': fund_info['last_updated']
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting Insurance Fund info: {e}")
        # Return a default value even on error for UI consistency
        return jsonify({
            'success': True,
            'insurance_fund': {
                'balance': 10000.0,
                'formatted_balance': '$10,000.00',
                'contribution_rate': '5%',
                'description': 'Safety Pool - covers slippage losses in extreme market conditions',
                'is_verified': True,
                'last_updated': None
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        })


# ==================== GOVERNANCE / VOTING SYSTEM ====================

@app.route('/governance')
@login_required
def governance_page():
    """
    Governance page showing active proposals and voting UI.
    Only Elite users (level >= 4) can vote, but all users can view.
    """
    return render_template('governance.html')


@app.route('/api/governance/proposals')
def get_proposals():
    """
    Get all proposals with optional filtering.
    
    Query params:
    - status: 'active', 'passed', 'rejected', 'implemented', 'all' (default: 'active')
    - category: 'trading_pair', 'risk_management', 'exchange', 'feature', 'other'
    - limit: max number of results (default: 50)
    """
    try:
        from models import Proposal, Vote
        
        status = request.args.get('status', 'active')
        category = request.args.get('category')
        limit = min(int(request.args.get('limit', 50)), 100)
        
        # Build query
        query = Proposal.query
        
        if status and status != 'all':
            query = query.filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        proposals = query.order_by(Proposal.created_at.desc()).limit(limit).all()
        
        # Check if current user can vote and their existing votes
        user_votes = {}
        can_vote = False
        vote_eligibility_message = "Login required to vote"
        
        if current_user.is_authenticated:
            can_vote_result = Vote.can_user_vote(current_user)
            can_vote = can_vote_result[0]
            vote_eligibility_message = can_vote_result[1]
            
            # Get user's votes for these proposals
            proposal_ids = [p.id for p in proposals]
            user_vote_records = Vote.query.filter(
                Vote.user_id == current_user.id,
                Vote.proposal_id.in_(proposal_ids)
            ).all()
            user_votes = {v.proposal_id: v.vote_type for v in user_vote_records}
        
        return jsonify({
            'success': True,
            'proposals': [p.to_dict() for p in proposals],
            'user_votes': user_votes,
            'can_vote': can_vote,
            'vote_eligibility_message': vote_eligibility_message,
            'total_count': len(proposals)
        })
        
    except Exception as e:
        logger.error(f"Error getting proposals: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося завантажити пропозиції'
        }), 500


@app.route('/api/governance/proposals/<int:proposal_id>')
def get_proposal(proposal_id):
    """Get a single proposal with detailed information."""
    try:
        from models import Proposal, Vote
        
        proposal = Proposal.query.get(proposal_id)
        
        if not proposal:
            return jsonify({
                'success': False,
                'error': 'Proposal not found'
            }), 404
        
        # Check user's vote
        user_vote = None
        can_vote = False
        
        if current_user.is_authenticated:
            vote = Vote.query.filter_by(
                proposal_id=proposal_id,
                user_id=current_user.id
            ).first()
            if vote:
                user_vote = vote.vote_type
            
            can_vote = Vote.can_user_vote(current_user)[0] and proposal.is_voting_open() and user_vote is None
        
        return jsonify({
            'success': True,
            'proposal': proposal.to_dict(include_votes=True),
            'user_vote': user_vote,
            'can_vote': can_vote
        })
        
    except Exception as e:
        logger.error(f"Error getting proposal {proposal_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося завантажити пропозицію'
        }), 500


@app.route('/api/governance/vote', methods=['POST'])
@login_required
def submit_vote():
    """
    Submit a vote on a proposal.
    
    Only Elite users (level >= 4) can vote.
    """
    try:
        from models import Proposal, Vote
        
        data = request.get_json()
        proposal_id = data.get('proposal_id')
        vote_type = data.get('vote_type', '').lower()
        
        if not proposal_id:
            return jsonify({
                'success': False,
                'error': 'Proposal ID required'
            }), 400
        
        if vote_type not in ['yes', 'no']:
            return jsonify({
                'success': False,
                'error': 'Vote must be "yes" or "no"'
            }), 400
        
        # Check if user can vote
        can_vote, reason = Vote.can_user_vote(current_user)
        if not can_vote:
            return jsonify({
                'success': False,
                'error': reason
            }), 403
        
        # Get proposal
        proposal = Proposal.query.get(proposal_id)
        if not proposal:
            return jsonify({
                'success': False,
                'error': 'Proposal not found'
            }), 404
        
        # Calculate vote weight based on user's volume
        vote_weight = Vote.calculate_vote_weight(current_user)
        
        # Submit vote
        success, message, vote = proposal.add_vote(
            user_id=current_user.id,
            vote_type=vote_type,
            vote_weight=vote_weight
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        logger.info(f"User {current_user.username} voted {vote_type} on proposal {proposal_id} (weight: {vote_weight:.2f})")
        
        return jsonify({
            'success': True,
            'message': message,
            'vote': vote.to_dict(),
            'proposal': proposal.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error submitting vote: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося відправити голос'
        }), 500


@app.route('/api/governance/eligibility')
@login_required
def check_vote_eligibility():
    """Check if current user is eligible to vote."""
    try:
        from models import Vote
        
        can_vote, reason = Vote.can_user_vote(current_user)
        vote_weight = Vote.calculate_vote_weight(current_user) if can_vote else 0
        
        user_level = current_user.current_level
        
        return jsonify({
            'success': True,
            'eligible': can_vote,
            'reason': reason,
            'vote_weight': round(vote_weight, 2),
            'current_level': {
                'name': user_level.name if user_level else 'None',
                'order_rank': user_level.order_rank if user_level else 0,
                'required_rank': 4  # Elite level
            },
            'trading_volume': round(current_user.total_trading_volume or 0, 2)
        })
        
    except Exception as e:
        logger.error(f"Error checking vote eligibility: {e}")
        return jsonify({
            'success': False,
            'error': 'Не вдалося перевірити право голосу'
        }), 500


# Admin endpoints for proposal management

@app.route('/api/admin/governance/create', methods=['POST'])
@login_required
def admin_create_proposal():
    """Create a new proposal (admin only)."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Proposal
        
        data = request.get_json()
        
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        category = data.get('category', 'other')
        voting_days = int(data.get('voting_days', 7))
        min_votes = int(data.get('min_votes', 5))
        pass_threshold = float(data.get('pass_threshold', 60.0))
        
        if not title or not description:
            return jsonify({
                'success': False,
                'error': 'Title and description are required'
            }), 400
        
        if category not in ['trading_pair', 'risk_management', 'exchange', 'feature', 'other']:
            return jsonify({
                'success': False,
                'error': 'Невірна категорія'
            }), 400
        
        proposal = Proposal.create_proposal(
            title=title,
            description=description,
            category=category,
            created_by_id=current_user.id,
            voting_days=voting_days,
            min_votes=min_votes,
            pass_threshold=pass_threshold
        )
        
        logger.info(f"Admin {current_user.username} created proposal: {title}")
        
        return jsonify({
            'success': True,
            'message': f'Proposal "{title}" created successfully',
            'proposal': proposal.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/governance/<int:proposal_id>/close', methods=['POST'])
@login_required
def admin_close_proposal(proposal_id):
    """Close voting on a proposal (admin only)."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Proposal
        
        proposal = Proposal.query.get(proposal_id)
        
        if not proposal:
            return jsonify({
                'success': False,
                'error': 'Proposal not found'
            }), 404
        
        if proposal.status != 'active':
            return jsonify({
                'success': False,
                'error': 'Proposal is not active'
            }), 400
        
        proposal.close_voting()
        
        logger.info(f"Admin {current_user.username} closed proposal {proposal_id}: {proposal.status}")
        
        return jsonify({
            'success': True,
            'message': f'Proposal closed. Status: {proposal.get_status_label()}',
            'proposal': proposal.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error closing proposal: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/governance/<int:proposal_id>/implement', methods=['POST'])
@login_required
def admin_implement_proposal(proposal_id):
    """Mark a passed proposal as implemented (admin only)."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import Proposal
        
        data = request.get_json() or {}
        admin_notes = data.get('admin_notes', '')
        
        proposal = Proposal.query.get(proposal_id)
        
        if not proposal:
            return jsonify({
                'success': False,
                'error': 'Proposal not found'
            }), 404
        
        if proposal.status != 'passed':
            return jsonify({
                'success': False,
                'error': 'Only passed proposals can be marked as implemented'
            }), 400
        
        proposal.mark_implemented(admin_notes=admin_notes)
        
        logger.info(f"Admin {current_user.username} marked proposal {proposal_id} as implemented")
        
        return jsonify({
            'success': True,
            'message': 'Proposal marked as implemented',
            'proposal': proposal.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error implementing proposal: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/favicon.ico')
def favicon():
    return '', 204  # No content - prevents 404 errors


def _require_internal_token(env_var: str) -> None:
    """Require internal token for sensitive endpoints if configured."""
    expected = os.environ.get(env_var, '')
    if not expected:
        return
    provided = request.headers.get('X-Internal-Token', '')
    if not provided or not secrets.compare_digest(provided, expected):
        abort(403)


@app.route('/health')
def health_check():
    """Health check endpoint for Docker/Kubernetes probes"""
    _require_internal_token('INTERNAL_HEALTH_TOKEN')
    try:
        # Verify database connection
        db.session.execute(text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        logger.error("Health check database failure", exc_info=True)
        db_status = 'unhealthy'
    
    return jsonify({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'database': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200 if db_status == 'healthy' else 503


@app.route('/metrics')
def prometheus_metrics():
    """Prometheus metrics endpoint for observability stack."""
    _require_internal_token('INTERNAL_METRICS_TOKEN')
    from flask import Response
    metrics_output, content_type = get_metrics()
    return Response(metrics_output, mimetype=content_type)


# ==================== GOOGLE OAUTH + WEBAUTHN MFA ====================

def _get_webauthn_rp_id() -> str:
    if Config.WEBAUTHN_RP_ID:
        return Config.WEBAUTHN_RP_ID
    return request.host.split(':')[0]


def _get_webauthn_origin() -> str:
    if Config.WEBAUTHN_ORIGIN:
        return Config.WEBAUTHN_ORIGIN.rstrip('/')
    return request.host_url.rstrip('/')


def _get_pending_mfa_user() -> User | None:
    user_id = session.get('mfa_user_id')
    if not user_id:
        return None
    return db.session.get(User, int(user_id))


def _build_unique_username(seed: str) -> str:
    base = re.sub(r'[^A-Za-z0-9_.@+\-]', '', seed)[:40]
    if not base:
        base = f"user_{secrets.token_hex(4)}"
    candidate = base[:50]
    suffix = 1
    while User.query.filter_by(username=candidate).first():
        candidate = f"{base[:45]}_{suffix}"
        suffix += 1
    return candidate[:50]


def _finalize_mfa_login(user: User):
    login_user(user)
    init_session_security()
    session.pop('mfa_pending', None)
    session.pop('mfa_user_id', None)
    session.pop('mfa_started_at', None)
    session.pop('mfa_provider', None)
    session.pop('webauthn_challenge', None)
    session.pop('webauthn_origin', None)
    session.pop('webauthn_rp_id', None)
    next_url = session.pop('post_auth_redirect', None)
    if next_url and is_safe_redirect_url(next_url):
        return next_url
    return url_for('dashboard')


@app.route('/auth/google')
def auth_google():
    if not Config.GOOGLE_CLIENT_ID or not Config.GOOGLE_CLIENT_SECRET:
        flash('Google login is not configured.', 'error')
        return redirect(url_for('login'))
    next_url = request.args.get('next')
    if next_url and is_safe_redirect_url(next_url):
        session['post_auth_redirect'] = next_url
    forwarded_proto = request.headers.get('X-Forwarded-Proto', '')
    scheme = 'https' if forwarded_proto == 'https' or request.is_secure else 'http'
    redirect_uri = Config.GOOGLE_OAUTH_REDIRECT_URL or url_for('auth_google_callback', _external=True, _scheme=scheme)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route('/auth/google/callback')
def auth_google_callback():
    if not Config.GOOGLE_CLIENT_ID or not Config.GOOGLE_CLIENT_SECRET:
        flash('Google login is not configured.', 'error')
        return redirect(url_for('login'))
    try:
        token = oauth.google.authorize_access_token()
        userinfo = oauth.google.parse_id_token(token)
        if not userinfo:
            userinfo = oauth.google.get('userinfo').json()
    except Exception as exc:
        logger.warning(f"Google OAuth failed: {exc}")
        flash('Google login failed. Please try again.', 'error')
        return redirect(url_for('login'))

    email = (userinfo.get('email') or '').lower()
    sub = userinfo.get('sub')
    email_verified = bool(userinfo.get('email_verified'))
    if not email or not sub:
        flash('Google account is missing required profile information.', 'error')
        return redirect(url_for('login'))

    user = User.query.filter_by(google_sub=sub).first()
    if not user:
        user = User.query.filter_by(email=email).first()
    if not user:
        username = _build_unique_username(email)
        user = User(
            username=username,
            email=email,
            first_name=userinfo.get('given_name') or '',
            last_name=userinfo.get('family_name') or '',
            is_active=True,
            is_paused=True,
            auth_provider='google',
            google_sub=sub,
            google_email_verified=email_verified
        )
        user.ensure_referral_code()
        db.session.add(user)
        db.session.commit()
    else:
        user.google_sub = sub
        user.google_email_verified = email_verified
        user.auth_provider = 'google'
        if not user.email:
            user.email = email
        if not user.first_name and userinfo.get('given_name'):
            user.first_name = userinfo.get('given_name')
        if not user.last_name and userinfo.get('family_name'):
            user.last_name = userinfo.get('family_name')
        db.session.commit()

    session['mfa_user_id'] = user.id
    session['mfa_pending'] = True
    session['mfa_provider'] = 'google'
    session['mfa_started_at'] = time.time()
    return redirect(url_for('mfa_webauthn'))


@app.route('/mfa')
def mfa_webauthn():
    user = _get_pending_mfa_user()
    if not user:
        return redirect(url_for('login'))
    credentials = WebAuthnCredential.query.filter_by(user_id=user.id).all()
    needs_registration = len(credentials) == 0
    return render_template(
        'mfa_webauthn.html',
        user=user,
        needs_registration=needs_registration,
        csrf_value=generate_csrf_token()
    )


@app.route('/webauthn/registration/options', methods=['POST'])
def webauthn_registration_options():
    user = _get_pending_mfa_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    csrf_token = request.headers.get('X-CSRF-Token', '')
    if not verify_csrf_token(csrf_token):
        return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 403

    rp_id = _get_webauthn_rp_id()
    rp_name = Config.WEBAUTHN_RP_NAME or 'MIMIC'
    origin = _get_webauthn_origin()
    existing = WebAuthnCredential.query.filter_by(user_id=user.id).all()
    exclude = [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=base64url_to_bytes(cred.credential_id)
        )
        for cred in existing
    ]

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=str(user.id).encode(),
        user_name=user.email or user.username,
        user_display_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED
        ),
        exclude_credentials=exclude
    )
    session['webauthn_challenge'] = bytes_to_base64url(options.challenge)
    session['webauthn_origin'] = origin
    session['webauthn_rp_id'] = rp_id
    options_json = options.json() if hasattr(options, "json") else json.dumps(options)
    return jsonify(json.loads(options_json))


@app.route('/webauthn/registration/verify', methods=['POST'])
def webauthn_registration_verify():
    user = _get_pending_mfa_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    csrf_token = request.headers.get('X-CSRF-Token', '')
    if not verify_csrf_token(csrf_token):
        return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 403

    challenge = session.get('webauthn_challenge')
    origin = session.get('webauthn_origin')
    rp_id = session.get('webauthn_rp_id')
    if not challenge or not origin or not rp_id:
        return jsonify({'success': False, 'error': 'Missing challenge'}), 400

    payload = request.get_json(silent=True) or {}
    device_name = (payload.get('device_name') or '').strip()[:100] or None
    credential_json = payload.get('credential')
    if not credential_json:
        return jsonify({'success': False, 'error': 'Invalid credential'}), 400

    try:
        verified = verify_registration_response(
            credential=RegistrationCredential.parse_raw(json.dumps(credential_json)),
            expected_challenge=base64url_to_bytes(challenge),
            expected_origin=origin,
            expected_rp_id=rp_id,
            require_user_verification=True
        )
    except Exception as exc:
        logger.warning(f"WebAuthn registration failed: {exc}")
        return jsonify({'success': False, 'error': 'Registration failed'}), 400

    new_credential = WebAuthnCredential(
        user_id=user.id,
        credential_id=bytes_to_base64url(verified.credential_id),
        public_key=bytes_to_base64url(verified.credential_public_key),
        sign_count=verified.sign_count,
        transports=','.join(credential_json.get('response', {}).get('transports', [])) or None,
        device_name=device_name
    )
    user.webauthn_enabled = True
    db.session.add(new_credential)
    db.session.commit()

    redirect_url = _finalize_mfa_login(user)
    return jsonify({'success': True, 'redirect': redirect_url})


@app.route('/webauthn/authentication/options', methods=['POST'])
def webauthn_authentication_options():
    user = _get_pending_mfa_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    csrf_token = request.headers.get('X-CSRF-Token', '')
    if not verify_csrf_token(csrf_token):
        return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 403

    rp_id = _get_webauthn_rp_id()
    origin = _get_webauthn_origin()
    credentials = WebAuthnCredential.query.filter_by(user_id=user.id).all()
    allow_credentials = [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=base64url_to_bytes(cred.credential_id)
        )
        for cred in credentials
    ]

    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED
    )
    session['webauthn_challenge'] = bytes_to_base64url(options.challenge)
    session['webauthn_origin'] = origin
    session['webauthn_rp_id'] = rp_id
    options_json = options.json() if hasattr(options, "json") else json.dumps(options)
    return jsonify(json.loads(options_json))


@app.route('/webauthn/authentication/verify', methods=['POST'])
def webauthn_authentication_verify():
    user = _get_pending_mfa_user()
    if not user:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    csrf_token = request.headers.get('X-CSRF-Token', '')
    if not verify_csrf_token(csrf_token):
        return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 403

    challenge = session.get('webauthn_challenge')
    origin = session.get('webauthn_origin')
    rp_id = session.get('webauthn_rp_id')
    if not challenge or not origin or not rp_id:
        return jsonify({'success': False, 'error': 'Missing challenge'}), 400

    payload = request.get_json(silent=True) or {}
    credential_json = payload.get('credential')
    if not credential_json:
        return jsonify({'success': False, 'error': 'Invalid credential'}), 400

    credential_id = credential_json.get('id')
    if not credential_id:
        return jsonify({'success': False, 'error': 'Invalid credential'}), 400
    stored = WebAuthnCredential.query.filter_by(credential_id=credential_id, user_id=user.id).first()
    if not stored:
        return jsonify({'success': False, 'error': 'Unknown credential'}), 400

    try:
        verified = verify_authentication_response(
            credential=AuthenticationCredential.parse_raw(json.dumps(credential_json)),
            expected_challenge=base64url_to_bytes(challenge),
            expected_origin=origin,
            expected_rp_id=rp_id,
            credential_public_key=base64url_to_bytes(stored.public_key),
            credential_current_sign_count=stored.sign_count,
            require_user_verification=True
        )
    except Exception as exc:
        logger.warning(f"WebAuthn authentication failed: {exc}")
        return jsonify({'success': False, 'error': 'Authentication failed'}), 400

    stored.update_sign_count(verified.new_sign_count)
    stored.last_used_at = datetime.now(timezone.utc)
    user.webauthn_enabled = True
    db.session.commit()

    redirect_url = _finalize_mfa_login(user)
    return jsonify({'success': True, 'redirect': redirect_url})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    ip = get_client_ip()
    
    # Check if IP is blocked
    if login_tracker.is_blocked(ip):
        flash('Занадто багато невдалих спроб. Спробуйте пізніше.', 'error')
        return render_template('login.html'), 429
    
    if request.method == 'POST':
        # CSRF token validation
        from security import verify_csrf_token
        csrf_token = request.form.get('csrf_token', '')
        if not verify_csrf_token(csrf_token):
            audit.log_security_event("CSRF_VALIDATION_FAIL", f"IP: {ip}, Endpoint: login", "WARNING")
            flash('Сесія закінчилася. Спробуйте ще раз.', 'error')
            return render_template('login.html'), 403
        
        # Rate limit login attempts
        if not login_limiter.check(ip, max_requests=10, window=60):
            flash('Занадто багато запитів. Зачекайте хвилину.', 'error')
            return render_template('login.html'), 429
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # Validate inputs
        valid_user, username = InputValidator.validate_username(username)
        if not valid_user:
            flash('Невірний формат логіну', 'error')
            return render_template('login.html')
        
        if not password:
            flash('Введіть пароль', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # Successful login
            login_tracker.record_success(ip)
            remember = request.form.get('remember') == 'on'
            login_user(user, remember=remember)
            init_session_security()  # Set session fingerprint
            
            audit.log_login(username, ip, True)
            logger.info(f"✅ User logged in: {username}")
            
            next_page = request.args.get('next')
            # Prevent open redirect attacks
            if next_page and not next_page.startswith('/'):
                next_page = None
            return redirect(next_page or url_for('dashboard'))
        
        # Failed login
        login_tracker.record_failure(ip, username)
        audit.log_login(username, ip, False, "Invalid credentials")
        flash('Невірний логін або пароль', 'error')
        
    return render_template('login.html')


# ==================== LEGAL / COMPLIANCE ROUTES ====================

@app.route('/legal/accept', methods=['GET', 'POST'])
@login_required
def legal_accept():
    """
    Terms of Service and Risk Disclaimer acceptance page.
    Users must accept the current TOS version to continue using the platform.
    """
    from security import verify_csrf_token
    
    tos_version = getattr(Config, 'TOS_VERSION', '1.0')
    ip = get_client_ip()
    
    # Check if user has already accepted this version
    if UserConsent.has_user_accepted_tos(current_user.id, tos_version):
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # CSRF validation
        csrf_token = request.form.get('csrf_token', '')
        if not verify_csrf_token(csrf_token):
            audit.log_security_event("CSRF_VALIDATION_FAIL", f"IP: {ip}, Endpoint: legal_accept", "WARNING")
            flash('Сесія закінчилася. Спробуй ще раз.', 'error')
            return render_template('legal_accept.html', tos_version=tos_version), 403
        
        # Check all required consents
        consent_risks = request.form.get('consent_risks')
        consent_tos = request.form.get('consent_tos')
        consent_jurisdiction = request.form.get('consent_jurisdiction')
        
        if not all([consent_risks, consent_tos, consent_jurisdiction]):
            flash('Необхідно прийняти всі умови для продовження.', 'error')
            return render_template('legal_accept.html', tos_version=tos_version)
        
        # Record the consent
        try:
            user_agent = request.headers.get('User-Agent', '')
            UserConsent.record_consent(
                user_id=current_user.id,
                tos_version=tos_version,
                ip_address=ip,
                user_agent=user_agent,
                consent_type='tos_and_risk_disclaimer'
            )
            
            audit.log_security_event(
                "TOS_ACCEPTED",
                f"User: {current_user.username}, Version: {tos_version}, IP: {ip}",
                "INFO"
            )
            logger.info(f"✅ User {current_user.username} accepted TOS v{tos_version}")
            flash('Дякуємо за прийняття Умов використання!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            logger.error(f"Failed to record TOS consent for user {current_user.id}: {e}")
            flash('Сталася помилка. Спробуй ще раз.', 'error')
            return render_template('legal_accept.html', tos_version=tos_version)
    
    return render_template('legal_accept.html', tos_version=tos_version)


@app.route('/legal/tos')
def legal_tos():
    """Display the full Terms of Service page"""
    tos_version = getattr(Config, 'TOS_VERSION', '1.0')
    return render_template('legal_tos.html', tos_version=tos_version)


@app.route('/legal/privacy')
def legal_privacy():
    """Display the Privacy Policy page"""
    return render_template('legal_privacy.html')


@app.route('/legal/risk-disclaimer')
def legal_risk_disclaimer():
    """Display the Risk Disclaimer page"""
    return render_template('legal_risk_disclaimer.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    ip = get_client_ip()
    
    # Get referral code from query param or form
    ref_code = request.args.get('ref', '') or request.form.get('ref_code', '')
    referrer = None
    if ref_code:
        referrer = User.query.filter_by(referral_code=ref_code.upper().strip()).first()
    
    if request.method == 'POST':
        # CSRF token validation
        from security import verify_csrf_token
        csrf_token = request.form.get('csrf_token', '')
        if not verify_csrf_token(csrf_token):
            audit.log_security_event("CSRF_VALIDATION_FAIL", f"IP: {ip}, Endpoint: register", "WARNING")
            flash('Сесія закінчилася. Спробуйте ще раз.', 'error')
            return render_template('register.html', ref_code=ref_code), 403
        
        # Rate limit registrations
        if not api_limiter.check(f"register_{ip}", max_requests=3, window=3600):
            flash('Занадто багато реєстрацій. Спробуйте пізніше.', 'error')
            return render_template('register.html', ref_code=ref_code), 429
        
        phone = request.form.get('phone', '').strip()
        first_name = InputValidator.sanitize_string(request.form.get('first_name', ''), 50)
        last_name = InputValidator.sanitize_string(request.form.get('last_name', ''), 50)
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        # Exchange API credentials
        exchange_name = request.form.get('exchange_name', '').strip().lower()
        api_key = request.form.get('api_key', '').strip()
        api_secret = request.form.get('api_secret', '').strip()
        passphrase = request.form.get('passphrase', '').strip() if request.form.get('passphrase') else None
        
        # Get referral code from hidden field (in case it was passed via URL initially)
        ref_code = request.form.get('ref_code', '').strip() or ref_code
        if ref_code and not referrer:
            referrer = User.query.filter_by(referral_code=ref_code.upper().strip()).first()
        
        # Validate phone/username
        valid, result = InputValidator.validate_username(phone)
        if not valid:
            flash(f'Невірний формат номеру: {result}', 'error')
            return render_template('register.html')
        phone = result
        
        # Validate email if provided
        if email:
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                flash('Невірний формат email', 'error')
                return render_template('register.html', ref_code=ref_code)
            if User.query.filter_by(email=email).first():
                flash('Користувач з таким email вже існує', 'error')
                return render_template('register.html', ref_code=ref_code)
        
        # Validate password
        valid, result = InputValidator.validate_password(password)
        if not valid:
            flash(f'Невірний пароль: {result}', 'error')
            return render_template('register.html', ref_code=ref_code)
        
        # Validate exchange selection
        if not exchange_name:
            flash('Виберіть біржу', 'error')
            return render_template('register.html', ref_code=ref_code)
        
        # Check if exchange is enabled by admin
        exchange_config = ExchangeConfig.query.filter_by(exchange_name=exchange_name, is_enabled=True, is_verified=True).first()
        if not exchange_config:
            flash('Ця біржа недоступна для реєстрації. Зверніться до адміністратора.', 'error')
            return render_template('register.html', ref_code=ref_code)
        
        # Check if passphrase is required
        if exchange_config.requires_passphrase and not passphrase:
            flash(f'Для біржі {exchange_config.display_name} потрібен Passphrase', 'error')
            return render_template('register.html', ref_code=ref_code)
        
        # Validate API keys
        valid, result = InputValidator.validate_api_key(api_key)
        if not valid:
            flash(f'Невірний API Key: {result}', 'error')
            return render_template('register.html', ref_code=ref_code)
        
        valid, result = InputValidator.validate_api_key(api_secret)
        if not valid:
            flash(f'Невірний API Secret: {result}', 'error')
            return render_template('register.html', ref_code=ref_code)
        
        # Validation
        if not all([phone, first_name, password, exchange_name, api_key, api_secret]):
            flash('Заповніть всі обов\'язкові поля', 'error')
            return render_template('register.html', ref_code=ref_code)
        
        if User.query.filter_by(username=phone).first():
            flash('Користувач з таким номером вже існує', 'error')
            return render_template('register.html', ref_code=ref_code)
        
        try:
            # Validate API keys with exchange before creating user
            from service_validator import validate_and_connect, ExchangeValidationError, ExchangeConnectionError
            
            try:
                validation_result = validate_and_connect(
                    exchange_name=exchange_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    passphrase=passphrase
                )
                
                if not validation_result.get('success'):
                    flash('Не вдалося підключитися до біржі. Перевірте API ключі.', 'error')
                    return render_template('register.html', ref_code=ref_code)
                    
            except ExchangeValidationError as e:
                flash(f'Помилка валідації: {str(e)}', 'error')
                return render_template('register.html', ref_code=ref_code)
            except ExchangeConnectionError as e:
                flash(f'Помилка підключення до біржі: {str(e)}', 'error')
                return render_template('register.html', ref_code=ref_code)
            except Exception as e:
                logger.warning(f"Exchange validation error during registration: {e}")
                # Continue with registration even if validation fails - admin will verify
            
            # Create user
            new_user = User(
                username=phone,
                phone=phone,
                email=email if email else None,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_paused=True,  # Requires admin approval
                custom_risk=0.0,
                custom_leverage=0,
                max_positions=GLOBAL_TRADE_SETTINGS['max_positions'],
                referred_by_id=referrer.id if referrer else None
            )
            new_user.set_password(password)
            # Generate unique referral code for new user
            new_user.referral_code = User.generate_referral_code()
            # Also store keys in user for backward compatibility
            new_user.set_keys(api_key, api_secret)
            
            db.session.add(new_user)
            db.session.flush()  # Get the user ID
            
            # Create UserExchange record
            user_exchange = UserExchange(
                user_id=new_user.id,
                exchange_name=exchange_name,
                label=f"{exchange_config.display_name} - Main",
                api_key=api_key,
                status='PENDING',  # Requires admin approval
                is_active=False,
                trading_enabled=False
            )
            user_exchange.set_api_secret(api_secret)
            if passphrase:
                user_exchange.set_passphrase(passphrase)
            
            db.session.add(user_exchange)
            db.session.commit()
            
            # Mark referral click as converted (if applicable)
            if referrer:
                try:
                    from models import ReferralClick
                    ReferralClick.mark_converted(referrer.id, ip, new_user.id)
                except Exception as ref_err:
                    logger.warning(f"Failed to mark referral click as converted: {ref_err}")
            
            engine.load_slaves()
            
            audit.log_security_event("NEW_REGISTRATION", f"User: {phone}, Exchange: {exchange_name}, IP: {ip}", "INFO")
            logger.info(f"✅ New user registered: {phone} with {exchange_config.display_name}")
            
            if telegram:
                telegram.notify_system_event(
                    "🆕 Новий користувач", 
                    f"{first_name} {last_name}\n📱 {phone}\n🏦 {exchange_config.display_name}"
                )
            
            # Auto-login the user after successful registration
            login_user(new_user)
            audit.log_security_event("AUTO_LOGIN_AFTER_REGISTER", f"User: {phone}, IP: {ip}", "INFO")
            
            flash(f'Реєстрація успішна! Ваша заявка на підключення до {exchange_config.display_name} надіслана адміністратору на перевірку.', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {e}")
            flash(f'Помилка реєстрації: {str(e)}', 'error')
            return render_template('register.html', ref_code=ref_code)
        
    return render_template('register.html', ref_code=ref_code)


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        users = User.query.all()
        
        # Get master balance
        m_bal = "N/A"  # Default when no exchanges configured
        
        # Check if any master exchanges are configured
        has_master_exchanges = bool(engine.master_clients) or bool(engine.master_client)
        
        if not has_master_exchanges:
            m_bal = "No exchanges configured"
        elif engine.master_client:
            try:
                balances = engine.master_client.futures_account_balance()
                for b in balances:
                    if b['asset'] == 'USDT':
                        m_bal = f"{float(b['balance']):,.2f}"
                        break
            except Exception as e:
                logger.warning(f"Failed to fetch master balance: {e}")
                m_bal = "Помилка"
        
        # Get user balances for admin view - from all connected exchanges
        user_balances = {}
        user_exchange_details = {}  # Detailed balance info per exchange
        
        for user in users:
            if user.role != 'admin':
                # Try to get balances from UserExchange records (new multi-exchange system)
                exchange_balances = get_user_exchange_balances(user.id)
                
                if exchange_balances['exchanges']:
                    # Store detailed exchange info
                    user_exchange_details[user.id] = exchange_balances['exchanges']
                    
                    # Sum up total balance from all exchanges
                    if exchange_balances['total'] > 0:
                        user_balances[user.id] = exchange_balances['total']
                    else:
                        # Check if any exchange has a valid balance
                        valid_balances = [e['balance'] for e in exchange_balances['exchanges'] if e['balance'] is not None]
                        user_balances[user.id] = sum(valid_balances) if valid_balances else None
                else:
                    # Fallback to legacy slave_clients if no UserExchange records
                    slave = next((s for s in engine.slave_clients if s['id'] == user.id), None)
                    if slave:
                        try:
                            bal_data = slave['client'].futures_account_balance()
                            for b in bal_data:
                                if b['asset'] == 'USDT':
                                    user_balances[user.id] = float(b['balance'])
                                    user_exchange_details[user.id] = [{
                                        'id': 0,
                                        'exchange_name': 'binance',
                                        'label': 'Binance (Legacy)',
                                        'balance': float(b['balance']),
                                        'status': 'APPROVED',
                                        'trading_enabled': True,
                                        'error': None
                                    }]
                                    break
                        except Exception:
                            user_balances[user.id] = None
                    else:
                        user_balances[user.id] = None
        
        # Get recent trades
        history_objs = TradeHistory.query.order_by(TradeHistory.close_time.desc()).limit(100).all()
        history_data = [h.to_dict() for h in history_objs]
        
        # Get master positions from ALL exchanges for initial load
        master_positions = []
        master_exchange_balances = []
        
        if has_master_exchanges:
            try:
                master_positions = engine.get_all_master_positions()
                master_exchange_balances = engine.get_all_master_balances()
                # Update m_bal with total from all exchanges
                total_balance = sum(b['balance'] for b in master_exchange_balances if b['balance'] is not None)
                if total_balance > 0:
                    m_bal = f"{total_balance:,.2f}"
                elif master_exchange_balances:
                    # Exchanges connected but balance is 0
                    m_bal = "0.00"
            except Exception as e:
                logger.warning(f"Failed to fetch master data: {e}")
                m_bal = "Error fetching data"
        
        return render_template('dashboard_admin.html',
                             users=users,
                             user_balances=user_balances,
                             user_exchange_details=user_exchange_details,
                             engine_paused=engine.is_paused,
                             master_balance=m_bal,
                             master_exchange_balances=master_exchange_balances,
                             closed_trades=history_data,
                             master_positions=master_positions,
                             global_settings=GLOBAL_TRADE_SETTINGS)
    else:
        # User dashboard
        u_bal = "Syncing..."
        slave = next((s for s in engine.slave_clients if s['id'] == current_user.id), None)
        
        if slave:
            try:
                balances = slave['client'].futures_account_balance()
                for b in balances:
                    if b['asset'] == 'USDT':
                        u_bal = f"{float(b['balance']):,.2f}"
                        break
            except Exception:
                u_bal = "Помилка"
        
        user_history = TradeHistory.query.filter_by(user_id=current_user.id)\
            .order_by(TradeHistory.close_time.desc()).limit(50).all()
        
        username = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
        if not username:
            username = current_user.username
        
        # Get telegram bot username for user to start chat
        telegram_bot_username = telegram.get_bot_username() if telegram else ""
        
        # Ensure user has a referral code
        if not current_user.referral_code:
            current_user.ensure_referral_code()
            db.session.commit()
        
        # Get referral stats
        referral_stats = current_user.get_referral_stats()
        
        # Build referral link
        referral_link = request.url_root.rstrip('/') + url_for('register') + f"?ref={current_user.referral_code}"
        
        return render_template('dashboard_user.html',
                             username=username,
                             is_active=current_user.is_active and not current_user.is_paused,
                             balance=u_bal,
                             target=current_user.target_balance,
                             user_settings=current_user,
                             global_settings=GLOBAL_TRADE_SETTINGS,
                             history=[h.to_dict() for h in user_history],
                             telegram_bot_username=telegram_bot_username,
                             referral_code=current_user.referral_code,
                             referral_link=referral_link,
                             referral_stats=referral_stats)


@app.route('/update_target', methods=['POST'])
@login_required
def update_target():
    try:
        target = float(request.form.get('target_amount', 1000.0))
        if target < 100:
            flash('Мінімальна ціль - 100 USDT', 'error')
        else:
            current_user.target_balance = target
            db.session.commit()
            flash('Фінансову ціль оновлено', 'success')
    except ValueError:
        flash('Невірний формат числа', 'error')
    return redirect(url_for('dashboard'))


@app.route('/update_telegram', methods=['POST'])
@login_required
def update_telegram():
    """Update user's Telegram settings"""
    try:
        chat_id = request.form.get('telegram_chat_id', '').strip()
        enabled = request.form.get('telegram_enabled') == 'on'
        
        # Validate chat_id format (should be numeric, possibly with minus for groups)
        if chat_id:
            # Remove any non-numeric characters except minus sign
            chat_id_clean = ''.join(c for c in chat_id if c.isdigit() or c == '-')
            if not chat_id_clean or (chat_id_clean != chat_id.replace(' ', '')):
                flash('❌ Невірний формат Chat ID! ID повинен містити тільки цифри (наприклад: 123456789)', 'error')
                return redirect(url_for('dashboard'))
            chat_id = chat_id_clean
        
        if chat_id and enabled:
            # Check if telegram is configured
            if not telegram:
                flash('❌ Telegram бот не налаштований на сервері. Зверніться до адміністратора.', 'error')
                return redirect(url_for('dashboard'))
            
            # Test connection by sending welcome message
            user_display = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.username
            success, error = telegram.test_connection(chat_id, user_display)
            
            if not success:
                bot_username = telegram.get_bot_username()
                bot_link = f'<a href="https://t.me/{bot_username}" target="_blank">@{bot_username}</a>' if bot_username else 'боту'
                id_link = '<a href="https://t.me/userinfobot" target="_blank">@userinfobot</a>'
                
                if error == "chat_not_found":
                    flash(f'❌ Чат не знайдено! Переконайтеся що: 1) Ви написали {bot_link} команду /start, 2) ID правильний (отримайте його через {id_link})', 'error')
                elif error == "bot_blocked":
                    flash(f'❌ Ви заблокували бота! Розблокуйте {bot_link} в Telegram і спробуйте знову.', 'error')
                elif error == "user_deactivated":
                    flash('❌ Акаунт Telegram деактивований. Перевірте свій Telegram.', 'error')
                elif "timeout" in error.lower():
                    flash('❌ Telegram не відповідає. Спробуйте пізніше.', 'error')
                elif "not initialized" in error.lower():
                    flash('❌ Telegram бот не налаштований. Зверніться до адміністратора.', 'error')
                else:
                    flash(f'❌ Помилка підключення: {error}. Перевірте правильність Chat ID.', 'error')
                return redirect(url_for('dashboard'))
            
            # Connection successful - save settings
            current_user.telegram_chat_id = chat_id
            current_user.telegram_enabled = True
            db.session.commit()
            flash('✅ Telegram успішно підключено! Перевірте повідомлення від бота.', 'success')
        elif chat_id and not enabled:
            # Just save chat_id but disable notifications
            current_user.telegram_chat_id = chat_id
            current_user.telegram_enabled = False
            db.session.commit()
            flash('💾 Telegram ID збережено, сповіщення вимкнено.', 'info')
        else:
            # Clear telegram settings
            current_user.telegram_chat_id = None
            current_user.telegram_enabled = False
            db.session.commit()
            flash('🗑️ Telegram налаштування очищено.', 'info')
    except Exception as e:
        logger.error(f"Error updating telegram settings: {e}")
        flash(f'❌ Помилка: Не вдалося зберегти налаштування. Спробуйте пізніше.', 'error')
    return redirect(url_for('dashboard'))


@app.route('/update_email', methods=['POST'])
@login_required
def update_email():
    """Update user's email for password recovery"""
    try:
        new_email = request.form.get('email', '').strip().lower()
        
        if new_email:
            # Validate email format
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', new_email):
                flash('Невірний формат email', 'error')
                return redirect(url_for('dashboard'))
            
            # Check if email already used by another user
            existing = User.query.filter(User.email == new_email, User.id != current_user.id).first()
            if existing:
                flash('Цей email вже використовується іншим користувачем', 'error')
                return redirect(url_for('dashboard'))
            
            current_user.email = new_email
            flash('Email успішно оновлено', 'success')
        else:
            current_user.email = None
            flash('Email видалено', 'info')
        
        db.session.commit()
    except Exception as e:
        flash(f'Помилка: {e}', 'error')
    return redirect(url_for('dashboard'))


# Avatar emoji options for selection (20 fun emojis)
AVATAR_EMOJIS = [
    '🧑‍💻', '🤖', '👽', '🥷', '🦸', '🧙', '👑', '🚀',
    '🔥', '💎', '🦁', '🐯', '🦊', '🐺', '🦄', '🐉',
    '🎭', '🔮', '💰', '🏆',
]


@app.route('/update_avatar', methods=['POST'])
@login_required
def update_avatar():
    """Update user's avatar (emoji or upload)"""
    try:
        avatar_type = request.form.get('avatar_type', 'emoji')
        
        if avatar_type == 'emoji':
            emoji = request.form.get('emoji', '🧑‍💻')
            # Validate emoji is in our allowed list
            if emoji in AVATAR_EMOJIS:
                current_user.avatar = emoji
                current_user.avatar_type = 'emoji'
                db.session.commit()
                flash('Аватар оновлено!', 'success')
            else:
                flash('Невірний вибір аватара', 'error')
        
        elif avatar_type == 'image':
            # Handle file upload
            if 'avatar_file' not in request.files:
                flash('Файл не обрано', 'error')
                return redirect(url_for('dashboard'))
            
            file = request.files['avatar_file']
            if file.filename == '':
                flash('Файл не обрано', 'error')
                return redirect(url_for('dashboard'))
            
            # Validate file type
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            
            if file_ext not in allowed_extensions:
                flash('Дозволені формати: PNG, JPG, GIF, WEBP', 'error')
                return redirect(url_for('dashboard'))
            
            # Check file size (max 2MB)
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            
            if size > 2 * 1024 * 1024:
                flash('Максимальний розмір файлу: 2MB', 'error')
                return redirect(url_for('dashboard'))
            
            # Generate unique filename
            filename = f"avatar_{current_user.id}_{secrets.token_hex(8)}.{file_ext}"
            
            # Ensure avatars directory exists
            avatars_dir = os.path.join(app.static_folder, 'avatars')
            os.makedirs(avatars_dir, exist_ok=True)
            
            # Delete old avatar file if exists
            if current_user.avatar_type == 'image' and current_user.avatar:
                old_file = os.path.join(avatars_dir, current_user.avatar)
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except:
                        pass
            
            # Save new file
            filepath = os.path.join(avatars_dir, filename)
            file.save(filepath)
            
            current_user.avatar = filename
            current_user.avatar_type = 'image'
            db.session.commit()
            flash('Аватар завантажено!', 'success')
        
    except Exception as e:
        logger.error(f"Error updating avatar: {e}")
        flash(f'Помилка: {e}', 'error')
    
    return redirect(url_for('dashboard'))


@app.route('/api/avatar_emojis')
@login_required
def get_avatar_emojis():
    """Return list of available avatar emojis"""
    return jsonify(AVATAR_EMOJIS)


@app.route('/admin/update_user_avatar/<int:user_id>', methods=['POST'])
@login_required
def admin_update_user_avatar(user_id):
    """Admin can update any user's avatar"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ заборонено'}), 403
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'Користувача не знайдено'}), 404
    
    try:
        avatar_type = request.form.get('avatar_type', 'emoji')
        
        if avatar_type == 'emoji':
            emoji = request.form.get('emoji', '🧑‍💻')
            if emoji in AVATAR_EMOJIS:
                user.avatar = emoji
                user.avatar_type = 'emoji'
                db.session.commit()
                return jsonify({'success': True, 'message': 'Аватар оновлено'})
            else:
                return jsonify({'success': False, 'error': 'Невірний емодзі'}), 400
        
        elif avatar_type == 'image':
            if 'avatar_file' not in request.files:
                return jsonify({'success': False, 'error': 'Файл не обрано'}), 400
            
            file = request.files['avatar_file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'Файл не обрано'}), 400
            
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            
            if file_ext not in allowed_extensions:
                return jsonify({'success': False, 'error': 'Дозволено лише PNG, JPG, GIF, WEBP'}), 400
            
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            
            if size > 2 * 1024 * 1024:
                return jsonify({'success': False, 'error': 'Максимальний розмір: 2МБ'}), 400
            
            filename = f"avatar_{user.id}_{secrets.token_hex(8)}.{file_ext}"
            avatars_dir = os.path.join(app.static_folder, 'avatars')
            os.makedirs(avatars_dir, exist_ok=True)
            
            if user.avatar_type == 'image' and user.avatar:
                old_file = os.path.join(avatars_dir, user.avatar)
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except:
                        pass
            
            filepath = os.path.join(avatars_dir, filename)
            file.save(filepath)
            
            user.avatar = filename
            user.avatar_type = 'image'
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Аватар завантажено', 'avatar': filename})
        
        return jsonify({'success': False, 'error': 'Невірний тип аватара'}), 400
        
    except Exception as e:
        logger.error(f"Error updating user avatar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/user/<int:user_id>/details')
@login_required
def get_user_details(user_id):
    """Get detailed user information for admin panel"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ заборонено'}), 403
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'Користувача не знайдено'}), 404
    
    # Get trade statistics
    total_trades = TradeHistory.query.filter_by(user_id=user_id).count()
    winning_trades = TradeHistory.query.filter(TradeHistory.user_id == user_id, TradeHistory.pnl > 0).count()
    losing_trades = TradeHistory.query.filter(TradeHistory.user_id == user_id, TradeHistory.pnl < 0).count()
    total_pnl = db.session.query(db.func.sum(TradeHistory.pnl)).filter(TradeHistory.user_id == user_id).scalar() or 0
    avg_roi = db.session.query(db.func.avg(TradeHistory.roi)).filter(TradeHistory.user_id == user_id).scalar() or 0
    
    # Get last trade
    last_trade = TradeHistory.query.filter_by(user_id=user_id).order_by(TradeHistory.close_time.desc()).first()
    
    # Get current balance from latest balance history
    latest_balance = BalanceHistory.query.filter_by(user_id=user_id).order_by(BalanceHistory.timestamp.desc()).first()
    current_balance = latest_balance.balance if latest_balance else 0
    
    # Get balance from 30 days ago to calculate growth
    from datetime import datetime, timedelta, timezone
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    old_balance = BalanceHistory.query.filter(
        BalanceHistory.user_id == user_id,
        BalanceHistory.timestamp <= thirty_days_ago
    ).order_by(BalanceHistory.timestamp.desc()).first()
    
    balance_growth = 0
    if old_balance and old_balance.balance > 0:
        balance_growth = ((current_balance - old_balance.balance) / old_balance.balance) * 100
    
    # Days since registration
    days_registered = 0
    if user.created_at:
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_registered = (datetime.now(timezone.utc) - created).days
    
    # Get exchange info with balances
    exchanges = UserExchange.query.filter_by(user_id=user_id).all()
    exchange_balances = get_user_exchange_balances(user_id)
    balance_map = {b['id']: b for b in exchange_balances['exchanges']}
    
    # Get display names
    configs = {c.exchange_name: c.display_name for c in ExchangeConfig.query.all()}
    
    # Check if user has API keys configured (legacy)
    has_api_keys = bool(user.api_key_enc and user.api_secret_enc)
    
    # Use live total balance from exchanges if available
    live_total_balance = exchange_balances['total'] if exchange_balances['total'] > 0 else current_balance
    
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'avatar': user.avatar,
            'avatar_type': user.avatar_type,
            'is_active': user.is_active,
            'is_paused': user.is_paused,
            'role': user.role,
            'target_balance': user.target_balance,
            'custom_risk': user.custom_risk,
            'custom_leverage': user.custom_leverage,
            'max_positions': user.max_positions,
            'telegram_enabled': user.telegram_enabled,
            'telegram_chat_id': user.telegram_chat_id,
            'created_at': user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else None,
            'days_registered': days_registered,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round((winning_trades / total_trades * 100) if total_trades > 0 else 0, 1),
            'total_pnl': round(total_pnl, 2),
            'avg_roi': round(avg_roi, 2),
            'current_balance': round(live_total_balance, 2),
            'balance_growth_30d': round(balance_growth, 2),
            'last_trade': {
                'symbol': last_trade.symbol,
                'side': last_trade.side,
                'pnl': round(last_trade.pnl, 2),
                'time': last_trade.close_time.strftime('%d.%m %H:%M') if last_trade.close_time else None
            } if last_trade else None,
            'has_api_keys': has_api_keys,
            'exchanges': [{
                'id': ex.id,
                'exchange_name': ex.exchange_name,
                'display_name': configs.get(ex.exchange_name, ex.exchange_name.upper()),
                'label': ex.label,
                'status': ex.status,
                'trading_enabled': ex.trading_enabled,
                'is_active': ex.is_active,
                'balance': balance_map.get(ex.id, {}).get('balance'),
                'balance_error': balance_map.get(ex.id, {}).get('error'),
                'created_at': ex.created_at.strftime('%d.%m.%Y') if ex.created_at else None
            } for ex in exchanges]
        }
    })


@app.route('/api/admin/user/<int:user_id>/delete', methods=['POST', 'DELETE'])
@login_required
def admin_delete_user(user_id):
    """Delete a user and all their data (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ заборонено'}), 403
    
    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Неможливо видалити себе'}), 400
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'Користувача не знайдено'}), 404
    
    # Prevent deleting other admins
    if user.role == 'admin':
        return jsonify({'success': False, 'error': 'Неможливо видалити адміністраторів'}), 400
    
    try:
        username = user.username
        
        # Delete user's avatar file if exists
        if user.avatar_type == 'image' and user.avatar:
            avatar_path = os.path.join(app.static_folder, 'avatars', user.avatar)
            if os.path.exists(avatar_path):
                try:
                    os.remove(avatar_path)
                except:
                    pass
        
        # Delete related data (cascades should handle most of this)
        # Delete user exchanges
        UserExchange.query.filter_by(user_id=user_id).delete()
        
        # Delete trade history
        TradeHistory.query.filter_by(user_id=user_id).delete()
        
        # Delete balance history
        BalanceHistory.query.filter_by(user_id=user_id).delete()
        
        # Delete messages (sent and received)
        Message.query.filter((Message.sender_id == user_id) | (Message.recipient_id == user_id)).delete()
        
        # Delete password reset tokens
        PasswordResetToken.query.filter_by(user_id=user_id).delete()
        
        # Finally delete the user
        db.session.delete(user)
        db.session.commit()
        
        logger.info(f"🗑️ Admin {current_user.username} deleted user {username} (ID: {user_id})")
        
        return jsonify({
            'success': True,
            'message': f'User {username} has been deleted'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user {user_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/user/panic')
@login_required
def user_panic():
    """Emergency close all positions for user"""
    if current_user.role == 'admin':
        return redirect(url_for('dashboard'))
    
    engine.close_all_for_user(current_user.id)
    flash('🚨 Команду на закриття всіх позицій відправлено!', 'warning')
    return redirect(url_for('dashboard'))


@app.route('/admin/panic')
@login_required
def admin_panic():
    """Emergency close all positions for ALL accounts (admin only)"""
    if current_user.role != 'admin':
        flash('⛔ Доступ заборонено!', 'error')
        return redirect(url_for('dashboard'))
    
    results = engine.close_all_positions_all_accounts()
    
    flash(f'🚨 ГЛОБАЛЬНЕ ЗАКРИТТЯ: Master={results["master_closed"]} позицій, Slaves={results["slaves_closed"]} акаунтів оброблено!', 'warning')
    return redirect(url_for('dashboard'))


@app.route('/api/admin/panic', methods=['POST'])
@login_required
def api_admin_panic():
    """API endpoint for admin panic close"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ заборонено'}), 403
    
    try:
        results = engine.close_all_positions_all_accounts()
        return jsonify({
            'success': True,
            'master_closed': results['master_closed'],
            'slaves_closed': results['slaves_closed'],
            'errors': results['errors']
        })
    except Exception as e:
        logger.error(f"API Panic error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== API ROUTES ====================

@app.route('/api/balance_history', methods=['GET'])
@login_required
def get_balance_history():
    """Get balance history for charts with time period support"""
    target_user_id = current_user.id
    
    if current_user.role == 'admin':
        req_id = request.args.get('user_id')
        if req_id == 'master':
            target_user_id = None
        elif req_id:
            try:
                target_user_id = int(req_id)
            except ValueError:
                pass
    
    # Get period parameter (default: 24h)
    period = request.args.get('period', '24h')
    period_map = {
        '24h': timedelta(hours=24),
        'week': timedelta(days=7),
        'month': timedelta(days=30),
        'quarter': timedelta(days=90),
        'year': timedelta(days=365)
    }
    delta = period_map.get(period, timedelta(hours=24))
    
    since = datetime.now(timezone.utc) - delta
    query = BalanceHistory.query.filter(BalanceHistory.timestamp >= since)
    
    if target_user_id is None:
        query = query.filter(BalanceHistory.user_id == None)
    else:
        query = query.filter(BalanceHistory.user_id == target_user_id)
    
    history = query.order_by(BalanceHistory.timestamp.asc()).all()
    
    # Time format based on period
    if period == '24h':
        time_fmt = '%H:%M'
    elif period == 'week':
        time_fmt = '%d/%m %H:%M'
    else:
        time_fmt = '%d/%m'
    
    data = [{
        'time': h.timestamp.strftime(time_fmt),
        'balance': h.balance
    } for h in history]
    
    return jsonify(data)


@app.route('/api/master_stats', methods=['GET'])
@login_required
def get_master_stats():
    """Get master trading statistics for different periods"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Доступ заборонено'}), 403
    
    # Get period parameter
    period = request.args.get('period', '24h')
    period_map = {
        '24h': timedelta(hours=24),
        'week': timedelta(days=7),
        'month': timedelta(days=30),
        'quarter': timedelta(days=90),
        'year': timedelta(days=365)
    }
    delta = period_map.get(period, timedelta(hours=24))
    since = datetime.now(timezone.utc) - delta
    
    # Get trades for period (master trades have user_id = None)
    trades = TradeHistory.query.filter(
        TradeHistory.close_time >= since,
        TradeHistory.user_id == None
    ).all()
    
    total_pnl = sum(t.pnl for t in trades) if trades else 0
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t.pnl > 0])
    
    # Calculate average ROI
    avg_roi = sum(t.roi for t in trades) / len(trades) if trades else 0
    
    # Get balance history for ROI calculation
    balance_history = BalanceHistory.query.filter(
        BalanceHistory.timestamp >= since,
        BalanceHistory.user_id == None
    ).order_by(BalanceHistory.timestamp.asc()).all()
    
    # Calculate ROI based on starting balance
    period_roi = 0
    if balance_history and len(balance_history) >= 2:
        start_balance = balance_history[0].balance
        end_balance = balance_history[-1].balance
        if start_balance > 0:
            period_roi = ((end_balance - start_balance) / start_balance) * 100
    
    return jsonify({
        'period': period,
        'total_pnl': round(total_pnl, 2),
        'period_roi': round(period_roi, 2),
        'avg_roi': round(avg_roi, 2),
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': round((winning_trades / total_trades * 100) if total_trades > 0 else 0, 1)
    })


@app.route('/api/master/exchange_balances', methods=['GET'])
@login_required
def get_master_exchange_balances():
    """Get balances from all master exchanges (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Доступ заборонено'}), 403
    
    try:
        balances = engine.get_all_master_balances()
        total_balance = sum(b['balance'] for b in balances if b['balance'] is not None)
        
        return jsonify({
            'success': True,
            'exchanges': balances,
            'total_balance': round(total_balance, 2)
        })
    except Exception as e:
        logger.error(f"Error fetching master exchange balances: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/master/positions', methods=['GET'])
@login_required
def get_master_positions():
    """Get positions from all master exchanges (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Доступ заборонено'}), 403
    
    try:
        positions = engine.get_all_master_positions()
        return jsonify({
            'success': True,
            'positions': positions,
            'count': len(positions)
        })
    except Exception as e:
        logger.error(f"Error fetching master positions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/positions', methods=['GET'])
@login_required
def get_user_positions():
    """
    Get open positions for the current user.
    Returns HTML partial for HTMX or JSON based on Accept header.
    This endpoint is polled by HTMX every 2 seconds for real-time updates.
    """
    try:
        positions_data = []
        
        if current_user.role == 'admin':
            # Admin sees master positions
            positions_data = engine.get_all_master_positions()
        else:
            # Regular user - find their slave clients and get positions
            for slave in engine.slave_clients:
                if slave['id'] == current_user.id:
                    try:
                        client = slave['client']
                        positions_info = client.futures_position_information()
                        
                        for p in positions_info:
                            amt = float(p['positionAmt'])
                            if amt != 0:
                                positions_data.append({
                                    'symbol': p['symbol'],
                                    'amount': amt,
                                    'entry_price': float(p['entryPrice']),
                                    'unrealized_pnl': float(p['unRealizedProfit']),
                                    'side': 'LONG' if amt > 0 else 'SHORT',
                                    'leverage': int(p.get('leverage', 1)),
                                    'exchange': slave.get('exchange_name', 'binance').upper()
                                })
                    except Exception as e:
                        logger.warning(f"Error fetching positions for user {current_user.id}: {e}")
                    break
        
        # Check if HTMX request (return HTML partial)
        if request.headers.get('HX-Request'):
            if not positions_data:
                return '''
                <div class="empty-positions">
                    <div class="icon"><i class="fas fa-inbox"></i></div>
                    <div class="text">No open positions</div>
                </div>
                '''
            
            html_parts = []
            for p in positions_data:
                pnl_class = 'positive' if p['unrealized_pnl'] >= 0 else 'negative'
                pnl_sign = '+' if p['unrealized_pnl'] >= 0 else ''
                side_class = 'long' if p['side'] == 'LONG' else 'short'
                arrow = 'arrow-trend-up' if p['side'] == 'LONG' else 'arrow-trend-down'
                symbol = html.escape(p.get('symbol', ''))
                side_label = html.escape(p.get('side', ''))
                exchange_label = html.escape(p.get('exchange', '')) if p.get('exchange') else ''
                
                html_parts.append(f'''
                <div class="position-card">
                    <div class="position-info">
                        <div class="side-badge {side_class}">
                            <i class="fas fa-{arrow}"></i>
                        </div>
                        <div>
                            <div class="symbol">{symbol}</div>
                            <div class="details">{side_label} · x{p['leverage']}{' · ' + exchange_label if exchange_label else ''}</div>
                        </div>
                    </div>
                    <div class="pnl">
                        <div class="pnl-value {pnl_class}">{pnl_sign}{p['unrealized_pnl']:.2f}$</div>
                        <div class="entry-price">${p['entry_price']:.4f}</div>
                    </div>
                </div>
                ''')
            
            return ''.join(html_parts)
        
        # Return JSON for non-HTMX requests
        return jsonify({
            'success': True,
            'positions': positions_data,
            'count': len(positions_data)
        })
        
    except Exception as e:
        logger.error(f"Error fetching user positions: {e}")
        if request.headers.get('HX-Request'):
            return '''
            <div class="empty-positions">
                <div class="icon"><i class="fas fa-exclamation-triangle" style="color: var(--neon-red);"></i></div>
                <div class="text" style="color: var(--neon-red);">Error loading positions</div>
            </div>
            '''
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user_stats', methods=['GET'])
@login_required
def get_user_stats():
    """Get user trading statistics for different periods"""
    # Get period parameter
    period = request.args.get('period', '24h')
    period_map = {
        '24h': timedelta(hours=24),
        'week': timedelta(days=7),
        'month': timedelta(days=30),
        'quarter': timedelta(days=90),
        'year': timedelta(days=365)
    }
    delta = period_map.get(period, timedelta(hours=24))
    since = datetime.now(timezone.utc) - delta
    
    # Get trades for period for current user
    trades = TradeHistory.query.filter(
        TradeHistory.close_time >= since,
        TradeHistory.user_id == current_user.id
    ).all()
    
    total_pnl = sum(t.pnl for t in trades) if trades else 0
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t.pnl > 0])
    
    # Calculate average ROI
    avg_roi = sum(t.roi for t in trades) / len(trades) if trades else 0
    
    # Get balance history for ROI calculation
    balance_history = BalanceHistory.query.filter(
        BalanceHistory.timestamp >= since,
        BalanceHistory.user_id == current_user.id
    ).order_by(BalanceHistory.timestamp.asc()).all()
    
    # Calculate ROI based on starting balance
    period_roi = 0
    if balance_history and len(balance_history) >= 2:
        start_balance = balance_history[0].balance
        end_balance = balance_history[-1].balance
        if start_balance > 0:
            period_roi = ((end_balance - start_balance) / start_balance) * 100
    
    return jsonify({
        'period': period,
        'total_pnl': round(total_pnl, 2),
        'period_roi': round(period_roi, 2),
        'avg_roi': round(avg_roi, 2),
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': round((winning_trades / total_trades * 100) if total_trades > 0 else 0, 1)
    })


@app.route('/api/referral_stats', methods=['GET'])
@login_required
def get_referral_stats():
    """Get user's referral statistics and commissions"""
    from models import ReferralCommission
    
    # Get basic stats
    stats = current_user.get_referral_stats()
    
    # Get recent commissions
    recent_commissions = ReferralCommission.query.filter_by(
        referrer_id=current_user.id
    ).order_by(ReferralCommission.created_at.desc()).limit(20).all()
    
    # Get referral list with basic info
    referrals = []
    for ref in current_user.referrals.limit(50).all():
        referrals.append({
            'username': ref.username,
            'first_name': ref.first_name,
            'joined': ref.created_at.strftime("%d.%m.%Y") if ref.created_at else None,
            'is_active': ref.is_active
        })
    
    return jsonify({
        'success': True,
        'referral_code': current_user.referral_code,
        'stats': stats,
        'referrals': referrals,
        'recent_commissions': [c.to_dict() for c in recent_commissions]
    })


# ==================== INFLUENCER DASHBOARD ====================

@app.route('/influencer')
@login_required
def influencer_dashboard():
    """
    Influencer/Partner Dashboard.
    
    Provides:
    - Detailed statistics (clicks, registrations, deposits, commissions)
    - Earnings chart over time
    - Marketing assets with dynamic banners
    - Payout request functionality
    """
    from models import ReferralCommission, ReferralClick, PayoutRequest
    from banner_generator import get_banner_types, get_platform_top_apy
    
    # Ensure user has a referral code
    if not current_user.referral_code:
        current_user.ensure_referral_code()
        db.session.commit()
    
    # Get referral stats
    referral_stats = current_user.get_referral_stats()
    
    # Get click stats
    try:
        click_stats = ReferralClick.get_referrer_stats(current_user.id)
    except Exception:
        click_stats = {
            'total_clicks': 0,
            'unique_visitors': 0,
            'registrations': 0,
            'deposits': 0,
            'total_deposit_amount': 0,
            'click_to_registration_rate': 0,
            'registration_to_deposit_rate': 0,
        }
    
    # Build referral link
    referral_link = request.url_root.rstrip('/') + url_for('register') + f"?ref={current_user.referral_code}"
    
    # Get referral list
    referrals = []
    for ref in current_user.referrals.order_by(User.created_at.desc()).limit(50).all():
        referrals.append({
            'username': ref.username,
            'first_name': ref.first_name,
            'joined': ref.created_at.strftime("%d %b %Y") if ref.created_at else None,
            'is_active': ref.is_active
        })
    
    # Get recent commissions
    recent_commissions = ReferralCommission.query.filter_by(
        referrer_id=current_user.id
    ).order_by(ReferralCommission.created_at.desc()).limit(20).all()
    
    # Check for pending payout request
    pending_payout = PayoutRequest.query.filter_by(
        user_id=current_user.id,
        status='pending'
    ).first()
    
    # Get payout history
    payout_history = [p.to_dict() for p in PayoutRequest.get_user_requests(current_user.id, limit=20)]
    
    # Get banner types
    banner_types = get_banner_types()
    
    return render_template('influencer.html',
                           referral_code=current_user.referral_code,
                           referral_link=referral_link,
                           referral_stats=referral_stats,
                           click_stats=click_stats,
                           referrals=referrals,
                           recent_commissions=[c.to_dict() for c in recent_commissions],
                           pending_payout=pending_payout,
                           payout_history=payout_history,
                           banner_types=banner_types)


@app.route('/r/<code>')
def track_referral_click(code):
    """
    Track referral link clicks and redirect to registration.
    
    URL format: /r/CODE?utm_source=...&utm_medium=...&utm_campaign=...
    """
    from models import ReferralClick
    
    # Find the referrer
    referrer = User.query.filter_by(referral_code=code.upper().strip()).first()
    
    if referrer:
        # Record the click
        try:
            ReferralClick.record_click(
                referrer_id=referrer.id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                referer_url=request.headers.get('Referer'),
                utm_source=request.args.get('utm_source'),
                utm_medium=request.args.get('utm_medium'),
                utm_campaign=request.args.get('utm_campaign'),
            )
        except Exception as e:
            logger.warning(f"Failed to record referral click: {e}")
    
    # Redirect to registration with referral code
    return redirect(url_for('register', ref=code))


@app.route('/api/influencer/earnings-chart', methods=['GET'])
@login_required
def get_earnings_chart():
    """
    Get earnings chart data for the influencer dashboard.
    
    Query params:
        days: Number of days to show (default 30)
        
    Returns:
        JSON with labels, daily_commission, and cumulative arrays
    """
    from models import ReferralCommission
    from sqlalchemy import func
    from datetime import timedelta
    
    days = min(int(request.args.get('days', 30)), 365)  # Max 1 year
    
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Query daily commission totals
    daily_data = db.session.query(
        func.date(ReferralCommission.created_at).label('date'),
        func.sum(ReferralCommission.amount).label('total')
    ).filter(
        ReferralCommission.referrer_id == current_user.id,
        ReferralCommission.created_at >= start_date
    ).group_by(
        func.date(ReferralCommission.created_at)
    ).order_by(
        func.date(ReferralCommission.created_at)
    ).all()
    
    # Create a dict of date -> amount
    daily_dict = {str(d.date): float(d.total or 0) for d in daily_data}
    
    # Generate labels for each day
    labels = []
    daily_commission = []
    cumulative = []
    running_total = 0
    
    for i in range(days):
        date = start_date + timedelta(days=i + 1)
        date_str = date.strftime('%Y-%m-%d')
        labels.append(date.strftime('%d %b'))
        
        amount = daily_dict.get(date_str, 0)
        daily_commission.append(round(amount, 2))
        
        running_total += amount
        cumulative.append(round(running_total, 2))
    
    return jsonify({
        'success': True,
        'labels': labels,
        'daily_commission': daily_commission,
        'cumulative': cumulative,
        'period_total': round(running_total, 2)
    })


@app.route('/api/influencer/banner/<banner_type>')
@login_required  
def get_banner(banner_type):
    """
    Generate and serve a promotional banner.
    
    Args:
        banner_type: One of 'landscape', 'square', 'story', 'leaderboard', 'sidebar'
        
    Returns:
        PNG image with user's referral code and stats
    """
    from banner_generator import generate_banner, get_platform_top_apy, get_user_trading_stats
    from flask import make_response
    
    # Ensure user has referral code
    if not current_user.referral_code:
        current_user.ensure_referral_code()
        db.session.commit()
    
    # Get user's trading stats
    trading_stats = get_user_trading_stats(current_user.id)
    
    # Get referral stats
    referral_stats = current_user.get_referral_stats()
    
    # Get platform top APY
    top_apy = get_platform_top_apy()
    
    # Generate banner
    banner_bytes = generate_banner(
        banner_type=banner_type,
        referral_code=current_user.referral_code,
        username=current_user.username,
        total_pnl=trading_stats['total_pnl'],
        total_roi=trading_stats['total_roi'],
        top_apy=top_apy,
        referral_count=referral_stats['referral_count'],
        total_commission=referral_stats['total_commission'],
    )
    
    if banner_bytes:
        response = make_response(banner_bytes)
        response.headers['Content-Type'] = 'image/png'
        response.headers['Content-Disposition'] = f'inline; filename=mimic-banner-{banner_type}.png'
        response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        return response
    else:
        return jsonify({'error': 'Не вдалося згенерувати банер'}), 500


@app.route('/api/influencer/payout-request', methods=['POST'])
@login_required
def request_payout():
    """
    Submit a payout request for referral commissions.
    
    Request body:
        amount: Amount to withdraw (min $50)
        payment_method: One of 'usdt_trc20', 'usdt_erc20', 'usdt_bep20', 'btc', 'bank_transfer'
        payment_address: Crypto wallet address or bank details
        
    Returns:
        JSON with success status and request details
    """
    from models import PayoutRequest
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Дані не надано'}), 400
        
        amount = float(data.get('amount', 0))
        payment_method = data.get('payment_method', '').strip()
        payment_address = data.get('payment_address', '').strip()
        
        # Validate inputs
        if not payment_method:
            return jsonify({'success': False, 'error': 'Потрібен метод оплати'}), 400
        
        if not payment_address:
            return jsonify({'success': False, 'error': 'Потрібна адреса платежу'}), 400
        
        # Create payout request
        payout = PayoutRequest.create_request(
            user_id=current_user.id,
            amount=amount,
            payment_method=payment_method,
            payment_address=payment_address
        )
        
        # Send notification to admin (optional - via Telegram)
        try:
            notifier = get_notifier()
            if notifier:
                notifier.send(
                    f"💰 <b>NEW PAYOUT REQUEST</b>\n\n"
                    f"👤 User: <code>{current_user.username}</code>\n"
                    f"💵 Amount: <code>${amount:.2f}</code>\n"
                    f"💳 Method: <code>{payment_method}</code>\n"
                    f"📝 Address: <code>{payment_address[:30]}...</code>\n\n"
                    f"Review at: /admin/payouts"
                )
        except Exception as e:
            logger.warning(f"Failed to send payout notification: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Payout request submitted successfully',
            'payout': payout.to_dict()
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Payout request error: {e}")
        return jsonify({'success': False, 'error': 'Не вдалося створити запит на виплату'}), 500


@app.route('/api/influencer/daily-stats', methods=['GET'])
@login_required
def get_daily_referral_stats():
    """
    Get daily referral statistics for the influencer dashboard.
    
    Complex SQL aggregation of:
    - Daily clicks
    - Daily registrations
    - Daily commissions
    
    Query params:
        days: Number of days (default 30)
        
    Returns:
        JSON with daily breakdown
    """
    from models import ReferralCommission, ReferralClick
    from sqlalchemy import func
    from datetime import timedelta
    
    days = min(int(request.args.get('days', 30)), 365)
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Daily clicks
    clicks_query = db.session.query(
        func.date(ReferralClick.created_at).label('date'),
        func.count(ReferralClick.id).label('clicks'),
        func.count(func.distinct(ReferralClick.ip_hash)).label('unique_clicks'),
        func.sum(func.cast(ReferralClick.converted, db.Integer)).label('conversions')
    ).filter(
        ReferralClick.referrer_id == current_user.id,
        ReferralClick.created_at >= start_date
    ).group_by(func.date(ReferralClick.created_at)).all()
    
    # Daily commissions
    commissions_query = db.session.query(
        func.date(ReferralCommission.created_at).label('date'),
        func.sum(ReferralCommission.amount).label('commission'),
        func.count(ReferralCommission.id).label('commission_count')
    ).filter(
        ReferralCommission.referrer_id == current_user.id,
        ReferralCommission.created_at >= start_date
    ).group_by(func.date(ReferralCommission.created_at)).all()
    
    # Merge into daily stats
    clicks_dict = {str(d.date): {'clicks': d.clicks, 'unique': d.unique_clicks, 'conversions': d.conversions or 0} 
                   for d in clicks_query}
    commissions_dict = {str(d.date): {'commission': float(d.commission or 0), 'count': d.commission_count} 
                        for d in commissions_query}
    
    daily_stats = []
    for i in range(days):
        date = start_date + timedelta(days=i + 1)
        date_str = date.strftime('%Y-%m-%d')
        
        clicks_data = clicks_dict.get(date_str, {'clicks': 0, 'unique': 0, 'conversions': 0})
        comm_data = commissions_dict.get(date_str, {'commission': 0, 'count': 0})
        
        daily_stats.append({
            'date': date_str,
            'clicks': clicks_data['clicks'],
            'unique_clicks': clicks_data['unique'],
            'conversions': clicks_data['conversions'],
            'commission': round(comm_data['commission'], 2),
            'commission_count': comm_data['count']
        })
    
    return jsonify({
        'success': True,
        'daily_stats': daily_stats
    })


# ==================== GAMIFICATION API ====================

@app.route('/api/gamification/status', methods=['GET'])
@login_required
def get_gamification_status():
    """
    Get current user's gamification status including level, XP, and badges.
    
    Returns:
        JSON with level info, XP progress, and unlocked badges
    """
    try:
        # Ensure levels exist
        UserLevel.initialize_default_levels()
        
        # Get gamification summary for current user
        summary = current_user.get_gamification_summary()
        
        return jsonify({
            'success': True,
            **summary
        })
    except Exception as e:
        logger.error(f"Error getting gamification status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gamification/levels', methods=['GET'])
def get_all_levels():
    """
    Get all available levels and their requirements (public endpoint).
    
    Returns:
        JSON with all level definitions
    """
    try:
        # Ensure levels exist
        UserLevel.initialize_default_levels()
        
        levels = UserLevel.query.order_by(UserLevel.order_rank.asc()).all()
        
        return jsonify({
            'success': True,
            'levels': [level.to_dict() for level in levels]
        })
    except Exception as e:
        logger.error(f"Error getting levels: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gamification/achievements', methods=['GET'])
@login_required
def get_achievements():
    """
    Get user's unlocked achievements and all possible achievements.
    
    Returns:
        JSON with unlocked badges and available achievements
    """
    try:
        # Get unlocked achievements for current user
        unlocked = current_user.get_unlocked_badges()
        unlocked_types = {a['achievement_type'] for a in unlocked}
        
        # Get all possible achievements
        all_achievements = []
        for achievement_type, data in UserAchievement.ACHIEVEMENTS.items():
            all_achievements.append({
                'type': achievement_type,
                'name': data['name'],
                'description': data['description'],
                'icon': data['icon'],
                'color': data['color'],
                'rarity': data['rarity'],
                'unlocked': achievement_type in unlocked_types
            })
        
        return jsonify({
            'success': True,
            'unlocked': unlocked,
            'all_achievements': all_achievements,
            'total_unlocked': len(unlocked),
            'total_available': len(all_achievements)
        })
    except Exception as e:
        logger.error(f"Error getting achievements: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gamification/leaderboard', methods=['GET'])
def get_gamification_leaderboard():
    """
    Get top users by XP (public endpoint with limited info).
    
    Query params:
        limit: Number of users to return (default 10, max 50)
    
    Returns:
        JSON with top users by XP
    """
    try:
        limit = min(int(request.args.get('limit', 10)), 50)

        cache_key = f"gamification_leaderboard:{limit}"
        data = get_public_stats_cached(cache_key, lambda: _compute_gamification_leaderboard(limit))
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting gamification leaderboard: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gamification/check_achievements', methods=['POST'])
@login_required
def check_user_achievements():
    """
    Manually trigger achievement check for current user.
    
    Returns:
        JSON with any newly unlocked achievements
    """
    try:
        new_achievements = UserAchievement.check_and_unlock(current_user.id)
        
        return jsonify({
            'success': True,
            'new_achievements': [a.to_dict() for a in new_achievements],
            'count': len(new_achievements)
        })
    except Exception as e:
        logger.error(f"Error checking achievements: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/gamification/stats', methods=['GET'])
@login_required
def admin_gamification_stats():
    """
    Admin endpoint: Get overall gamification statistics.
    
    Returns:
        JSON with level distribution, achievement stats, etc.
    """
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        def _compute_stats():
            from sqlalchemy import func
            
            # Users by level
            level_distribution = db.session.query(
                UserLevel.name,
                UserLevel.color,
                func.count(User.id)
            ).outerjoin(User, User.current_level_id == UserLevel.id).filter(
                User.role == 'user'
            ).group_by(UserLevel.id).order_by(UserLevel.order_rank).all()
            
            # Achievement stats
            achievement_stats = db.session.query(
                UserAchievement.achievement_type,
                UserAchievement.name,
                func.count(UserAchievement.id)
            ).group_by(UserAchievement.achievement_type).order_by(
                func.count(UserAchievement.id).desc()
            ).all()
            
            # Total XP across platform
            total_xp = db.session.query(func.sum(User.xp)).filter(User.role == 'user').scalar() or 0
            
            # Average XP
            avg_xp = db.session.query(func.avg(User.xp)).filter(User.role == 'user').scalar() or 0
            
            return {
                'success': True,
                'level_distribution': [
                    {'name': name, 'color': color, 'count': count}
                    for name, color, count in level_distribution
                ],
                'achievement_stats': [
                    {'type': t, 'name': n, 'count': c}
                    for t, n, c in achievement_stats
                ],
                'total_xp_platform': int(total_xp),
                'average_xp': round(float(avg_xp), 1),
                'total_achievements_unlocked': UserAchievement.query.count()
            }
        
        data = get_admin_stats_cached('gamification_stats', _compute_stats)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting admin gamification stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/gamification/recalculate', methods=['POST'])
@login_required
def admin_recalculate_xp():
    """
    Admin endpoint: Trigger XP recalculation for all users.
    
    Returns:
        JSON with recalculation results
    """
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from sqlalchemy import func
        
        # Ensure levels exist
        UserLevel.initialize_default_levels()
        
        users_updated = 0
        levels_changed = 0
        
        # Get all users
        users = User.query.filter(User.role == 'user').all()
        
        for user in users:
            # Calculate new XP
            new_xp = user.calculate_xp()
            old_level_id = user.current_level_id
            
            # Update XP and level
            user.xp = new_xp
            new_level, leveled_up = user.update_xp_and_level(new_xp)
            
            users_updated += 1
            if leveled_up:
                levels_changed += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'users_updated': users_updated,
            'levels_changed': levels_changed,
            'message': f'Recalculated XP for {users_updated} users, {levels_changed} level changes'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error recalculating XP: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ADMIN PLATFORM STATS ====================

@app.route('/api/admin/referral-stats', methods=['GET'])
@login_required
def admin_referral_stats():
    """Get admin referral and payout statistics"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        def _compute_stats():
            from models import ReferralCommission, PayoutRequest
            from sqlalchemy import func
            
            # Total referrals (users who have referred_by_id set)
            total_referrals = User.query.filter(User.referred_by_id.isnot(None)).count()
            
            # Total commissions earned
            total_commissions = db.session.query(func.coalesce(func.sum(ReferralCommission.amount), 0.0)).scalar()
            
            # Pending payouts (unpaid commissions)
            pending_payouts = db.session.query(func.coalesce(func.sum(ReferralCommission.amount), 0.0))\
                .filter(ReferralCommission.is_paid == False).scalar()
            
            # Pending payout requests
            pending_requests = PayoutRequest.query.filter_by(status='pending').count()
            
            return {
                'success': True,
                'total_referrals': total_referrals,
                'total_commissions': float(total_commissions or 0),
                'pending_payouts': float(pending_payouts or 0),
                'pending_requests': pending_requests
            }
        
        data = get_admin_stats_cached('referral_stats', _compute_stats)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting admin referral stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/subscription-stats', methods=['GET'])
@login_required
def admin_subscription_stats():
    """Get admin subscription statistics"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        def _compute_stats():
            from datetime import datetime, timezone
            
            # Count premium users (non-free, non-expired subscriptions)
            now = datetime.now(timezone.utc)
            
            premium_count = User.query.filter(
                User.subscription_plan != 'free',
                User.subscription_plan.isnot(None),
                db.or_(
                    User.subscription_expires_at.is_(None),  # Lifetime subscriptions
                    User.subscription_expires_at > now  # Active subscriptions
                )
            ).count()
            
            # Count by plan
            plan_counts = db.session.query(User.subscription_plan, db.func.count(User.id))\
                .filter(User.role == 'user')\
                .group_by(User.subscription_plan).all()
            
            plans = {plan: count for plan, count in plan_counts if plan}
            
            return {
                'success': True,
                'premium_count': premium_count,
                'plans': plans,
                'total_users': User.query.filter(User.role == 'user').count()
            }
        
        data = get_admin_stats_cached('subscription_stats', _compute_stats)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting admin subscription stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SUBSCRIPTION MANAGEMENT ====================

@app.route('/api/admin/subscription-settings', methods=['GET'])
@login_required
def get_subscription_settings():
    """Get subscription settings for admin panel"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import SystemSetting
        
        # Get subscription settings
        subscription_settings = SystemSetting.get_category_settings('subscription')
        wallet_settings = SystemSetting.get_category_settings('wallet')
        insurance_settings = SystemSetting.get_category_settings('insurance_fund')
        
        # Get subscription plans from config
        plans = []
        for plan_id, plan_data in Config.SUBSCRIPTION_PLANS.items():
            plans.append({
                'id': plan_id,
                'name': plan_data['name'],
                'price': plan_data['price'],
                'days': plan_data['days']
            })
        
        return jsonify({
            'success': True,
            'subscription': {
                'enabled': subscription_settings.get('enabled', 'false').lower() == 'true',
                'auto_confirm': subscription_settings.get('auto_confirm', 'false').lower() == 'true',
                'confirm_timeout_hours': int(subscription_settings.get('confirm_timeout_hours', '24')),
                'default_days': int(subscription_settings.get('default_days', '30'))
            },
            'wallets': {
                'usdt_trc20': wallet_settings.get('usdt_trc20', ''),
                'usdt_erc20': wallet_settings.get('usdt_erc20', ''),
                'usdt_bep20': wallet_settings.get('usdt_bep20', ''),
                'btc': wallet_settings.get('btc', ''),
                'eth': wallet_settings.get('eth', ''),
                'ltc': wallet_settings.get('ltc', ''),
                'sol': wallet_settings.get('sol', '')
            },
            'insurance_fund': {
                'wallet_address': insurance_settings.get('wallet_address', ''),
                'wallet_network': insurance_settings.get('wallet_network', 'USDT_TRC20'),
                'contribution_rate': float(insurance_settings.get('contribution_rate', '5'))
            },
            'plans': plans
        })
    except Exception as e:
        logger.error(f"Error getting subscription settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/subscription-settings', methods=['POST'])
@login_required
def update_subscription_settings():
    """Update subscription settings from admin panel"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import SystemSetting
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Дані не надано'}), 400
        
        updated = []
        
        # Update subscription settings
        if 'subscription' in data:
            sub_data = data['subscription']
            if 'enabled' in sub_data:
                SystemSetting.set_setting('subscription', 'enabled', str(sub_data['enabled']).lower())
                updated.append('subscription.enabled')
            if 'auto_confirm' in sub_data:
                SystemSetting.set_setting('subscription', 'auto_confirm', str(sub_data['auto_confirm']).lower())
                updated.append('subscription.auto_confirm')
            if 'confirm_timeout_hours' in sub_data:
                SystemSetting.set_setting('subscription', 'confirm_timeout_hours', str(sub_data['confirm_timeout_hours']))
                updated.append('subscription.confirm_timeout_hours')
            if 'default_days' in sub_data:
                SystemSetting.set_setting('subscription', 'default_days', str(sub_data['default_days']))
                updated.append('subscription.default_days')
        
        # Update wallet settings
        if 'wallets' in data:
            for network, address in data['wallets'].items():
                if network in ['usdt_trc20', 'usdt_erc20', 'usdt_bep20', 'btc', 'eth', 'ltc', 'sol']:
                    SystemSetting.set_setting('wallet', network, address or '')
                    updated.append(f'wallet.{network}')
        
        # Update insurance fund settings
        if 'insurance_fund' in data:
            ins_data = data['insurance_fund']
            if 'wallet_address' in ins_data:
                SystemSetting.set_setting('insurance_fund', 'wallet_address', ins_data['wallet_address'] or '')
                updated.append('insurance_fund.wallet_address')
            if 'wallet_network' in ins_data:
                SystemSetting.set_setting('insurance_fund', 'wallet_network', ins_data['wallet_network'])
                updated.append('insurance_fund.wallet_network')
            if 'contribution_rate' in ins_data:
                SystemSetting.set_setting('insurance_fund', 'contribution_rate', str(ins_data['contribution_rate']))
                updated.append('insurance_fund.contribution_rate')
        
        logger.info(f"Admin {current_user.username} updated subscription settings: {updated}")
        
        return jsonify({
            'success': True,
            'message': f'Updated {len(updated)} settings',
            'updated': updated
        })
    except Exception as e:
        logger.error(f"Error updating subscription settings: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/subscription-payments', methods=['GET'])
@login_required
def get_admin_subscription_payments():
    """Get all pending and recent subscription payments for admin"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        status_filter = request.args.get('status', 'all')
        limit = int(request.args.get('limit', 50))
        
        query = Payment.query
        
        if status_filter != 'all':
            query = query.filter(Payment.status == status_filter)
        
        payments = query.order_by(Payment.created_at.desc()).limit(limit).all()
        
        result = []
        for p in payments:
            user = User.query.get(p.user_id)
            result.append({
                'id': p.id,
                'user_id': p.user_id,
                'username': user.username if user else 'Unknown',
                'email': user.email if user else None,
                'amount_usd': p.amount_usd,
                'amount_crypto': p.amount_crypto,
                'currency': p.currency,
                'plan': p.plan,
                'days': p.days,
                'status': p.status,
                'provider': p.provider,
                'wallet_address': p.wallet_address,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'completed_at': p.completed_at.isoformat() if p.completed_at else None
            })
        
        return jsonify({
            'success': True,
            'payments': result,
            'total': len(result)
        })
    except Exception as e:
        logger.error(f"Error getting admin subscription payments: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/confirm-payment/<int:payment_id>', methods=['POST'])
@login_required
def admin_confirm_payment(payment_id):
    """Manually confirm a pending payment and activate subscription"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'success': False, 'error': 'Платіж не знайдено'}), 404
        
        if payment.status == 'completed':
            return jsonify({'success': False, 'error': 'Платіж вже підтверджено'}), 400
        
        user = User.query.get(payment.user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Користувача не знайдено'}), 404
        
        # Update payment status
        payment.status = 'completed'
        payment.completed_at = datetime.now(timezone.utc)
        
        # Activate user subscription
        user.extend_subscription(days=payment.days, plan=payment.plan)
        
        db.session.commit()
        
        logger.info(f"Admin {current_user.username} confirmed payment {payment_id} for user {user.username}")
        
        # Send notification if Telegram is enabled
        notifier = get_notifier()
        if notifier and user.telegram_chat_id and user.telegram_enabled:
            msg = f"""
💎 <b>SUBSCRIPTION ACTIVATED!</b>

✅ <b>Plan:</b> <code>{payment.plan.upper()}</code>
📅 <b>Days:</b> <code>{payment.days}</code>
💰 <b>Amount:</b> <code>${payment.amount_usd:.2f}</code>

🚀 Your subscription is active until: <code>{user.subscription_expires_at.strftime('%d.%m.%Y %H:%M')}</code>

Thank you for your payment! Trading is now enabled.
"""
            notifier.send(msg.strip(), chat_id=user.telegram_chat_id)
        
        return jsonify({
            'success': True,
            'message': f'Payment confirmed and subscription activated for {user.username}',
            'subscription_expires': user.subscription_expires_at.isoformat() if user.subscription_expires_at else None
        })
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/reject-payment/<int:payment_id>', methods=['POST'])
@login_required
def admin_reject_payment(payment_id):
    """Reject a pending payment"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'Payment not verified')
        
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'success': False, 'error': 'Платіж не знайдено'}), 404
        
        if payment.status == 'completed':
            return jsonify({'success': False, 'error': 'Неможливо відхилити завершений платіж'}), 400
        
        user = User.query.get(payment.user_id)
        
        # Update payment status
        payment.status = 'cancelled'
        db.session.commit()
        
        logger.info(f"Admin {current_user.username} rejected payment {payment_id}: {reason}")
        
        # Notify user if Telegram is enabled
        notifier = get_notifier()
        if notifier and user and user.telegram_chat_id and user.telegram_enabled:
            msg = f"""
❌ <b>PAYMENT REJECTED</b>

Your payment request has been rejected.
<b>Reason:</b> <code>{reason}</code>

Please contact support if you believe this is an error.
"""
            notifier.send(msg.strip(), chat_id=user.telegram_chat_id)
        
        return jsonify({
            'success': True,
            'message': 'Payment rejected'
        })
    except Exception as e:
        logger.error(f"Error rejecting payment: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/activate-subscription/<int:user_id>', methods=['POST'])
@login_required
def admin_activate_subscription(user_id):
    """Manually activate subscription for a user without payment"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібен доступ адміністратора'}), 403
    
    try:
        from models import SystemSetting
        data = request.get_json() or {}
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Користувача не знайдено'}), 404
        
        plan = data.get('plan', 'basic')
        days = int(data.get('days', SystemSetting.get_setting('subscription', 'default_days', '30') or '30'))
        
        # Activate subscription
        user.extend_subscription(days=days, plan=plan)
        
        # Create a manual payment record
        payment = Payment(
            user_id=user.id,
            provider='manual',
            amount_usd=0,
            plan=plan,
            days=days,
            status='completed',
            completed_at=datetime.now(timezone.utc)
        )
        db.session.add(payment)
        db.session.commit()
        
        logger.info(f"Admin {current_user.username} manually activated {days} days of {plan} subscription for user {user.username}")
        
        return jsonify({
            'success': True,
            'message': f'Subscription activated for {user.username}',
            'plan': plan,
            'days': days,
            'expires_at': user.subscription_expires_at.isoformat() if user.subscription_expires_at else None
        })
    except Exception as e:
        logger.error(f"Error activating subscription: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/subscription/create-payment', methods=['POST'])
@login_required
def create_direct_payment():
    """
    Create a direct wallet payment request (replaces Plisio).
    User selects plan and network, receives admin wallet address.
    """
    try:
        from models import SystemSetting
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Дані не надано'}), 400
        
        plan_id = data.get('plan', 'basic')
        network = data.get('network', 'usdt_trc20')
        
        # Validate plan
        if plan_id not in Config.SUBSCRIPTION_PLANS:
            return jsonify({'success': False, 'error': f'Невірний план: {plan_id}'}), 400
        
        plan = Config.SUBSCRIPTION_PLANS[plan_id]
        
        # Get wallet address for the selected network
        wallet_address = SystemSetting.get_setting('wallet', network, '')
        
        if not wallet_address:
            return jsonify({
                'success': False, 
                'error': f'Wallet address not configured for {network}. Please contact admin.'
            }), 400
        
        # Check if subscription system is enabled
        subscription_enabled = SystemSetting.get_setting('subscription', 'enabled', 'false').lower() == 'true'
        if not subscription_enabled:
            return jsonify({
                'success': False,
                'error': 'Subscription payments are currently disabled. You have free access.'
            }), 400
        
        # Generate unique payment reference
        payment_ref = f"SUB-{current_user.id}-{secrets.token_hex(6).upper()}"
        
        # Create pending payment record
        payment = Payment(
            user_id=current_user.id,
            provider='direct_wallet',
            provider_txn_id=payment_ref,
            amount_usd=plan['price'],
            currency=network.upper(),
            plan=plan_id,
            days=plan['days'],
            status='pending',
            wallet_address=wallet_address,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        
        db.session.add(payment)
        db.session.commit()
        
        # Network display names
        network_names = {
            'usdt_trc20': 'USDT (TRC20 - Tron)',
            'usdt_erc20': 'USDT (ERC20 - Ethereum)',
            'usdt_bep20': 'USDT (BEP20 - BSC)',
            'btc': 'Bitcoin (BTC)',
            'eth': 'Ethereum (ETH)',
            'ltc': 'Litecoin (LTC)',
            'sol': 'Solana (SOL)'
        }
        
        return jsonify({
            'success': True,
            'payment': {
                'id': payment.id,
                'reference': payment_ref,
                'plan_name': plan['name'],
                'amount_usd': plan['price'],
                'days': plan['days'],
                'network': network,
                'network_name': network_names.get(network, network),
                'wallet_address': wallet_address,
                'expires_at': payment.expires_at.isoformat()
            },
            'message': f'Send ${plan["price"]:.2f} worth of {network_names.get(network, network)} to the wallet address below'
        })
    except Exception as e:
        logger.error(f"Error creating direct payment: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/subscription/mark-paid/<int:payment_id>', methods=['POST'])
@login_required
def mark_payment_as_paid(payment_id):
    """User marks their payment as sent, awaiting admin confirmation"""
    try:
        from models import SystemSetting
        
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'success': False, 'error': 'Платіж не знайдено'}), 404
        
        if payment.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Неавторизовано'}), 403
        
        if payment.status != 'pending':
            return jsonify({'success': False, 'error': f'Payment is already {payment.status}'}), 400
        
        data = request.get_json() or {}
        tx_hash = data.get('tx_hash', '')
        
        # Update payment status to awaiting confirmation
        payment.status = 'awaiting_confirmation'
        if tx_hash:
            payment.provider_txn_id = f"{payment.provider_txn_id}|TX:{tx_hash}"
        
        db.session.commit()
        
        # Check if auto-confirm is enabled
        auto_confirm = SystemSetting.get_setting('subscription', 'auto_confirm', 'false').lower() == 'true'
        
        if auto_confirm:
            # Auto-confirm the payment
            payment.status = 'completed'
            payment.completed_at = datetime.now(timezone.utc)
            current_user.extend_subscription(days=payment.days, plan=payment.plan)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Payment automatically confirmed! Your subscription is now active.',
                'auto_confirmed': True,
                'subscription_expires': current_user.subscription_expires_at.isoformat() if current_user.subscription_expires_at else None
            })
        
        # Notify admin via Telegram if available
        notifier = get_notifier()
        if notifier:
            admin_msg = f"""
📬 <b>NEW PAYMENT AWAITING CONFIRMATION</b>

👤 <b>User:</b> <code>{current_user.username}</code>
📧 <b>Email:</b> <code>{current_user.email or 'N/A'}</code>
💰 <b>Amount:</b> <code>${payment.amount_usd:.2f}</code>
📋 <b>Plan:</b> <code>{payment.plan}</code>
🔗 <b>Network:</b> <code>{payment.currency}</code>
{f'📝 <b>TX Hash:</b> <code>{tx_hash}</code>' if tx_hash else ''}

Please verify and confirm in the admin panel.
"""
            try:
                notifier.send(admin_msg.strip())
            except:
                pass
        
        return jsonify({
            'success': True,
            'message': 'Payment marked as sent. Awaiting admin confirmation.',
            'auto_confirmed': False
        })
    except Exception as e:
        logger.error(f"Error marking payment as paid: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/subscription/status', methods=['GET'])
@login_required
def get_user_subscription_status():
    """Get current user's detailed subscription status"""
    try:
        from models import SystemSetting
        
        # Check if subscription system is enabled
        subscription_enabled = SystemSetting.get_setting('subscription', 'enabled', 'false').lower() == 'true'
        
        # Get pending payments
        pending_payments = Payment.query.filter(
            Payment.user_id == current_user.id,
            Payment.status.in_(['pending', 'awaiting_confirmation'])
        ).order_by(Payment.created_at.desc()).all()
        
        pending_list = [{
            'id': p.id,
            'plan': p.plan,
            'amount_usd': p.amount_usd,
            'currency': p.currency,
            'status': p.status,
            'wallet_address': p.wallet_address,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'expires_at': p.expires_at.isoformat() if p.expires_at else None
        } for p in pending_payments]
        
        # Get payment history
        payment_history = Payment.query.filter(
            Payment.user_id == current_user.id,
            Payment.status == 'completed'
        ).order_by(Payment.completed_at.desc()).limit(10).all()
        
        history_list = [{
            'id': p.id,
            'plan': p.plan,
            'days': p.days,
            'amount_usd': p.amount_usd,
            'completed_at': p.completed_at.isoformat() if p.completed_at else None
        } for p in payment_history]
        
        return jsonify({
            'success': True,
            'subscription_enabled': subscription_enabled,
            'is_active': current_user.has_active_subscription() if subscription_enabled else True,
            'plan': current_user.subscription_plan or 'free',
            'expires_at': current_user.subscription_expires_at.isoformat() if current_user.subscription_expires_at else None,
            'days_remaining': current_user.subscription_days_remaining() if subscription_enabled else 999,
            'can_trade': (current_user.has_active_subscription() or not subscription_enabled) and current_user.is_active,
            'pending_payments': pending_list,
            'payment_history': history_list
        })
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/subscription/available-networks', methods=['GET'])
def get_available_payment_networks():
    """Get list of available payment networks with wallet addresses configured"""
    try:
        from models import SystemSetting
        
        # Check if subscription is enabled
        subscription_enabled = SystemSetting.get_setting('subscription', 'enabled', 'false').lower() == 'true'
        
        networks = []
        network_info = {
            'usdt_trc20': {'name': 'USDT (TRC20)', 'icon': 'tron', 'symbol': 'USDT'},
            'usdt_erc20': {'name': 'USDT (ERC20)', 'icon': 'ethereum', 'symbol': 'USDT'},
            'usdt_bep20': {'name': 'USDT (BEP20)', 'icon': 'binance', 'symbol': 'USDT'},
            'btc': {'name': 'Bitcoin', 'icon': 'bitcoin', 'symbol': 'BTC'},
            'eth': {'name': 'Ethereum', 'icon': 'ethereum', 'symbol': 'ETH'},
            'ltc': {'name': 'Litecoin', 'icon': 'litecoin', 'symbol': 'LTC'},
            'sol': {'name': 'Solana', 'icon': 'solana', 'symbol': 'SOL'}
        }
        
        for network_id, info in network_info.items():
            wallet = SystemSetting.get_setting('wallet', network_id, '')
            if wallet:  # Only show networks with configured wallets
                networks.append({
                    'id': network_id,
                    'name': info['name'],
                    'icon': info['icon'],
                    'symbol': info['symbol'],
                    'available': True
                })
        
        # Get subscription plans
        plans = []
        for plan_id, plan_data in Config.SUBSCRIPTION_PLANS.items():
            plans.append({
                'id': plan_id,
                'name': plan_data['name'],
                'price': plan_data['price'],
                'days': plan_data['days']
            })
        
        return jsonify({
            'success': True,
            'subscription_enabled': subscription_enabled,
            'networks': networks,
            'plans': plans
        })
    except Exception as e:
        logger.error(f"Error getting available networks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== AI SENTIMENT FILTER ====================

@app.route('/api/sentiment', methods=['GET'])
@login_required
def get_market_sentiment():
    """
    Get current market sentiment (Fear & Greed Index) and active risk adjustments.
    
    Returns:
        JSON with:
        - value: Current Fear & Greed Index (0-100)
        - classification: 'extreme_fear', 'fear', 'neutral', 'greed', 'extreme_greed'
        - label: Human-readable label
        - color: Color code for display
        - is_extreme: True if in extreme fear/greed zone
        - risk_adjustments: Active risk adjustment rules
    """
    import asyncio
    from sentiment import SentimentManager
    
    try:
        # Get sentiment data - try Redis cache first, then API
        if redis_client:
            try:
                # Use async-to-sync pattern
                async def get_sentiment():
                    import redis.asyncio as aioredis
                    from urllib.parse import urlparse
                    
                    parsed = urlparse(app.config.get('REDIS_URL', 'redis://localhost:6379/0'))
                    async_redis = aioredis.Redis(
                        host=parsed.hostname or '127.0.0.1',
                        port=parsed.port or 6379,
                        db=int(parsed.path.lstrip('/') or 0) if parsed.path else 0,
                        password=parsed.password,
                        socket_timeout=5,
                    )
                    
                    try:
                        manager = SentimentManager(async_redis)
                        status = await manager.get_sentiment_status()
                        return status
                    finally:
                        await async_redis.aclose()
                
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Fallback to sync Redis read
                        value = redis_client.get('market:sentiment:fear_greed')
                        if value:
                            value = int(value)
                            classification = redis_client.get('market:sentiment:classification')
                            classification = classification.decode() if isinstance(classification, bytes) else (classification or 'neutral')
                            timestamp = redis_client.get('market:sentiment:timestamp')
                            
                            # Build response
                            from sentiment import SENTIMENT_CLASSIFICATIONS, EXTREME_FEAR_THRESHOLD, EXTREME_GREED_THRESHOLD, RISK_REDUCTION_PERCENT
                            
                            class_details = SENTIMENT_CLASSIFICATIONS.get(classification, {
                                "label": classification.replace('_', ' ').title(),
                                "color": "#808080"
                            })
                            
                            adjustments = []
                            if value > EXTREME_GREED_THRESHOLD:
                                adjustments.append({
                                    "affected": "LONG",
                                    "adjustment": f"-{RISK_REDUCTION_PERCENT}% risk",
                                    "reason": "Extreme Greed - preventing buying tops"
                                })
                            elif value < EXTREME_FEAR_THRESHOLD:
                                adjustments.append({
                                    "affected": "SHORT",
                                    "adjustment": f"-{RISK_REDUCTION_PERCENT}% risk",
                                    "reason": "Extreme Fear - preventing selling bottoms"
                                })
                            
                            return jsonify({
                                'success': True,
                                'value': value,
                                'classification': classification,
                                'label': class_details.get('label', classification),
                                'color': class_details.get('color', '#808080'),
                                'is_extreme': value < EXTREME_FEAR_THRESHOLD or value > EXTREME_GREED_THRESHOLD,
                                'risk_adjustments': adjustments,
                                'last_updated': timestamp.decode() if isinstance(timestamp, bytes) else timestamp,
                                'source': 'cache'
                            })
                    else:
                        status = loop.run_until_complete(get_sentiment())
                        return jsonify({'success': True, **status})
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    status = loop.run_until_complete(get_sentiment())
                    return jsonify({'success': True, **status})
                    
            except Exception as redis_err:
                logger.warning(f"Redis sentiment read failed: {redis_err}")
        
        # Fallback: return neutral sentiment
        return jsonify({
            'success': True,
            'value': 50,
            'classification': 'neutral',
            'label': 'Neutral',
            'color': '#ffc400',
            'is_extreme': False,
            'risk_adjustments': [],
            'last_updated': None,
            'source': 'fallback'
        })
        
    except Exception as e:
        logger.error(f"Sentiment API error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'value': 50,
            'classification': 'neutral',
            'label': 'Unknown',
            'color': '#808080',
            'is_extreme': False,
            'risk_adjustments': []
        }), 500


# ==================== WEBHOOK ====================

# ARQ task queueing helper
async def enqueue_signal_task(signal: dict) -> str:
    """
    Queue a trading signal to the ARQ worker.
    Returns job_id on success.
    """
    try:
        arq_settings = globals().get("ARQ_REDIS_SETTINGS")
        if not arq_settings:
            logger.warning("ARQ enqueue skipped: ARQ_REDIS_SETTINGS not configured")
            return None
        from arq import create_pool
        pool = await create_pool(arq_settings)
        job = await pool.enqueue_job('execute_signal_task', signal)
        await pool.close()
        return job.job_id if job else None
    except Exception as e:
        logger.error(f"ARQ enqueue error: {e}")
        return None


def queue_signal_to_arq(signal: dict) -> tuple:
    """
    Synchronous wrapper to queue signal via ARQ.
    Returns (success: bool, job_id_or_error: str)
    """
    try:
        arq_settings = globals().get("ARQ_REDIS_SETTINGS")
        if not arq_settings:
            return False, "ARQ_REDIS_SETTINGS not configured"
        import asyncio
        
        # Try to get existing event loop or create new one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running in async context (e.g., with eventlet/gevent)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, enqueue_signal_task(signal))
                    job_id = future.result(timeout=5)
            else:
                job_id = loop.run_until_complete(enqueue_signal_task(signal))
        except RuntimeError:
            # No event loop, create new one
            job_id = asyncio.run(enqueue_signal_task(signal))
        
        if job_id:
            return True, job_id
        return False, "Failed to enqueue job"
    except Exception as e:
        return False, str(e)


@app.route('/webhook', methods=['POST'])
@validate_webhook
def webhook():
    """
    TradingView webhook endpoint with security
    
    DECOUPLED ARCHITECTURE:
    - Validates signature and input
    - Queues task to ARQ worker via Redis
    - Returns 200 OK immediately
    - Trading execution happens in separate worker process
    
    SECURITY HARDENED:
    - Rate limiting via @validate_webhook
    - Timing-safe passphrase comparison
    - Input validation for all fields
    - No sensitive data in logs
    """
    ip = get_client_ip()
    
    try:
        # SECURITY: Don't log raw webhook data in production - may contain passphrase
        raw_data = request.get_data(as_text=True)
        if IS_PRODUCTION:
            logger.info(f"📨 Webhook received from {ip} ({len(raw_data) if raw_data else 0} bytes)")
        else:
            # Development only - truncate sensitive data
            safe_data = raw_data[:100].replace(Config.WEBHOOK_PASSPHRASE, '***') if raw_data else '(empty)'
            logger.info(f"📨 Webhook from {ip}: {safe_data}...")
        
        data = request.get_json(silent=True)
        
        if not data:
            # Try to fix common TradingView JSON issues (trailing commas)
            if raw_data:
                try:
                    # Remove trailing commas before closing brackets/braces
                    cleaned_data = re.sub(r',(\s*[}\]])', r'\1', raw_data)
                    data = json.loads(cleaned_data)
                    logger.info(f"✅ Webhook: Fixed malformed JSON (trailing commas)")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Webhook: Data received but not valid JSON: {raw_data[:200]}")
                    logger.warning(f"JSON parse error: {str(e)}")
                    return jsonify({'error': 'Невірний формат JSON'}), 400
            
            if not data:
                # Empty request - health check
                logger.debug("Webhook: Health check ping")
                return jsonify({'status': 'ok', 'message': 'Webhook active'}), 200
        
        logger.info(f"📦 Webhook parsed: {data}")
        
        # Verify passphrase (timing-safe comparison)
        received_pass = data.get('passphrase', '')
        expected_pass = Config.WEBHOOK_PASSPHRASE
        if not secrets.compare_digest(str(received_pass), str(expected_pass)):
            audit.log_security_event("WEBHOOK_AUTH_FAIL", f"IP: {ip}", "WARNING")
            logger.warning(f"Webhook: Invalid passphrase from {ip}")
            return jsonify({'error': 'Неавторизовано'}), 401
        
        # Parse and validate signal
        raw_symbol = re.sub(r'\.P|\.p|\.S|\.s$', '', str(data.get('symbol', ''))).upper()
        valid, symbol = InputValidator.validate_symbol(raw_symbol)
        if not valid:
            return jsonify({'error': f'Невірний символ: {symbol}'}), 400
        
        action = data.get('action', 'close').lower()
        if action not in ['long', 'short', 'close']:
            return jsonify({'error': 'Невірна дія'}), 400
        
        # Get TP/SL with proper defaults from global settings
        tp_val = data.get('tp_perc')
        sl_val = data.get('sl_perc')
        
        # Use webhook value if provided and > 0, otherwise use global settings
        if tp_val is not None and float(tp_val) > 0:
            tp_perc = float(tp_val)
        else:
            tp_perc = float(GLOBAL_TRADE_SETTINGS.get('tp_perc', 5.0))
            
        if sl_val is not None and float(sl_val) > 0:
            sl_perc = float(sl_val)
        else:
            sl_perc = float(GLOBAL_TRADE_SETTINGS.get('sl_perc', 2.0))
        
        # Get risk and leverage: use webhook value only if > 0, otherwise use global settings
        webhook_risk = float(data.get('risk_perc', 0))
        webhook_leverage = int(data.get('leverage', 0))
        
        # For leverage, only use webhook value if it's > 1 (1x leverage is rarely intentional for futures)
        task_leverage = webhook_leverage if webhook_leverage > 1 else GLOBAL_TRADE_SETTINGS['leverage']
        task_risk = webhook_risk if webhook_risk > 0 else GLOBAL_TRADE_SETTINGS['risk_perc']
        
        # Get strategy_id from webhook (optional - defaults to 1 for backward compatibility)
        strategy_id = data.get('strategy_id')
        if strategy_id:
            try:
                strategy_id = int(strategy_id)
            except (ValueError, TypeError):
                strategy_id = 1  # Default to main strategy
        else:
            strategy_id = 1  # Default to main strategy
        
        signal = {
            'symbol': symbol,
            'action': action,
            'strategy_id': strategy_id,
            'risk': task_risk,
            'lev': task_leverage,
            'tp_perc': tp_perc,
            'sl_perc': sl_perc
        }
        
        logger.info(f"📥 Webhook received: {action.upper()} {symbol} (strategy_id={strategy_id})")
        logger.info(f"📊 Signal created: Risk={signal['risk']}%, Leverage={signal['lev']}x, TP={signal['tp_perc']}%, SL={signal['sl_perc']}%, Strategy={strategy_id}")
        logger.info(f"📊 (Webhook values: risk={webhook_risk}%, lev={webhook_leverage}x, using global: {webhook_leverage <= 1})")
        log_system_event(None, symbol, f"SIGNAL: {action.upper()} (Strategy: {strategy_id}, Risk: {signal['risk']}%, Lev: {signal['lev']}x)")
        
        # Queue the task via ARQ (preferred) or legacy Redis/memory queue
        queue_mode = 'memory'
        job_id = None
        
        # Use globals().get() for safe access - prevents NameError in edge cases
        arq_settings = globals().get("ARQ_REDIS_SETTINGS")
        if arq_settings:
            # Use ARQ async task queue (preferred)
            success, result = queue_signal_to_arq(signal)
            if success:
                queue_mode = 'arq'
                job_id = result
                logger.info(f"✅ Signal queued to ARQ worker: job_id={job_id}")
            else:
                # Fallback to legacy Redis queue
                logger.warning(f"⚠️ ARQ queue failed ({result}), using legacy Redis queue")
                if redis_client:
                    redis_client.rpush('trade_signals', json.dumps(signal))
                    queue_mode = 'redis-legacy'
                else:
                    signal_queue.put(signal)
                    queue_mode = 'memory'
        elif redis_client:
            # Legacy Redis queue (for backwards compatibility)
            redis_client.rpush('trade_signals', json.dumps(signal))
            queue_mode = 'redis-legacy'
        else:
            # In-memory queue (development only)
            signal_queue.put(signal)
            queue_mode = 'memory'
        
        # Return OK immediately - trading happens in background worker
        response = {
            'status': 'queued',
            'symbol': symbol,
            'action': action,
            'strategy_id': strategy_id,
            'mode': queue_mode
        }
        if job_id:
            response['job_id'] = job_id
            
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== ADMIN ROUTES ====================

@app.route('/admin/global_settings/update', methods=['POST'])
@login_required
def admin_update_global_settings():
    if current_user.role != 'admin':
        abort(403)
    
    try:
        # Helper function to safely parse float with default
        def safe_float(val, default):
            try:
                if val is None or val == '':
                    return default
                result = float(val)
                return result if result > 0 else default
            except (ValueError, TypeError):
                return default
        
        # Helper function to safely parse int with default
        def safe_int(val, default):
            try:
                if val is None or val == '':
                    return default
                result = int(float(val))  # Handle "10.0" -> 10
                return result if result > 0 else default
            except (ValueError, TypeError):
                return default
        
        # Parse values with explicit validation
        new_max_pos = safe_int(request.form.get('global_max_pos'), 10)
        new_max_pos = max(1, min(50, new_max_pos))  # Clamp between 1 and 50
        
        # Parse TP/SL with minimum of 0.1% to ensure they work
        new_tp = safe_float(request.form.get('global_tp'), 5.0)
        new_sl = safe_float(request.form.get('global_sl'), 2.0)
        
        # Ensure minimum values for TP/SL (at least 0.1%)
        new_tp = max(0.1, new_tp)
        new_sl = max(0.1, new_sl)
        
        # Parse min_balance with default of $1
        new_min_balance = safe_float(request.form.get('global_min_balance'), 1.0)
        new_min_balance = max(0.0, new_min_balance)  # Allow 0 to disable the check
        
        GLOBAL_TRADE_SETTINGS.update({
            'risk_perc': safe_float(request.form.get('global_risk'), 3.0),
            'leverage': safe_int(request.form.get('global_leverage'), 20),
            'tp_perc': new_tp,
            'sl_perc': new_sl,
            'max_positions': new_max_pos,
            'min_order_cost': safe_float(request.form.get('global_min_cost'), 5.0),
            'min_balance': new_min_balance
        })
        engine.min_order_cost = GLOBAL_TRADE_SETTINGS['min_order_cost']
        
        # Log the update for debugging - include TP/SL and min_balance
        logger.info(f"🔧 Global settings updated: max_positions={new_max_pos}, risk={GLOBAL_TRADE_SETTINGS['risk_perc']}%, leverage={GLOBAL_TRADE_SETTINGS['leverage']}x, TP={new_tp}%, SL={new_sl}%, min_balance=${new_min_balance}")
        
        flash('Глобальні налаштування оновлено', 'success')
    except Exception as e:
        logger.error(f"Failed to update global settings: {e}")
        flash(f'Помилка: {e}', 'error')
    
    return redirect(url_for('dashboard'))


@app.route('/admin/settings/update', methods=['POST'])
@login_required
def admin_update_user_settings():
    if current_user.role != 'admin':
        abort(403)
    
    try:
        user_id = request.form.get('user_id')
        user = db.session.get(User, user_id)
        
        if user:
            user.custom_risk = float(request.form.get('risk', 0))
            user.custom_leverage = int(request.form.get('leverage', 0))
            user.max_positions = int(request.form.get('max_pos', 5))
            db.session.commit()
            engine.load_slaves()
            flash(f'Налаштування {user.username} оновлено', 'success')
    except Exception as e:
        flash(f'Помилка: {e}', 'error')
    
    return redirect(url_for('dashboard'))


@app.route('/admin/credentials/update', methods=['POST'])
@login_required
def admin_update_credentials():
    """Admin can change user's login and password"""
    if current_user.role != 'admin':
        audit.log_security_event("UNAUTHORIZED_ADMIN_ACCESS", f"User: {current_user.username}", "WARNING")
        abort(403)
    
    try:
        user_id = request.form.get('user_id')
        new_username = InputValidator.sanitize_string(request.form.get('new_username', ''), 50)
        new_password = request.form.get('new_password', '').strip()
        
        user = db.session.get(User, user_id)
        
        if not user:
            flash('Користувача не знайдено', 'error')
            return redirect(url_for('dashboard'))
        
        if user.role == 'admin' and user.id != current_user.id:
            audit.log_security_event("ADMIN_MODIFY_ATTEMPT", f"By: {current_user.username}, Target: {user.username}", "WARNING")
            flash('Не можна змінювати дані іншого адміна', 'error')
            return redirect(url_for('dashboard'))
        
        old_username = user.username
        changes = []
        
        # Update username if provided
        if new_username and new_username != user.username:
            # Validate new username
            valid, result = InputValidator.validate_username(new_username)
            if not valid:
                flash(f'Невірний формат логіну: {result}', 'error')
                return redirect(url_for('dashboard'))
            
            # Check if username already exists
            existing = User.query.filter_by(username=new_username).first()
            if existing and existing.id != user.id:
                flash('Цей логін вже зайнятий', 'error')
                return redirect(url_for('dashboard'))
            user.username = new_username
            changes.append('логін')
        
        # Update password if provided
        if new_password:
            valid, result = InputValidator.validate_password(new_password)
            if not valid:
                flash(f'Невірний пароль: {result}', 'error')
                return redirect(url_for('dashboard'))
            user.set_password(new_password)
            changes.append('пароль')
        
        if changes:
            db.session.commit()
            flash(f'Змінено {", ".join(changes)} для {user.username}', 'success')
            audit.log_admin_action(
                current_user.username, 
                "CREDENTIAL_CHANGE", 
                f"User ID: {user.id} ({old_username})",
                f"Changed: {', '.join(changes)}"
            )
        else:
            flash('Нічого не змінено', 'info')
            
    except Exception as e:
        flash(f'Помилка: {e}', 'error')
        audit.log_security_event("CREDENTIAL_UPDATE_ERROR", str(e), "WARNING")
    
    return redirect(url_for('dashboard'))


@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@login_required
def approve_user(user_id):
    """
    Approve a user account
    
    SECURITY: Changed to POST to prevent CSRF via GET request
    """
    if current_user.role != 'admin':
        abort(403)
    
    user = db.session.get(User, user_id)
    if user:
        user.is_paused = False
        db.session.commit()
        engine.load_slaves()
        flash(f'Вузол {user.username} активовано', 'success')
        audit.log_admin_action(current_user.username, "APPROVE_USER", user.username)
        
        if telegram:
            telegram.notify_system_event("Вузол активовано", user.username)
    
    return redirect(url_for('dashboard'))


@app.route('/admin/security/status')
@login_required
def security_status():
    """View security status - blocked IPs, etc."""
    if current_user.role != 'admin':
        abort(403)
    
    return jsonify({
        'blocked_ips': login_tracker.get_blocked_ips(),
        'total_blocked': len(login_tracker.get_blocked_ips()),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/admin/security/unblock/<ip>')
@login_required
def unblock_ip(ip):
    """Unblock an IP address"""
    if current_user.role != 'admin':
        abort(403)
    
    if ip in login_tracker.blocked_ips:
        del login_tracker.blocked_ips[ip]
        audit.log_admin_action(current_user.username, "UNBLOCK_IP", ip)
        flash(f'IP {ip} розблоковано', 'success')
    else:
        flash(f'IP {ip} не знайдено в списку заблокованих', 'info')
    
    return redirect(url_for('dashboard'))


@app.route('/admin/disconnect/<int:user_id>', methods=['POST'])
@login_required
def disconnect_user(user_id):
    """
    Disconnect/pause a user account
    
    SECURITY: Changed to POST to prevent CSRF via GET request
    """
    if current_user.role != 'admin':
        abort(403)
    
    user = db.session.get(User, user_id)
    if user:
        user.is_paused = True
        db.session.commit()
        engine.load_slaves()
        flash(f'Вузол {user.username} призупинено', 'warning')
        audit.log_admin_action(current_user.username, "DISCONNECT_USER", user.username)
    
    return redirect(url_for('dashboard'))


@app.route('/admin/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """
    Delete a user account (simplified version)
    
    SECURITY: Changed to POST to prevent CSRF via GET request
    Use admin_delete_user for full deletion with related data
    """
    if current_user.role != 'admin':
        abort(403)
    
    user = db.session.get(User, user_id)
    if user:
        username = user.username
        audit.log_admin_action(current_user.username, "DELETE_USER", username)
        db.session.delete(user)
        db.session.commit()
        engine.load_slaves()
        flash(f'Вузол {username} видалено', 'success')
    
    return redirect(url_for('dashboard'))


@app.route('/action/<action_type>', methods=['POST'])
@login_required
def actions(action_type):
    """
    Admin trading actions (pause/resume/reload)
    
    SECURITY: Changed to POST to prevent CSRF via GET request
    """
    if current_user.role != 'admin':
        abort(403)
    
    # Validate action type
    valid_actions = ['pause', 'resume', 'reload']
    if action_type not in valid_actions:
        flash('Невідома дія', 'error')
        return redirect(url_for('dashboard'))
    
    if action_type == 'pause':
        engine.is_paused = True
        flash('Торгівлю призупинено', 'warning')
        audit.log_admin_action(current_user.username, "PAUSE_TRADING", "Global")
        if telegram:
            telegram.notify_system_event("Торгівлю призупинено", "Admin action")
    elif action_type == 'resume':
        engine.is_paused = False
        flash('Торгівлю відновлено', 'success')
        audit.log_admin_action(current_user.username, "RESUME_TRADING", "Global")
        if telegram:
            telegram.notify_system_event("Торгівлю відновлено", "Admin action")
    elif action_type == 'reload':
        engine.load_slaves()
        flash('Конфігурацію перезавантажено', 'success')
        audit.log_admin_action(current_user.username, "RELOAD_CONFIG", "Global")
    
    return redirect(url_for('dashboard'))


# ==================== ADMIN PAYOUT MANAGEMENT ====================

@app.route('/admin/payouts')
@login_required
def admin_payouts():
    """Admin page to view and manage payout requests"""
    if current_user.role != 'admin':
        abort(403)
    
    from models import PayoutRequest
    
    status_filter = request.args.get('status', 'pending')
    
    if status_filter == 'all':
        payouts = PayoutRequest.query.order_by(PayoutRequest.created_at.desc()).limit(100).all()
    else:
        payouts = PayoutRequest.query.filter_by(status=status_filter).order_by(PayoutRequest.created_at.desc()).limit(100).all()
    
    # Get counts for each status
    pending_count = PayoutRequest.query.filter_by(status='pending').count()
    approved_count = PayoutRequest.query.filter_by(status='approved').count()
    paid_count = PayoutRequest.query.filter_by(status='paid').count()
    rejected_count = PayoutRequest.query.filter_by(status='rejected').count()
    
    return render_template('admin_payouts.html',
                           payouts=payouts,
                           status_filter=status_filter,
                           pending_count=pending_count,
                           approved_count=approved_count,
                           paid_count=paid_count,
                           rejected_count=rejected_count)


@app.route('/admin/payout/<int:payout_id>/approve', methods=['POST'])
@login_required
def admin_approve_payout(payout_id):
    """Approve a payout request"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ заборонено'}), 403
    
    from models import PayoutRequest
    
    payout = PayoutRequest.query.get_or_404(payout_id)
    notes = request.form.get('notes', '')
    
    try:
        payout.approve(current_user.id, notes)
        audit.log_admin_action(current_user.username, "APPROVE_PAYOUT", f"ID: {payout_id}, Amount: ${payout.amount}")
        
        # Notify user via Telegram
        user = User.query.get(payout.user_id)
        if user and user.telegram_enabled and user.telegram_chat_id:
            try:
                notifier = get_notifier()
                if notifier:
                    notifier.send(
                        f"✅ <b>PAYOUT APPROVED</b>\n\n"
                        f"💵 Amount: <code>${payout.amount:.2f}</code>\n"
                        f"💳 Method: <code>{payout.payment_method}</code>\n\n"
                        f"Your payout has been approved and will be processed soon.",
                        chat_id=user.telegram_chat_id
                    )
            except Exception:
                pass
        
        flash(f'Payout #{payout_id} approved', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('admin_payouts', status='approved'))


@app.route('/admin/payout/<int:payout_id>/reject', methods=['POST'])
@login_required
def admin_reject_payout(payout_id):
    """Reject a payout request"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ заборонено'}), 403
    
    from models import PayoutRequest
    
    payout = PayoutRequest.query.get_or_404(payout_id)
    reason = request.form.get('reason', 'No reason provided')
    
    try:
        payout.reject(current_user.id, reason)
        audit.log_admin_action(current_user.username, "REJECT_PAYOUT", f"ID: {payout_id}, Reason: {reason}")
        
        # Notify user via Telegram
        user = User.query.get(payout.user_id)
        if user and user.telegram_enabled and user.telegram_chat_id:
            try:
                notifier = get_notifier()
                if notifier:
                    notifier.send(
                        f"❌ <b>PAYOUT REJECTED</b>\n\n"
                        f"💵 Amount: <code>${payout.amount:.2f}</code>\n"
                        f"📝 Reason: {reason}\n\n"
                        f"Please contact support if you have questions.",
                        chat_id=user.telegram_chat_id
                    )
            except Exception:
                pass
        
        flash(f'Payout #{payout_id} rejected', 'warning')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('admin_payouts'))


@app.route('/admin/payout/<int:payout_id>/pay', methods=['POST'])
@login_required
def admin_mark_payout_paid(payout_id):
    """Mark a payout as paid (after actual payment)"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ заборонено'}), 403
    
    from models import PayoutRequest
    
    payout = PayoutRequest.query.get_or_404(payout_id)
    txn_id = request.form.get('txn_id', '')
    notes = request.form.get('notes', '')
    
    try:
        payout.mark_paid(current_user.id, txn_id, notes)
        audit.log_admin_action(current_user.username, "MARK_PAYOUT_PAID", f"ID: {payout_id}, TxnID: {txn_id}")
        
        # Notify user via Telegram
        user = User.query.get(payout.user_id)
        if user and user.telegram_enabled and user.telegram_chat_id:
            try:
                notifier = get_notifier()
                if notifier:
                    notifier.send(
                        f"💰 <b>PAYOUT COMPLETED</b>\n\n"
                        f"💵 Amount: <code>${payout.amount:.2f}</code>\n"
                        f"💳 Method: <code>{payout.payment_method}</code>\n"
                        + (f"🔗 TxnID: <code>{txn_id}</code>\n" if txn_id else "") +
                        f"\nYour commission has been sent!",
                        chat_id=user.telegram_chat_id
                    )
            except Exception:
                pass
        
        flash(f'Payout #{payout_id} marked as paid', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('admin_payouts', status='paid'))


@app.route('/api/admin/payout/<int:payout_id>', methods=['GET'])
@login_required
def api_get_payout_details(payout_id):
    """Get payout details for admin modal"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ заборонено'}), 403
    
    from models import PayoutRequest
    
    payout = PayoutRequest.query.get_or_404(payout_id)
    user = User.query.get(payout.user_id)
    
    return jsonify({
        'success': True,
        'payout': payout.to_dict(),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'referral_stats': user.get_referral_stats() if user else {}
        }
    })


# ==================== PASSWORD ROUTES ====================

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """Сторінка вибору методу відновлення паролю"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    ip = get_client_ip()
    
    # Check rate limiting for password reset (more generous for testing)
    if not api_limiter.check(f"reset_{ip}", max_requests=10, window=3600):
        flash('Занадто багато спроб. Спробуйте через годину.', 'error')
        return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled)), 429
    
    if request.method == 'POST':
        # CSRF token validation
        from security import verify_csrf_token
        csrf_token = request.form.get('csrf_token', '')
        if not verify_csrf_token(csrf_token):
            audit.log_security_event("CSRF_VALIDATION_FAIL", f"IP: {ip}, Endpoint: forgot_password", "WARNING")
            flash('Сесія закінчилася. Спробуйте ще раз.', 'error')
            return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled)), 403
        
        identifier = request.form.get('identifier', '').strip()
        method = request.form.get('method', 'email')  # 'email' or 'telegram'
        
        if not identifier:
            flash('Введіть email, номер телефону або логін', 'error')
            return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled))
        
        # Пошук користувача за email, телефоном або логіном
        user = None
        if '@' in identifier:
            user = User.query.filter_by(email=identifier).first()
        if not user:
            user = User.query.filter(
                db.or_(
                    User.username == identifier,
                    User.phone == identifier
                )
            ).first()
        
        if not user:
            # Не показуємо чи користувач існує (security)
            flash('Якщо акаунт існує, ви отримаєте код відновлення', 'info')
            return redirect(url_for('forgot_password'))
        
        # Перевіряємо доступність методу
        can_use_email = user.email and email_sender and email_sender.enabled
        can_use_telegram = user.telegram_chat_id and user.telegram_enabled and telegram and telegram.enabled
        
        # Детальні повідомлення про проблеми
        if method == 'email':
            if not EMAIL_CONFIGURED:
                flash('Email відправка не налаштована на сервері. Зверніться до адміністратора або спробуйте Telegram.', 'error')
                return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled))
            if not user.email:
                flash('У вашому профілі не вказано email. Додайте email в налаштуваннях або спробуйте Telegram.', 'warning')
                return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled))
        
        if method == 'telegram':
            if not (telegram and telegram.enabled):
                flash('Telegram бот не налаштований на сервері. Зверніться до адміністратора.', 'error')
                return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled))
            if not user.telegram_chat_id:
                flash('У вашому профілі не вказано Telegram Chat ID. Додайте його в налаштуваннях.', 'warning')
                return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled))
            if not user.telegram_enabled:
                flash('Telegram сповіщення вимкнено у вашому профілі. Увімкніть їх в налаштуваннях.', 'warning')
                return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled))
        
        # Створюємо токен
        reset_token = PasswordResetToken.create_for_user(user.id, method=method)
        
        # SECURITY: Password reset codes are NOT logged in production
        # Only log that a reset was requested, not the actual code
        if not IS_PRODUCTION:
            logger.debug(f"🔐 [DEV ONLY] Password reset requested for {user.username}")
        
        # Відправляємо код
        success = False
        if method == 'email' and can_use_email:
            success = email_sender.send_password_reset_code(user.email, reset_token.code, user.username)
        elif method == 'telegram' and can_use_telegram:
            success = telegram.send_password_reset_code(user.telegram_chat_id, reset_token.code, user.username)
        
        if success:
            logger.info(f"📩 Password reset code sent to {user.username} via {method}")
            audit.log_security_event("PASSWORD_RESET_REQUESTED", f"User: {user.username}, Method: {method}, IP: {ip}", "INFO")
            session['reset_token'] = reset_token.token
            flash(f'Код підтвердження надіслано {"на email" if method == "email" else "в Telegram"}', 'success')
            return redirect(url_for('reset_password_verify'))
        else:
            # Якщо відправка не вдалася, але код створено - показуємо його в логах
            logger.warning(f"⚠️ Failed to send reset code to {user.username} via {method}. Code: {reset_token.code}")
            flash('Помилка відправки. Код відновлення записано в логи - зверніться до адміністратора.', 'warning')
            return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled))
    
    # GET request - показуємо форму
    return render_template('forgot_password.html', email_available=EMAIL_CONFIGURED, telegram_available=bool(telegram and telegram.enabled))


@app.route('/reset_password_verify', methods=['GET', 'POST'])
def reset_password_verify():
    """Сторінка введення коду та нового паролю"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    token_str = session.get('reset_token')
    if not token_str:
        flash('Сесія закінчилась. Почніть спочатку.', 'warning')
        return redirect(url_for('forgot_password'))
    
    # Знаходимо токен
    reset_token = PasswordResetToken.query.filter_by(token=token_str).first()
    
    if not reset_token or not reset_token.is_valid():
        session.pop('reset_token', None)
        flash('Код недійсний або прострочений. Спробуйте знову.', 'error')
        return redirect(url_for('forgot_password'))
    
    user = db.session.get(User, reset_token.user_id)
    if not user:
        session.pop('reset_token', None)
        flash('Користувача не знайдено', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        # CSRF token validation
        from security import verify_csrf_token
        csrf_token = request.form.get('csrf_token', '')
        if not verify_csrf_token(csrf_token):
            audit.log_security_event("CSRF_VALIDATION_FAIL", f"IP: {get_client_ip()}, Endpoint: reset_password_verify", "WARNING")
            flash('Сесія закінчилася. Спробуйте ще раз.', 'error')
            return redirect(url_for('forgot_password'))
        
        code = request.form.get('code', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Перевірка коду
        if not secrets.compare_digest(code, reset_token.code):
            flash('Невірний код підтвердження', 'error')
            return render_template('reset_password.html', 
                                 method=reset_token.method,
                                 masked_contact=_mask_contact(user, reset_token.method))
        
        # Валідація паролю - SECURITY: Use strong password validation
        valid, result = InputValidator.validate_password(new_password, strict=False)  # Less strict for password reset
        if not valid:
            flash(f'Пароль має бути не менше 8 символів з великими, малими літерами та цифрами', 'error')
            return render_template('reset_password.html',
                                 method=reset_token.method,
                                 masked_contact=_mask_contact(user, reset_token.method))
        
        if new_password != confirm_password:
            flash('Паролі не співпадають', 'error')
            return render_template('reset_password.html',
                                 method=reset_token.method,
                                 masked_contact=_mask_contact(user, reset_token.method))
        
        # Змінюємо пароль
        user.set_password(new_password)
        reset_token.mark_used()
        db.session.commit()
        
        # Очищаємо сесію
        session.pop('reset_token', None)
        
        logger.info(f"✅ Password reset successful for {user.username}")
        audit.log_security_event("PASSWORD_RESET_SUCCESS", f"User: {user.username}", "INFO")
        
        # Сповіщаємо користувача
        if user.telegram_chat_id and user.telegram_enabled and telegram:
            telegram.send(f"🔒 Ваш пароль Brain Capital було успішно змінено.", chat_id=user.telegram_chat_id)
        
        flash('Пароль успішно змінено! Увійдіть з новим паролем.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html',
                         method=reset_token.method,
                         masked_contact=_mask_contact(user, reset_token.method))


@app.route('/resend_reset_code', methods=['POST'])
def resend_reset_code():
    """Повторна відправка коду відновлення"""
    token_str = session.get('reset_token')
    if not token_str:
        return jsonify({'success': False, 'error': 'Сесія закінчилась'}), 400
    
    ip = get_client_ip()
    if not api_limiter.check(f"resend_{ip}", max_requests=3, window=300):
        return jsonify({'success': False, 'error': 'Зачекайте 5 хвилин перед повторною спробою'}), 429
    
    # Знаходимо старий токен
    old_token = PasswordResetToken.query.filter_by(token=token_str).first()
    if not old_token:
        return jsonify({'success': False, 'error': 'Токен не знайдено'}), 400
    
    user = db.session.get(User, old_token.user_id)
    if not user:
        return jsonify({'success': False, 'error': 'Користувача не знайдено'}), 400
    
    method = old_token.method
    
    # Створюємо новий токен
    new_token = PasswordResetToken.create_for_user(user.id, method=method)
    
    # Відправляємо код
    success = False
    if method == 'email' and email_sender:
        success = email_sender.send_password_reset_code(user.email, new_token.code, user.username)
    elif method == 'telegram' and telegram:
        success = telegram.send_password_reset_code(user.telegram_chat_id, new_token.code, user.username)
    
    if success:
        session['reset_token'] = new_token.token
        return jsonify({'success': True, 'message': 'Новий код надіслано'})
    else:
        return jsonify({'success': False, 'error': 'Помилка відправки'}), 500


def _mask_contact(user, method):
    """Маскування контакту для відображення"""
    if method == 'email' and user.email:
        email = user.email
        parts = email.split('@')
        if len(parts) == 2:
            name = parts[0]
            domain = parts[1]
            if len(name) > 2:
                masked_name = name[0] + '*' * (len(name) - 2) + name[-1]
            else:
                masked_name = name[0] + '*'
            return f"{masked_name}@{domain}"
    elif method == 'telegram' and user.telegram_chat_id:
        chat_id = user.telegram_chat_id
        if len(chat_id) > 4:
            return chat_id[:2] + '*' * (len(chat_id) - 4) + chat_id[-2:]
        return '****'
    return '***'


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        # CSRF token validation
        from security import verify_csrf_token
        csrf_token = request.form.get('csrf_token', '')
        if not verify_csrf_token(csrf_token):
            audit.log_security_event("CSRF_VALIDATION_FAIL", f"User: {current_user.username}, Endpoint: change_password", "WARNING")
            flash('Сесія закінчилася. Спробуйте ще раз.', 'error')
            return render_template('change_password.html'), 403
        
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        
        if not current_user.check_password(old_password):
            flash('Невірний поточний пароль', 'error')
            return render_template('change_password.html')
        
        # SECURITY: Validate password strength
        valid, result = InputValidator.validate_password(new_password)
        if not valid:
            flash(f'Невірний пароль: {result}', 'error')
            return render_template('change_password.html')
        
        current_user.set_password(new_password)
        db.session.commit()
        
        audit.log_security_event("PASSWORD_CHANGED", f"User: {current_user.username}", "INFO")
        flash('Пароль успішно змінено', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('change_password.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ==================== MESSAGING SYSTEM ====================

@app.route('/messages')
@login_required
def messages():
    """View messages - both for users and admin"""
    if current_user.role == 'admin':
        # Admin sees all messages sent to admin (recipient_id is NULL or is_from_admin=False)
        user_messages = Message.query.filter(
            Message.is_from_admin == False,
            Message.parent_id == None  # Only root messages
        ).order_by(Message.created_at.desc()).all()
        
        # Calculate stats for admin
        total_replies = sum(msg.replies.count() for msg in user_messages)
        unread_count = sum(1 for msg in user_messages if not msg.is_read)
        
        return render_template('messages_admin.html', 
                             messages=user_messages,
                             total_replies=total_replies,
                             unread_count=unread_count)
    else:
        # User sees their own conversations
        user_messages = Message.query.filter(
            db.or_(
                Message.sender_id == current_user.id,
                Message.recipient_id == current_user.id
            ),
            Message.parent_id == None  # Only root messages
        ).order_by(Message.created_at.desc()).all()
        return render_template('messages_user.html', messages=user_messages)


@app.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    """Send a message to admin (from user) or to user (from admin)"""
    subject = InputValidator.sanitize_string(request.form.get('subject', ''), 200)
    content = request.form.get('content', '').strip()
    recipient_id = request.form.get('recipient_id')
    
    if not content:
        flash('Повідомлення не може бути порожнім', 'error')
        return redirect(url_for('messages'))
    
    if len(content) > 2000:
        content = content[:2000]
    
    if current_user.role == 'admin' and recipient_id:
        # Admin sending to a user
        try:
            recipient_id = int(recipient_id)
            recipient = db.session.get(User, recipient_id)
            if not recipient:
                flash('Користувача не знайдено', 'error')
                return redirect(url_for('messages'))
        except ValueError:
            flash('Невірний ID користувача', 'error')
            return redirect(url_for('messages'))
        
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient_id,
            subject=subject or 'Повідомлення від адміністратора',
            content=content,
            is_from_admin=True
        )
        flash(f'Повідомлення відправлено користувачу {recipient.username}', 'success')
    else:
        # User sending to admin
        message = Message(
            sender_id=current_user.id,
            recipient_id=None,  # NULL means to admin
            subject=subject or 'Запит до адміністратора',
            content=content,
            is_from_admin=False
        )
        flash('Повідомлення відправлено адміністратору', 'success')
        
        # Notify admin via telegram
        if telegram:
            sender_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.username
            telegram.notify_system_event("Нове повідомлення", f"Від: {sender_name}\n{content[:100]}...")
    
    db.session.add(message)
    db.session.commit()
    
    # Emit socket event for real-time notification
    try:
        if current_user.role != 'admin':
            socketio.emit('new_message', message.to_dict(), room='admin_room')
        elif recipient_id:
            socketio.emit('new_message', message.to_dict(), room=f'user_{recipient_id}')
    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
            urllib3.exceptions.ProtocolError):
        # Client disconnected - expected behavior, silently ignore
        pass
    
    return redirect(url_for('messages'))


@app.route('/messages/reply/<int:message_id>', methods=['POST'])
@login_required
def reply_message(message_id):
    """Reply to a message"""
    original = db.session.get(Message, message_id)
    if not original:
        flash('Повідомлення не знайдено', 'error')
        return redirect(url_for('messages'))
    
    content = request.form.get('content', '').strip()
    if not content:
        flash('Відповідь не може бути порожньою', 'error')
        return redirect(url_for('messages'))
    
    if len(content) > 2000:
        content = content[:2000]
    
    # Determine recipient
    if current_user.role == 'admin':
        recipient_id = original.sender_id
        is_from_admin = True
    else:
        # Users can only reply to admin messages
        if not original.is_from_admin and original.sender_id != current_user.id:
            flash('Немає доступу до цього повідомлення', 'error')
            return redirect(url_for('messages'))
        recipient_id = None
        is_from_admin = False
    
    reply = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        subject=f"Re: {original.subject}",
        content=content,
        is_from_admin=is_from_admin,
        parent_id=original.id
    )
    
    db.session.add(reply)
    db.session.commit()
    
    # Emit socket event
    try:
        if is_from_admin and recipient_id:
            socketio.emit('new_message', reply.to_dict(), room=f'user_{recipient_id}')
        else:
            socketio.emit('new_message', reply.to_dict(), room='admin_room')
    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
            urllib3.exceptions.ProtocolError):
        # Client disconnected - expected behavior, silently ignore
        pass
    
    flash('Відповідь відправлено', 'success')
    return redirect(url_for('view_message', message_id=original.id))


@app.route('/messages/<int:message_id>')
@login_required
def view_message(message_id):
    """View a single message with its replies"""
    message = db.session.get(Message, message_id)
    if not message:
        flash('Повідомлення не знайдено', 'error')
        return redirect(url_for('messages'))
    
    # Check access
    if current_user.role != 'admin':
        if message.sender_id != current_user.id and message.recipient_id != current_user.id:
            flash('Немає доступу до цього повідомлення', 'error')
            return redirect(url_for('messages'))
    
    # Mark as read
    if not message.is_read:
        if (current_user.role == 'admin' and not message.is_from_admin) or \
           (current_user.role != 'admin' and message.is_from_admin):
            message.is_read = True
            db.session.commit()
    
    # Get all replies
    replies = Message.query.filter_by(parent_id=message.id).order_by(Message.created_at.asc()).all()
    
    # Mark replies as read
    for reply in replies:
        if not reply.is_read:
            if (current_user.role == 'admin' and not reply.is_from_admin) or \
               (current_user.role != 'admin' and reply.is_from_admin):
                reply.is_read = True
    db.session.commit()
    
    if current_user.role == 'admin':
        return render_template('message_view_admin.html', message=message, replies=replies)
    else:
        return render_template('message_view_user.html', message=message, replies=replies)


@app.route('/api/messages/unread')
@login_required
def get_unread_count():
    """Get count of unread messages"""
    if current_user.role == 'admin':
        count = Message.query.filter(
            Message.is_from_admin == False,
            Message.is_read == False
        ).count()
    else:
        count = Message.query.filter(
            Message.recipient_id == current_user.id,
            Message.is_from_admin == True,
            Message.is_read == False
        ).count()
    
    return jsonify({'unread': count})


@app.route('/api/messages/mark_read/<int:message_id>', methods=['POST'])
@login_required
def mark_message_read(message_id):
    """Mark a message as read"""
    message = db.session.get(Message, message_id)
    if message:
        message.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404


@app.route('/api/users/list')
@login_required
def get_users_list():
    """Get list of users for admin to send messages to"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    users = User.query.filter(User.role != 'admin').all()
    users_data = [{
        'id': u.id,
        'name': f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username,
        'username': u.username
    } for u in users]
    
    return jsonify(users_data)


# ==================== LIVE CHAT API ====================

@app.route('/api/chat/history')
@login_required
def get_chat_history():
    """Get chat message history for a room"""
    from models import ChatMessage, ChatBan
    
    room = request.args.get('room', 'general')
    before_id = request.args.get('before_id', type=int)
    limit = min(request.args.get('limit', 50, type=int), 100)
    
    # Check subscription
    if not current_user.has_active_subscription() and current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Потрібна активна підписка'}), 403
    
    # Check if user is banned
    is_banned, ban_type, reason, expires_at = ChatBan.is_user_banned(current_user.id)
    if is_banned:
        return jsonify({
            'success': False,
            'error': f'You are {ban_type}ed from chat',
            'ban_type': ban_type,
            'expires_at': expires_at.isoformat() if expires_at else None
        }), 403
    
    messages = ChatMessage.get_recent_messages(room, limit, before_id)
    
    return jsonify({
        'success': True,
        'messages': [msg.to_dict() for msg in reversed(messages)],
        'room': room,
        'has_more': len(messages) == limit
    })


@app.route('/api/chat/status')
def get_chat_status():
    """Check if user can access chat and their status.
    
    Non-authenticated users can still access AI Support, but not Live Chat.
    """
    from models import ChatBan
    
    # Check if user is authenticated
    if not current_user.is_authenticated:
        return jsonify({
            'success': True,
            'is_authenticated': False,
            'can_chat': False,  # Live chat requires authentication
            'has_subscription': False,
            'is_banned': False,
            'ban_type': None,
            'ban_reason': None,
            'ban_expires_at': None,
            'is_admin': False,
            'message': 'AI Support available. Log in for Live Chat.'
        })
    
    # All logged-in users can access chat (no subscription required)
    is_banned, ban_type, reason, expires_at = ChatBan.is_user_banned(current_user.id)
    
    return jsonify({
        'success': True,
        'is_authenticated': True,
        'can_chat': not is_banned,  # All users can chat unless banned
        'has_subscription': True,  # Always true - chat is free for all users
        'is_banned': is_banned,
        'ban_type': ban_type,
        'ban_reason': reason,
        'ban_expires_at': expires_at.isoformat() if expires_at else None,
        'is_admin': current_user.role == 'admin'
    })


@app.route('/api/chat/online_users')
@login_required
def get_online_users():
    """Get list of users currently in chat (approximation based on recent activity)"""
    from models import ChatMessage
    from datetime import datetime, timezone, timedelta
    
    # Chat is available to all logged-in users (no subscription required)
    
    # Get users who sent messages in the last 5 minutes
    recent_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    recent_users = db.session.query(
        ChatMessage.user_id,
        User.username,
        User.avatar,
        User.avatar_type,
        User.role
    ).join(User, ChatMessage.user_id == User.id).filter(
        ChatMessage.created_at >= recent_threshold,
        ChatMessage.is_deleted == False
    ).distinct().limit(50).all()
    
    users_list = [{
        'user_id': u[0],
        'username': u[1],
        'avatar': u[2],
        'avatar_type': u[3],
        'is_admin': u[4] == 'admin'
    } for u in recent_users]
    
    return jsonify({
        'success': True,
        'online_users': users_list,
        'count': len(users_list)
    })


# ==================== CHAT ADMIN API ====================

@app.route('/api/admin/chat/bans')
@login_required
def get_chat_bans():
    """Get list of all chat bans (admin only)"""
    from models import ChatBan
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Потрібен доступ адміністратора'}), 403
    
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    
    query = ChatBan.query.order_by(ChatBan.created_at.desc())
    if active_only:
        query = query.filter_by(is_active=True)
    
    bans = query.limit(100).all()
    
    return jsonify({
        'success': True,
        'bans': [ban.to_dict() for ban in bans]
    })


@app.route('/api/admin/chat/mute', methods=['POST'])
@login_required
def mute_user_chat():
    """Mute a user from chat (admin only)"""
    from models import ChatBan
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Потрібен доступ адміністратора'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    duration = data.get('duration', 60)  # Default 60 minutes
    reason = data.get('reason', 'Chat rule violation')
    
    if not user_id:
        return jsonify({'error': 'Потрібен ID користувача'}), 400
    
    # Check if user exists
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({'error': 'Користувача не знайдено'}), 404
    
    # Don't allow muting admins
    if target_user.role == 'admin':
        return jsonify({'error': 'Неможливо замʼютити адміністраторів'}), 400
    
    # Create mute
    ban = ChatBan.mute_user(user_id, duration, reason, current_user.id)
    
    # Notify the user via socket
    try:
        socketio.emit('chat_muted', {
            'message': f'You have been muted for {duration} minutes: {reason}',
            'duration': duration,
            'expires_at': ban.expires_at.isoformat() if ban.expires_at else None
        }, room=f'user_{user_id}')
    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
            urllib3.exceptions.ProtocolError):
        # Client disconnected - expected behavior, silently ignore
        pass
    
    return jsonify({
        'success': True,
        'message': f'User {target_user.username} muted for {duration} minutes',
        'ban': ban.to_dict()
    })


@app.route('/api/admin/chat/ban', methods=['POST'])
@login_required
def ban_user_chat():
    """Permanently ban a user from chat (admin only)"""
    from models import ChatBan
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Потрібен доступ адміністратора'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    reason = data.get('reason', 'Chat rule violation')
    
    if not user_id:
        return jsonify({'error': 'Потрібен ID користувача'}), 400
    
    # Check if user exists
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({'error': 'Користувача не знайдено'}), 404
    
    # Don't allow banning admins
    if target_user.role == 'admin':
        return jsonify({'error': 'Неможливо заблокувати адміністраторів'}), 400
    
    # Create ban
    ban = ChatBan.ban_user(user_id, reason, current_user.id)
    
    # Notify the user via socket
    try:
        socketio.emit('chat_banned', {
            'message': f'You have been banned from chat: {reason}'
        }, room=f'user_{user_id}')
        
        # Force disconnect from chat room
        socketio.emit('force_leave_chat', {'room': 'general'}, room=f'user_{user_id}')
    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
            urllib3.exceptions.ProtocolError):
        # Client disconnected - expected behavior, silently ignore
        pass
    
    return jsonify({
        'success': True,
        'message': f'User {target_user.username} banned from chat',
        'ban': ban.to_dict()
    })


@app.route('/api/admin/chat/unban', methods=['POST'])
@login_required
def unban_user_chat():
    """Remove ban/mute from a user (admin only)"""
    from models import ChatBan
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Потрібен доступ адміністратора'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'Потрібен ID користувача'}), 400
    
    # Check if user exists
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({'error': 'Користувача не знайдено'}), 404
    
    # Remove all active bans
    ChatBan.unban_user(user_id)
    
    # Notify the user via socket
    try:
        socketio.emit('chat_unbanned', {
            'message': 'Your chat restrictions have been lifted'
        }, room=f'user_{user_id}')
    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
            urllib3.exceptions.ProtocolError):
        # Client disconnected - expected behavior, silently ignore
        pass
    
    return jsonify({
        'success': True,
        'message': f'User {target_user.username} unbanned from chat'
    })


@app.route('/api/admin/chat/delete_message', methods=['POST'])
@login_required
def admin_delete_message():
    """Delete a chat message (admin only)"""
    from models import ChatMessage
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Потрібен доступ адміністратора'}), 403
    
    data = request.get_json()
    message_id = data.get('message_id')
    
    if not message_id:
        return jsonify({'error': 'Потрібен ID повідомлення'}), 400
    
    message = ChatMessage.query.get(message_id)
    if not message:
        return jsonify({'error': 'Повідомлення не знайдено'}), 404
    
    room = message.room
    message.is_deleted = True
    message.deleted_by_id = current_user.id
    db.session.commit()
    
    # Notify chat room
    try:
        socketio.emit('message_deleted', {'message_id': message_id}, room=f'chat_{room}')
    except (RemoteDisconnected, ConnectionAbortedError, ConnectionResetError, 
            urllib3.exceptions.ProtocolError):
        # Client disconnected - expected behavior, silently ignore
        pass
    
    return jsonify({
        'success': True,
        'message': 'Message deleted'
    })


# ==================== AI SUPPORT BOT API ====================

@app.route('/api/support/chat', methods=['POST'])
def support_chat():
    """
    AI Support Bot endpoint using RAG.
    
    Receives user questions and returns AI-generated answers based on
    documentation (README, DEV_MANUAL, FAQ).
    
    Request JSON:
    {
        "message": "How do I connect Binance?",
        "session_id": "optional-session-id"
    }
    
    Response JSON:
    {
        "success": true,
        "answer": "To connect Binance...",
        "confidence": 0.85,
        "sources": [{"file": "FAQ.md", "similarity": 0.92}],
        "ticket_id": null,
        "needs_human_review": false,
        "session_id": "abc123"
    }
    """
    from support_bot import chat_with_support
    from config import Config
    
    # Check if support bot is enabled
    if not getattr(Config, 'SUPPORT_BOT_ENABLED', False):
        return jsonify({
            'success': False,
            'error': 'AI Support Bot is not configured. Please contact admin support.'
        }), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Дані не надано'}), 400
    
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'success': False, 'error': 'Потрібне повідомлення'}), 400
    
    if len(message) > 1000:
        return jsonify({'success': False, 'error': 'Повідомлення задовге (макс. 1000 символів)'}), 400
    
    session_id = data.get('session_id')
    
    # Get user ID if logged in
    user_id = None
    if current_user.is_authenticated:
        user_id = current_user.id
    
    try:
        response = chat_with_support(
            message=message,
            session_id=session_id,
            user_id=user_id,
            channel='web'
        )
        
        return jsonify({
            'success': True,
            **response
        })
        
    except Exception as e:
        logger.error(f"Support chat error: {e}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while processing your question. Please try again.'
        }), 500


@app.route('/api/support/history')
def support_history():
    """Get support conversation history for current session"""
    from support_bot import get_support_bot
    
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'error': 'Потрібен ID сесії'}), 400
    
    bot = get_support_bot()
    history = bot.get_conversation_history(session_id)
    
    return jsonify({
        'success': True,
        'messages': history
    })


@app.route('/api/support/status')
def support_status():
    """Check if support bot is available"""
    from support_bot import get_support_bot
    from config import Config
    
    bot = get_support_bot()
    
    return jsonify({
        'success': True,
        'available': bot.is_available(),
        'enabled': getattr(Config, 'SUPPORT_BOT_ENABLED', False)
    })


@app.route('/api/admin/support/tickets')
@login_required
def get_support_tickets():
    """Get support tickets (admin only)"""
    from models import SupportTicket
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Потрібен доступ адміністратора'}), 403
    
    status = request.args.get('status', 'open')
    limit = min(int(request.args.get('limit', 50)), 100)
    
    if status == 'all':
        tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).limit(limit).all()
    else:
        tickets = SupportTicket.query.filter_by(status=status).order_by(SupportTicket.created_at.desc()).limit(limit).all()
    
    return jsonify({
        'success': True,
        'tickets': [t.to_dict() for t in tickets]
    })


@app.route('/api/admin/support/tickets/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def manage_support_ticket(ticket_id):
    """View or respond to a support ticket (admin only)"""
    from models import SupportTicket
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Потрібен доступ адміністратора'}), 403
    
    ticket = SupportTicket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Тікет не знайдено'}), 404
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'ticket': ticket.to_dict()
        })
    
    # POST - respond to ticket
    data = request.get_json()
    admin_response = data.get('response', '').strip()
    
    if not admin_response:
        return jsonify({'error': 'Потрібна відповідь'}), 400
    
    ticket.resolve(admin_response=admin_response, admin_id=current_user.id)
    
    return jsonify({
        'success': True,
        'message': 'Ticket resolved',
        'ticket': ticket.to_dict()
    })


# WebSocket event for support chat
@socketio.on('support_message')
def handle_support_message(data):
    """Handle support chat messages via WebSocket"""
    from support_bot import chat_with_support
    from config import Config
    
    if not getattr(Config, 'SUPPORT_BOT_ENABLED', False):
        emit('support_response', {
            'success': False,
            'error': 'AI Support Bot is not configured'
        })
        return
    
    message = data.get('message', '').strip()
    session_id = data.get('session_id')
    
    if not message:
        emit('support_response', {'success': False, 'error': 'Message required'})
        return
    
    user_id = None
    if current_user.is_authenticated:
        user_id = current_user.id
    
    try:
        response = chat_with_support(
            message=message,
            session_id=session_id,
            user_id=user_id,
            channel='web'
        )
        
        emit('support_response', {
            'success': True,
            **response
        })
        
    except Exception as e:
        logger.error(f"Support WebSocket error: {e}")
        emit('support_response', {
            'success': False,
            'error': 'An error occurred'
        })


# ==================== EXCHANGE MANAGEMENT ====================

# All supported exchanges (master list) - Limited to 5 exchanges
ALL_SUPPORTED_EXCHANGES = [
    {'value': 'binance', 'label': 'Binance', 'requires_passphrase': False},
    {'value': 'bybit', 'label': 'Bybit', 'requires_passphrase': False},
    {'value': 'okx', 'label': 'OKX', 'requires_passphrase': True},
    {'value': 'gate', 'label': 'Gate.io', 'requires_passphrase': False},
    {'value': 'mexc', 'label': 'MEXC Global', 'requires_passphrase': False},
]


def init_exchange_configs():
    """Initialize exchange configs if they don't exist"""
    for ex in ALL_SUPPORTED_EXCHANGES:
        existing = ExchangeConfig.query.filter_by(exchange_name=ex['value']).first()
        if not existing:
            config = ExchangeConfig(
                exchange_name=ex['value'],
                display_name=ex['label'],
                is_enabled=False,
                requires_passphrase=ex['requires_passphrase']
            )
            db.session.add(config)
    db.session.commit()


@app.route('/api/exchanges/available')
def get_available_exchanges():
    """Return list of all configured exchanges (for registration and logged-in users)"""
    # Initialize exchanges if they don't exist
    init_exchange_configs()
    
    # Get all configured exchanges
    all_exchanges = ExchangeConfig.query.all()
    
    # If no exchanges configured, initialize and return them
    if not all_exchanges:
        init_exchange_configs()
        all_exchanges = ExchangeConfig.query.all()
    
    # Convert to dict format expected by frontend
    result = []
    for ex in all_exchanges:
        result.append({
            'exchange_name': ex.exchange_name,
            'display_name': ex.display_name,
            'requires_passphrase': ex.requires_passphrase,
            'is_enabled': ex.is_enabled,
            'is_verified': ex.is_verified
        })
    
    return jsonify(result)


@app.route('/api/exchanges', methods=['GET'])
@login_required
def list_user_exchanges():
    """List all exchanges for current user with optional balance fetching"""
    exchanges = UserExchange.query.filter_by(user_id=current_user.id).all()
    
    # Get display names from config
    configs = {c.exchange_name: c.display_name for c in ExchangeConfig.query.all()}
    
    # Check if balances should be included
    include_balances = request.args.get('with_balances', 'false').lower() == 'true'
    
    result = []
    for ex in exchanges:
        ex_data = {
            'id': ex.id,
            'exchange_name': ex.exchange_name,
            'display_name': configs.get(ex.exchange_name, ex.exchange_name.upper()),
            'label': ex.label,
            'api_key': ex.api_key[:8] + '...' + ex.api_key[-4:] if ex.api_key and len(ex.api_key) > 12 else '***',
            'status': ex.status,
            'is_active': ex.is_active,
            'trading_enabled': ex.trading_enabled,
            'error_message': ex.error_message,
            'created_at': ex.created_at.strftime('%d.%m.%Y %H:%M') if ex.created_at else None,
            'balance': None,
            'balance_error': None
        }
        result.append(ex_data)
    
    # Fetch balances if requested (async fetch for all exchanges at once)
    if include_balances:
        balance_data = get_user_exchange_balances(current_user.id)
        balance_map = {b['id']: b for b in balance_data['exchanges']}
        for ex_data in result:
            if ex_data['id'] in balance_map:
                ex_data['balance'] = balance_map[ex_data['id']].get('balance')
                ex_data['balance_error'] = balance_map[ex_data['id']].get('error')
    
    return jsonify(result)


@app.route('/api/exchanges/balances', methods=['GET'])
@login_required
def get_user_exchange_balances_api():
    """Get balances for all user's connected exchanges"""
    try:
        balance_data = get_user_exchange_balances(current_user.id)
        return jsonify({
            'success': True,
            'total_balance': balance_data['total'],
            'exchanges': balance_data['exchanges']
        })
    except Exception as e:
        logger.error(f"Error fetching exchange balances for user {current_user.id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exchanges', methods=['POST'])
@login_required
def add_user_exchange():
    """Add a new exchange connection for user (only from admin-enabled exchanges)"""
    try:
        data = request.get_json()
        
        exchange_name = data.get('exchange_name', '').lower().strip()
        api_key = data.get('api_key', '').strip()
        api_secret = data.get('api_secret', '').strip()
        passphrase = data.get('passphrase', '').strip() if data.get('passphrase') else None
        label = InputValidator.sanitize_string(data.get('label', ''), 100)
        
        # Check if exchange is enabled AND verified by admin
        exchange_config = ExchangeConfig.query.filter_by(exchange_name=exchange_name).first()
        if not exchange_config:
            return jsonify({'success': False, 'error': f'Біржа "{exchange_name}" не знайдена.'}), 400
        
        if not exchange_config.is_verified:
            return jsonify({'success': False, 'error': f'Біржа "{exchange_config.display_name}" ще не верифікована адміністратором.'}), 400
        
        if not exchange_config.is_enabled:
            return jsonify({'success': False, 'error': f'Біржа "{exchange_config.display_name}" вимкнена адміністратором.'}), 400
        
        # Validate passphrase requirement
        if exchange_config.requires_passphrase and not passphrase:
            return jsonify({'success': False, 'error': f'Біржа {exchange_config.display_name} вимагає passphrase'}), 400
        
        # Check if user already has this exchange
        existing = UserExchange.query.filter_by(user_id=current_user.id, exchange_name=exchange_name).first()
        if existing:
            return jsonify({'success': False, 'error': f'Ви вже маєте підключення до {exchange_config.display_name}'}), 400
        
        # Validate API key format
        valid, result = InputValidator.validate_api_key(api_key)
        if not valid:
            return jsonify({'success': False, 'error': f'Невірний API Key: {result}'}), 400
        
        valid, result = InputValidator.validate_api_key(api_secret)
        if not valid:
            return jsonify({'success': False, 'error': f'Невірний API Secret: {result}'}), 400
        
        if not label:
            label = f'{exchange_config.display_name} Account'
        
        # MANDATORY: Validate credentials with exchange before saving
        from service_validator import validate_and_connect, ExchangeValidationError, ExchangeConnectionError
        
        try:
            logger.info(f"🔄 Validating {exchange_name} credentials for user {current_user.id}...")
            
            validation_result = validate_and_connect(
                exchange_name=exchange_name,
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase
            )
            
            if not validation_result.get('success'):
                return jsonify({
                    'success': False, 
                    'error': f'❌ Не вдалося підключитися до {exchange_config.display_name}. Перевірте API ключі.'
                }), 400
            
            logger.info(f"✅ API keys validated successfully for {exchange_name}")
            
        except ExchangeConnectionError as e:
            logger.warning(f"Exchange connection error: {e}")
            error_msg = str(e)
            if 'Authentication' in error_msg or 'Invalid' in error_msg:
                return jsonify({
                    'success': False, 
                    'error': f'❌ Невірні API ключі для {exchange_config.display_name}. Перевірте API Key та Secret.'
                }), 400
            return jsonify({
                'success': False, 
                'error': f'❌ Помилка підключення до {exchange_config.display_name}: {error_msg}'
            }), 400
            
        except ExchangeValidationError as e:
            logger.warning(f"Exchange validation error: {e}")
            return jsonify({
                'success': False, 
                'error': f'❌ Помилка валідації: {str(e)}'
            }), 400
            
        except Exception as e:
            logger.error(f"Unexpected validation error: {e}")
            return jsonify({
                'success': False, 
                'error': f'❌ Помилка перевірки з\'єднання: {str(e)}'
            }), 400
        
        # Keys are valid - create exchange record
        user_exchange = UserExchange(
            user_id=current_user.id,
            exchange_name=exchange_name,
            label=label,
            api_key=api_key,
            status='PENDING',
            is_active=False,
            error_message=None  # No error - keys are valid
        )
        user_exchange.set_api_secret(api_secret)
        if passphrase:
            user_exchange.set_passphrase(passphrase)
        
        db.session.add(user_exchange)
        db.session.commit()
        
        logger.info(f"✅ User {current_user.id} added exchange {exchange_name} (ID: {user_exchange.id}) - Keys validated!")
        
        # Notify admin
        if telegram:
            user_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.username
            telegram.notify_system_event(
                "✅ Нова біржа (ключі перевірено)", 
                f"Користувач: {user_name}\nБіржа: {exchange_config.display_name}\nНазва: {label}\nСтатус: API ключі валідні"
            )
        
        return jsonify({
            'success': True,
            'message': f'✅ Біржу {exchange_config.display_name} додано! API ключі перевірено. Очікуйте підтвердження від адміністратора.',
            'exchange': {
                'id': user_exchange.id,
                'exchange_name': user_exchange.exchange_name,
                'label': user_exchange.label,
                'status': user_exchange.status
            }
        })
        
    except Exception as e:
        logger.error(f"Error adding exchange: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exchanges/<int:exchange_id>/toggle', methods=['POST'])
@login_required
def toggle_user_exchange(exchange_id):
    """Toggle exchange active status"""
    try:
        data = request.get_json()
        is_active = data.get('is_active', False)
        
        exchange = UserExchange.query.filter_by(
            id=exchange_id, 
            user_id=current_user.id
        ).first()
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        # Cannot activate if not approved
        if is_active and exchange.status != 'APPROVED':
            return jsonify({
                'success': False, 
                'error': f'Біржу ще не затверджено. Статус: {exchange.status}'
            }), 400
        
        # Check if exchange is still enabled by admin
        config = ExchangeConfig.query.filter_by(exchange_name=exchange.exchange_name, is_enabled=True).first()
        if is_active and not config:
            return jsonify({
                'success': False,
                'error': 'Цю біржу вимкнено адміністратором'
            }), 400
        
        exchange.is_active = is_active
        exchange.trading_enabled = is_active  # Must set both for trading to work
        db.session.commit()
        
        logger.info(f"User {current_user.id} toggled exchange {exchange_id} to {'active' if is_active else 'inactive'}")
        
        return jsonify({
            'success': True,
            'message': f'Біржу {"активовано" if is_active else "деактивовано"}',
            'is_active': exchange.is_active
        })
        
    except Exception as e:
        logger.error(f"Error toggling exchange: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exchanges/<int:exchange_id>', methods=['DELETE'])
@login_required
def delete_user_exchange(exchange_id):
    """Delete user's exchange connection"""
    try:
        exchange = UserExchange.query.filter_by(
            id=exchange_id,
            user_id=current_user.id
        ).first()
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        db.session.delete(exchange)
        db.session.commit()
        
        logger.info(f"User {current_user.id} deleted exchange {exchange_id}")
        
        return jsonify({'success': True, 'message': 'Біржу видалено'})
        
    except Exception as e:
        logger.error(f"Error deleting exchange: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ADMIN EXCHANGE CONFIGURATION ====================

@app.route('/api/admin/exchange-configs', methods=['GET'])
@login_required
def admin_list_exchange_configs():
    """List all exchange configurations with verification status (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    # Initialize exchanges if they don't exist
    configs = ExchangeConfig.query.all()
    if not configs:
        init_exchange_configs()
        configs = ExchangeConfig.query.all()
    
    return jsonify([c.to_dict(include_admin_keys=True) for c in configs])


@app.route('/api/admin/exchange-configs/<exchange_name>/toggle', methods=['POST'])
@login_required
def admin_toggle_exchange_config(exchange_name):
    """Enable/disable an exchange for user connections (admin only)
    IMPORTANT: Can only enable if exchange is verified by admin"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        data = request.get_json()
        is_enabled = data.get('is_enabled', False)
        
        config = ExchangeConfig.query.filter_by(exchange_name=exchange_name).first()
        if not config:
            return jsonify({'success': False, 'error': 'Біржу не знайдено в конфігурації'}), 404
        
        # CRITICAL: Cannot enable if not verified
        if is_enabled and not config.is_verified:
            return jsonify({
                'success': False, 
                'error': 'Неможливо увімкнути біржу без верифікації. Спочатку підключіть свої API ключі.'
            }), 400
        
        config.is_enabled = is_enabled
        db.session.commit()
        
        # If disabling, deactivate all user exchanges for this exchange
        if not is_enabled:
            UserExchange.query.filter_by(exchange_name=exchange_name, is_active=True).update({'is_active': False})
            UserExchange.query.filter_by(exchange_name=exchange_name, trading_enabled=True).update({'trading_enabled': False})
            db.session.commit()
        
        logger.info(f"Admin {current_user.id} {'enabled' if is_enabled else 'disabled'} exchange {exchange_name}")
        audit.log_admin_action(current_user.username, "TOGGLE_EXCHANGE_CONFIG", exchange_name, f"Enabled: {is_enabled}")
        
        # CRITICAL: Reload master exchanges after toggling
        # This ensures newly enabled/disabled exchanges are picked up by the trading engine
        try:
            engine.init_master()
            logger.info(f"🔄 Master exchanges reloaded after toggling {exchange_name}")
        except Exception as e:
            logger.error(f"Failed to reload master exchanges: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Біржу {config.display_name} {"увімкнено" if is_enabled else "вимкнено"}',
            'is_enabled': config.is_enabled
        })
        
    except Exception as e:
        logger.error(f"Error toggling exchange config: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/exchange-configs/<exchange_name>/verify', methods=['POST'])
@login_required
def admin_verify_exchange(exchange_name):
    """Admin connects and verifies exchange with their own API keys"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        api_secret = data.get('api_secret', '').strip()
        passphrase = data.get('passphrase', '').strip() if data.get('passphrase') else None
        
        config = ExchangeConfig.query.filter_by(exchange_name=exchange_name).first()
        if not config:
            return jsonify({'success': False, 'error': 'Біржу не знайдено в конфігурації'}), 404
        
        # Validate required fields
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'API Key та API Secret обов\'язкові'}), 400
        
        # Validate passphrase requirement
        if config.requires_passphrase and not passphrase:
            return jsonify({'success': False, 'error': f'{config.display_name} вимагає passphrase'}), 400
        
        # Validate API key format
        valid, result = InputValidator.validate_api_key(api_key)
        if not valid:
            return jsonify({'success': False, 'error': f'Невірний API Key: {result}'}), 400
        
        valid, result = InputValidator.validate_api_key(api_secret)
        if not valid:
            return jsonify({'success': False, 'error': f'Невірний API Secret: {result}'}), 400
        
        # Test connection with CCXT
        from service_validator import validate_and_connect, ExchangeValidationError, ExchangeConnectionError
        
        try:
            logger.info(f"🔄 Admin verifying {exchange_name} credentials...")
            
            validation_result = validate_and_connect(
                exchange_name=exchange_name,
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase
            )
            
            if not validation_result.get('success'):
                config.is_verified = False
                config.verification_error = 'Не вдалося підключитися до біржі'
                db.session.commit()
                return jsonify({
                    'success': False,
                    'error': '❌ Не вдалося підключитися до біржі. Перевірте API ключі.'
                }), 400
            
            # Success! Save admin keys and mark as verified
            config.admin_api_key = api_key
            config.set_admin_api_secret(api_secret)
            if passphrase:
                config.set_admin_passphrase(passphrase)
            config.is_verified = True
            config.verified_at = datetime.now(timezone.utc)
            config.verification_error = None
            db.session.commit()
            
            logger.info(f"✅ Admin verified exchange {exchange_name}")
            audit.log_admin_action(current_user.username, "VERIFY_EXCHANGE", exchange_name, "Successfully verified")
            
            # Reload master exchanges if this exchange is also enabled
            # This ensures newly verified exchanges are immediately available for trading
            if config.is_enabled:
                try:
                    engine.init_master()
                    logger.info(f"🔄 Master exchanges reloaded after verifying {exchange_name}")
                except Exception as e:
                    logger.error(f"Failed to reload master exchanges: {e}")
            
            return jsonify({
                'success': True,
                'message': f'✅ Біржу {config.display_name} успішно верифіковано! Тепер ви можете увімкнути її для користувачів.',
                'balance': validation_result.get('balance'),
                'is_verified': True
            })
            
        except ExchangeConnectionError as e:
            config.is_verified = False
            config.verification_error = str(e)
            db.session.commit()
            logger.warning(f"Exchange connection error: {e}")
            return jsonify({
                'success': False,
                'error': f'❌ Помилка підключення: {str(e)}'
            }), 400
            
        except ExchangeValidationError as e:
            config.is_verified = False
            config.verification_error = str(e)
            db.session.commit()
            logger.warning(f"Exchange validation error: {e}")
            return jsonify({
                'success': False,
                'error': f'❌ Помилка валідації: {str(e)}'
            }), 400
        
    except Exception as e:
        logger.error(f"Error verifying exchange: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/exchange-configs/<exchange_name>/disconnect', methods=['POST'])
@login_required
def admin_disconnect_exchange(exchange_name):
    """Admin disconnects their API keys from exchange (also disables for users)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        config = ExchangeConfig.query.filter_by(exchange_name=exchange_name).first()
        if not config:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        # Clear admin keys and verification
        config.admin_api_key = None
        config.admin_api_secret = None
        config.admin_passphrase = None
        config.is_verified = False
        config.verified_at = None
        config.is_enabled = False  # Also disable for users
        
        # Deactivate all user exchanges for this exchange
        UserExchange.query.filter_by(exchange_name=exchange_name).update({
            'is_active': False,
            'trading_enabled': False
        })
        
        db.session.commit()
        
        logger.info(f"Admin disconnected exchange {exchange_name}")
        audit.log_admin_action(current_user.username, "DISCONNECT_EXCHANGE", exchange_name)
        
        return jsonify({
            'success': True,
            'message': f'Біржу {config.display_name} відключено'
        })
        
    except Exception as e:
        logger.error(f"Error disconnecting exchange: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ADMIN USER EXCHANGE MANAGEMENT ====================

@app.route('/api/admin/exchanges/pending', methods=['GET'])
@login_required
def admin_list_pending_exchanges():
    """List all pending exchange requests (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    pending = UserExchange.query.filter_by(status='PENDING').all()
    configs = {c.exchange_name: c.display_name for c in ExchangeConfig.query.all()}
    
    result = []
    for ex in pending:
        user = db.session.get(User, ex.user_id)
        result.append({
            'id': ex.id,
            'user_id': ex.user_id,
            'user_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username if user else 'Unknown',
            'user_username': user.username if user else 'Unknown',
            'exchange_name': ex.exchange_name,
            'display_name': configs.get(ex.exchange_name, ex.exchange_name.upper()),
            'label': ex.label,
            'api_key': ex.api_key[:8] + '...' + ex.api_key[-4:] if ex.api_key and len(ex.api_key) > 12 else '***',
            'error_message': ex.error_message,
            'created_at': ex.created_at.strftime('%d.%m.%Y %H:%M') if ex.created_at else None
        })
    
    return jsonify(result)


@app.route('/api/admin/exchanges/all', methods=['GET'])
@login_required
def admin_list_all_exchanges():
    """List all user exchanges (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    user_id = request.args.get('user_id', type=int)
    
    query = UserExchange.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    exchanges = query.all()
    configs = {c.exchange_name: c.display_name for c in ExchangeConfig.query.all()}
    
    result = []
    for ex in exchanges:
        user = db.session.get(User, ex.user_id)
        result.append({
            'id': ex.id,
            'user_id': ex.user_id,
            'user_name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username if user else 'Unknown',
            'user_username': user.username if user else 'Unknown',
            'exchange_name': ex.exchange_name,
            'display_name': configs.get(ex.exchange_name, ex.exchange_name.upper()),
            'label': ex.label,
            'api_key': ex.api_key[:8] + '...' + ex.api_key[-4:] if ex.api_key and len(ex.api_key) > 12 else '***',
            'status': ex.status,
            'is_active': ex.is_active,
            'trading_enabled': ex.trading_enabled,
            'error_message': ex.error_message,
            'created_at': ex.created_at.strftime('%d.%m.%Y %H:%M') if ex.created_at else None
        })
    
    return jsonify(result)


@app.route('/api/admin/exchanges/<int:exchange_id>/approve', methods=['POST'])
@login_required
def admin_approve_exchange(exchange_id):
    """Approve user's exchange connection (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        data = request.get_json() or {}
        auto_enable_trading = data.get('auto_enable_trading', False)
        
        exchange = db.session.get(UserExchange, exchange_id)
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        if exchange.status != 'PENDING':
            return jsonify({'success': False, 'error': f'Біржа вже оброблена: {exchange.status}'}), 400
        
        exchange.status = 'APPROVED'
        exchange.error_message = None
        if auto_enable_trading:
            exchange.trading_enabled = True
            exchange.is_active = True
        db.session.commit()
        
        # Get display name
        config = ExchangeConfig.query.filter_by(exchange_name=exchange.exchange_name).first()
        display_name = config.display_name if config else exchange.exchange_name.upper()
        
        # Notify user
        user = db.session.get(User, exchange.user_id)
        if user and user.telegram_chat_id and user.telegram_enabled and telegram:
            telegram.send(
                f"✅ Вашу біржу {exchange.label} ({display_name}) затверджено! "
                f"Тепер ви можете активувати її в налаштуваннях.",
                chat_id=user.telegram_chat_id
            )
        
        logger.info(f"Admin {current_user.id} approved exchange {exchange_id} for user {exchange.user_id}")
        audit.log_admin_action(current_user.username, "APPROVE_EXCHANGE", f"Exchange ID: {exchange_id}")
        
        return jsonify({
            'success': True,
            'message': 'Біржу затверджено'
        })
        
    except Exception as e:
        logger.error(f"Error approving exchange: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/exchanges/<int:exchange_id>/reject', methods=['POST'])
@login_required
def admin_reject_exchange(exchange_id):
    """Reject user's exchange connection (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        data = request.get_json()
        reason = data.get('reason', 'Відхилено адміністратором')
        
        exchange = db.session.get(UserExchange, exchange_id)
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        if exchange.status != 'PENDING':
            return jsonify({'success': False, 'error': f'Біржа вже оброблена: {exchange.status}'}), 400
        
        exchange.status = 'REJECTED'
        exchange.error_message = reason
        exchange.is_active = False
        db.session.commit()
        
        # Get display name
        config = ExchangeConfig.query.filter_by(exchange_name=exchange.exchange_name).first()
        display_name = config.display_name if config else exchange.exchange_name.upper()
        
        # Notify user
        user = db.session.get(User, exchange.user_id)
        if user and user.telegram_chat_id and user.telegram_enabled and telegram:
            telegram.send(
                f"❌ Вашу біржу {exchange.label} ({display_name}) відхилено.\n"
                f"Причина: {reason}",
                chat_id=user.telegram_chat_id
            )
        
        logger.info(f"Admin {current_user.id} rejected exchange {exchange_id}: {reason}")
        audit.log_admin_action(current_user.username, "REJECT_EXCHANGE", f"Exchange ID: {exchange_id}", reason)
        
        return jsonify({
            'success': True,
            'message': 'Біржу відхилено'
        })
        
    except Exception as e:
        logger.error(f"Error rejecting exchange: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/exchanges/<int:exchange_id>/test', methods=['POST'])
@login_required
def admin_test_exchange(exchange_id):
    """Test user's exchange connection (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        exchange = db.session.get(UserExchange, exchange_id)
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        api_secret = exchange.get_api_secret()
        passphrase = exchange.get_passphrase()
        
        from service_validator import validate_and_connect, ExchangeValidationError, ExchangeConnectionError
        
        try:
            result = validate_and_connect(
                exchange_name=exchange.exchange_name,
                api_key=exchange.api_key,
                api_secret=api_secret,
                passphrase=passphrase
            )
            
            if result.get('success'):
                exchange.error_message = None
                db.session.commit()
                return jsonify({
                    'success': True,
                    'message': 'Підключення успішне!',
                    'balance': result.get('balance')
                })
            else:
                exchange.error_message = 'Помилка підключення'
                db.session.commit()
                return jsonify({'success': False, 'error': 'Не вдалося підключитися'}), 400
                
        except (ExchangeValidationError, ExchangeConnectionError) as e:
            exchange.error_message = str(e)
            db.session.commit()
            return jsonify({'success': False, 'error': str(e)}), 400
        
    except Exception as e:
        logger.error(f"Error testing exchange: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/exchanges/pending/count', methods=['GET'])
@login_required
def admin_pending_exchanges_count():
    """Get count of pending exchanges (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    count = UserExchange.query.filter_by(status='PENDING').count()
    return jsonify({'count': count})


# ==================== ADMIN USER EXCHANGE TRADING MANAGEMENT ====================

@app.route('/api/admin/exchanges/<int:exchange_id>/start-trading', methods=['POST'])
@login_required
def admin_start_user_trading(exchange_id):
    """Admin enables trading for a user's exchange"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        exchange = db.session.get(UserExchange, exchange_id)
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        # Check if exchange is approved
        if exchange.status != 'APPROVED':
            return jsonify({
                'success': False,
                'error': f'Біржу ще не затверджено. Статус: {exchange.status}'
            }), 400
        
        # Check if exchange config is enabled
        config = ExchangeConfig.query.filter_by(exchange_name=exchange.exchange_name, is_enabled=True).first()
        if not config:
            return jsonify({
                'success': False,
                'error': 'Цю біржу вимкнено в конфігурації'
            }), 400
        
        exchange.trading_enabled = True
        exchange.is_active = True  # Also activate the exchange
        db.session.commit()
        
        # Get user for notification
        user = db.session.get(User, exchange.user_id)
        
        logger.info(f"Admin {current_user.id} enabled trading for exchange {exchange_id} (user {exchange.user_id})")
        audit.log_admin_action(current_user.username, "START_USER_TRADING", f"Exchange ID: {exchange_id}, User: {user.username if user else 'Unknown'}")
        
        # Notify user
        if user and user.telegram_chat_id and user.telegram_enabled and telegram:
            telegram.send(
                f"🚀 Торгівлю на біржі {exchange.label} ({config.display_name}) увімкнено адміністратором!",
                chat_id=user.telegram_chat_id
            )
        
        return jsonify({
            'success': True,
            'message': 'Торгівлю увімкнено',
            'trading_enabled': True
        })
        
    except Exception as e:
        logger.error(f"Error starting user trading: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/exchanges/<int:exchange_id>/stop-trading', methods=['POST'])
@login_required
def admin_stop_user_trading(exchange_id):
    """Admin disables trading for a user's exchange"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        exchange = db.session.get(UserExchange, exchange_id)
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        exchange.trading_enabled = False
        db.session.commit()
        
        # Get user for notification and display name
        user = db.session.get(User, exchange.user_id)
        config = ExchangeConfig.query.filter_by(exchange_name=exchange.exchange_name).first()
        display_name = config.display_name if config else exchange.exchange_name.upper()
        
        logger.info(f"Admin {current_user.id} disabled trading for exchange {exchange_id} (user {exchange.user_id})")
        audit.log_admin_action(current_user.username, "STOP_USER_TRADING", f"Exchange ID: {exchange_id}, User: {user.username if user else 'Unknown'}")
        
        # Notify user
        if user and user.telegram_chat_id and user.telegram_enabled and telegram:
            telegram.send(
                f"⏸️ Торгівлю на біржі {exchange.label} ({display_name}) призупинено адміністратором.",
                chat_id=user.telegram_chat_id
            )
        
        return jsonify({
            'success': True,
            'message': 'Торгівлю зупинено',
            'trading_enabled': False
        })
        
    except Exception as e:
        logger.error(f"Error stopping user trading: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/exchanges/<int:exchange_id>/trading', methods=['POST'])
@login_required
def admin_toggle_user_trading(exchange_id):
    """Admin toggles trading for a user's exchange"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        data = request.get_json(force=True, silent=True) or {}
        trading_enabled = data.get('trading_enabled', False)
        
        exchange = db.session.get(UserExchange, exchange_id)
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        # Check if exchange is approved
        if exchange.status != 'APPROVED':
            return jsonify({'success': False, 'error': 'Біржу не затверджено'}), 400
        
        # Check if exchange config is enabled
        config = ExchangeConfig.query.filter_by(exchange_name=exchange.exchange_name).first()
        if trading_enabled and config and not config.is_enabled:
            return jsonify({
                'success': False,
                'error': 'Цю біржу вимкнено в конфігурації'
            }), 400
        
        exchange.trading_enabled = trading_enabled
        if trading_enabled:
            exchange.is_active = True
        db.session.commit()
        
        # Get user for notification
        user = db.session.get(User, exchange.user_id)
        display_name = config.display_name if config else exchange.exchange_name.upper()
        
        action = "START_USER_TRADING" if trading_enabled else "STOP_USER_TRADING"
        logger.info(f"Admin {current_user.id} {'enabled' if trading_enabled else 'disabled'} trading for exchange {exchange_id} (user {exchange.user_id})")
        audit.log_admin_action(current_user.username, action, f"Exchange ID: {exchange_id}, User: {user.username if user else 'Unknown'}")
        
        # Notify user
        if user and user.telegram_chat_id and user.telegram_enabled and telegram:
            if trading_enabled:
                telegram.send(
                    f"▶️ Торгівлю на біржі {exchange.label} ({display_name}) запущено!",
                    chat_id=user.telegram_chat_id
                )
            else:
                telegram.send(
                    f"⏸️ Торгівлю на біржі {exchange.label} ({display_name}) призупинено адміністратором.",
                    chat_id=user.telegram_chat_id
                )
        
        return jsonify({
            'success': True,
            'message': 'Торгівлю увімкнено' if trading_enabled else 'Торгівлю зупинено',
            'trading_enabled': trading_enabled
        })
        
    except Exception as e:
        logger.error(f"Error toggling user trading: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/exchanges/<int:exchange_id>/delete', methods=['DELETE'])
@login_required
def admin_delete_user_exchange(exchange_id):
    """Admin deletes a user's exchange connection"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        exchange = db.session.get(UserExchange, exchange_id)
        
        if not exchange:
            return jsonify({'success': False, 'error': 'Біржу не знайдено'}), 404
        
        # Get user for notification
        user = db.session.get(User, exchange.user_id)
        config = ExchangeConfig.query.filter_by(exchange_name=exchange.exchange_name).first()
        display_name = config.display_name if config else exchange.exchange_name.upper()
        exchange_label = exchange.label
        user_id = exchange.user_id
        
        db.session.delete(exchange)
        db.session.commit()
        
        logger.info(f"Admin {current_user.id} deleted exchange {exchange_id} for user {user_id}")
        audit.log_admin_action(current_user.username, "DELETE_USER_EXCHANGE", f"Exchange ID: {exchange_id}, User: {user.username if user else 'Unknown'}")
        
        # Notify user
        if user and user.telegram_chat_id and user.telegram_enabled and telegram:
            telegram.send(
                f"🗑️ Біржу {exchange_label} ({display_name}) видалено адміністратором.",
                chat_id=user.telegram_chat_id
            )
        
        return jsonify({
            'success': True,
            'message': 'Біржу видалено'
        })
        
    except Exception as e:
        logger.error(f"Error deleting user exchange: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== STRATEGY MANAGEMENT API ====================

@app.route('/api/strategies', methods=['GET'])
@login_required
def get_strategies():
    """Get all available strategies (for users to subscribe to)"""
    try:
        strategies = Strategy.query.filter_by(is_active=True).all()
        
        return jsonify({
            'success': True,
            'strategies': [s.to_dict(include_stats=True) for s in strategies]
        })
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/subscriptions', methods=['GET'])
@login_required
def get_user_subscriptions():
    """Get current user's strategy subscriptions"""
    try:
        subscriptions = StrategySubscription.query.filter_by(
            user_id=current_user.id
        ).all()
        
        total_allocation = sum(s.allocation_percent for s in subscriptions if s.is_active)
        
        return jsonify({
            'success': True,
            'subscriptions': [s.to_dict() for s in subscriptions],
            'total_allocation': total_allocation,
            'remaining_allocation': 100.0 - total_allocation
        })
    except Exception as e:
        logger.error(f"Error fetching user subscriptions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/subscriptions', methods=['POST'])
@login_required
def create_subscription():
    """Subscribe to a strategy"""
    try:
        data = request.get_json()
        strategy_id = data.get('strategy_id')
        allocation_percent = float(data.get('allocation_percent', 100.0))
        
        if not strategy_id:
            return jsonify({'error': 'Потрібен strategy_id'}), 400
        
        if allocation_percent <= 0 or allocation_percent > 100:
            return jsonify({'error': 'allocation_percent must be between 0 and 100'}), 400
        
        # Check strategy exists and is active
        strategy = Strategy.query.get(strategy_id)
        if not strategy or not strategy.is_active:
            return jsonify({'error': 'Стратегію не знайдено або вона неактивна'}), 404
        
        # Check if already subscribed
        existing = StrategySubscription.query.filter_by(
            user_id=current_user.id,
            strategy_id=strategy_id
        ).first()
        
        if existing:
            return jsonify({'error': 'Already subscribed to this strategy. Use PUT to update allocation.'}), 400
        
        # Validate total allocation won't exceed 100%
        is_valid, current_total, message = StrategySubscription.validate_user_allocations(
            current_user.id, allocation_percent
        )
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Create subscription
        subscription = StrategySubscription(
            user_id=current_user.id,
            strategy_id=strategy_id,
            allocation_percent=allocation_percent,
            is_active=True
        )
        db.session.add(subscription)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Subscribed to {strategy.name} with {allocation_percent}% allocation',
            'subscription': subscription.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/subscriptions/<int:subscription_id>', methods=['PUT'])
@login_required
def update_subscription(subscription_id):
    """Update a subscription's allocation percent or active status"""
    try:
        subscription = StrategySubscription.query.get(subscription_id)
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        if subscription.user_id != current_user.id:
            return jsonify({'error': 'Неавторизовано'}), 403
        
        data = request.get_json()
        
        # Update allocation percent if provided
        if 'allocation_percent' in data:
            allocation_percent = float(data['allocation_percent'])
            if allocation_percent <= 0 or allocation_percent > 100:
                return jsonify({'error': 'allocation_percent must be between 0 and 100'}), 400
            
            # Validate total allocation won't exceed 100%
            is_valid, current_total, message = StrategySubscription.validate_user_allocations(
                current_user.id, allocation_percent, exclude_subscription_id=subscription_id
            )
            if not is_valid:
                return jsonify({'error': message}), 400
            
            subscription.allocation_percent = allocation_percent
        
        # Update active status if provided
        if 'is_active' in data:
            subscription.is_active = bool(data['is_active'])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Subscription updated',
            'subscription': subscription.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating subscription: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/subscriptions/<int:subscription_id>', methods=['DELETE'])
@login_required
def delete_subscription(subscription_id):
    """Unsubscribe from a strategy"""
    try:
        subscription = StrategySubscription.query.get(subscription_id)
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        if subscription.user_id != current_user.id:
            return jsonify({'error': 'Неавторизовано'}), 403
        
        strategy_name = subscription.strategy.name if subscription.strategy else 'Unknown'
        
        db.session.delete(subscription)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Unsubscribed from {strategy_name}'
        })
        
    except Exception as e:
        logger.error(f"Error deleting subscription: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== ADMIN STRATEGY MANAGEMENT ====================

@app.route('/api/admin/strategies', methods=['GET'])
@login_required
def admin_get_strategies():
    """Get all strategies (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        strategies = Strategy.query.all()
        return jsonify({
            'success': True,
            'strategies': [s.to_dict(include_stats=True) for s in strategies]
        })
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/strategies', methods=['POST'])
@login_required
def admin_create_strategy():
    """Create a new strategy (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Strategy name is required'}), 400
        
        # Check if name already exists
        existing = Strategy.query.filter_by(name=name).first()
        if existing:
            return jsonify({'error': f'Strategy "{name}" already exists'}), 400
        
        strategy = Strategy(
            name=name,
            description=data.get('description', ''),
            risk_level=data.get('risk_level', 'medium'),
            master_exchange_id=data.get('master_exchange_id'),
            default_risk_perc=data.get('default_risk_perc'),
            default_leverage=data.get('default_leverage'),
            max_positions=data.get('max_positions'),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(strategy)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Strategy "{name}" created',
            'strategy': strategy.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/strategies/<int:strategy_id>', methods=['PUT'])
@login_required
def admin_update_strategy(strategy_id):
    """Update a strategy (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        strategy = Strategy.query.get(strategy_id)
        if not strategy:
            return jsonify({'error': 'Strategy not found'}), 404
        
        data = request.get_json()
        
        # Update fields if provided
        if 'name' in data:
            new_name = data['name'].strip()
            if new_name and new_name != strategy.name:
                existing = Strategy.query.filter_by(name=new_name).first()
                if existing:
                    return jsonify({'error': f'Strategy "{new_name}" already exists'}), 400
                strategy.name = new_name
        
        if 'description' in data:
            strategy.description = data['description']
        if 'risk_level' in data:
            strategy.risk_level = data['risk_level']
        if 'master_exchange_id' in data:
            strategy.master_exchange_id = data['master_exchange_id']
        if 'default_risk_perc' in data:
            strategy.default_risk_perc = data['default_risk_perc']
        if 'default_leverage' in data:
            strategy.default_leverage = data['default_leverage']
        if 'max_positions' in data:
            strategy.max_positions = data['max_positions']
        if 'is_active' in data:
            strategy.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Strategy updated',
            'strategy': strategy.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/strategies/<int:strategy_id>', methods=['DELETE'])
@login_required
def admin_delete_strategy(strategy_id):
    """Delete a strategy (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        strategy = Strategy.query.get(strategy_id)
        if not strategy:
            return jsonify({'error': 'Strategy not found'}), 404
        
        # Check if this is the default strategy
        if strategy.name == 'Main':
            return jsonify({'error': 'Cannot delete the default "Main" strategy'}), 400
        
        # Check for active subscriptions
        active_subs = strategy.subscriptions.filter_by(is_active=True).count()
        if active_subs > 0:
            return jsonify({
                'error': f'Неможливо видалити стратегію з {active_subs} активними підписниками. Спочатку деактивуй її.'
            }), 400
        
        strategy_name = strategy.name
        db.session.delete(strategy)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Strategy "{strategy_name}" deleted'
        })
        
    except Exception as e:
        logger.error(f"Error deleting strategy: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/strategies/<int:strategy_id>/subscribers', methods=['GET'])
@login_required
def admin_get_strategy_subscribers(strategy_id):
    """Get all subscribers of a strategy (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        strategy = Strategy.query.get(strategy_id)
        if not strategy:
            return jsonify({'error': 'Strategy not found'}), 404
        
        subscriptions = strategy.subscriptions.all()
        
        subscribers = []
        for sub in subscriptions:
            user = db.session.get(User, sub.user_id)
            subscribers.append({
                'subscription_id': sub.id,
                'user_id': sub.user_id,
                'username': user.username if user else 'Unknown',
                'allocation_percent': sub.allocation_percent,
                'is_active': sub.is_active,
                'created_at': sub.created_at.isoformat() if sub.created_at else None
            })
        
        return jsonify({
            'success': True,
            'strategy': strategy.to_dict(),
            'subscribers': subscribers,
            'total_subscribers': len([s for s in subscribers if s['is_active']])
        })
        
    except Exception as e:
        logger.error(f"Error fetching strategy subscribers: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/user/<int:user_id>/balances', methods=['GET'])
@login_required
def admin_get_user_balances(user_id):
    """Get balances for all connected exchanges of a user (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': 'Користувача не знайдено'}), 404
        
        # Get balances from all exchanges
        balance_data = get_user_exchange_balances(user_id)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'username': user.username,
            'total_balance': balance_data['total'],
            'exchanges': balance_data['exchanges']
        })
        
    except Exception as e:
        logger.error(f"Error fetching user balances: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/users/balances', methods=['GET'])
@login_required
def admin_get_all_user_balances():
    """Get balances for all users across all exchanges (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        users = User.query.filter(User.role != 'admin').all()
        
        result = []
        for user in users:
            balance_data = get_user_exchange_balances(user.id)
            result.append({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'is_active': user.is_active,
                'is_paused': user.is_paused,
                'total_balance': balance_data['total'],
                'exchanges': balance_data['exchanges']
            })
        
        return jsonify({
            'success': True,
            'users': result
        })
        
    except Exception as e:
        logger.error(f"Error fetching all user balances: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/user/<int:user_id>/exchanges', methods=['GET'])
@login_required
def admin_get_user_exchanges(user_id):
    """Get all exchanges for a specific user (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': 'Користувача не знайдено'}), 404
        
        exchanges = UserExchange.query.filter_by(user_id=user_id).all()
        configs = {c.exchange_name: c.display_name for c in ExchangeConfig.query.all()}
        
        result = []
        for ex in exchanges:
            result.append({
                'id': ex.id,
                'user_id': ex.user_id,
                'exchange_name': ex.exchange_name,
                'display_name': configs.get(ex.exchange_name, ex.exchange_name.upper()),
                'label': ex.label,
                'api_key': ex.api_key[:8] + '...' + ex.api_key[-4:] if ex.api_key and len(ex.api_key) > 12 else '***',
                'status': ex.status,
                'is_active': ex.is_active,
                'trading_enabled': ex.trading_enabled,
                'error_message': ex.error_message,
                'created_at': ex.created_at.strftime('%d.%m.%Y %H:%M') if ex.created_at else None
            })
        
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
            },
            'exchanges': result
        })
        
    except Exception as e:
        logger.error(f"Error getting user exchanges: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SYSTEM SETTINGS API ROUTES ====================
# Admin endpoints for managing service configurations (Telegram, Plisio, Email, etc.)

@app.route('/api/admin/system-settings', methods=['GET'])
@login_required
def admin_get_system_settings():
    """Get all system settings grouped by category (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting, SERVICE_CATEGORIES
        
        # Ensure defaults are initialized
        if SystemSetting.query.count() == 0:
            SystemSetting.initialize_defaults()
        
        settings = SystemSetting.get_all_grouped()
        
        # Add category metadata
        categories_with_meta = {}
        for category, meta in SERVICE_CATEGORIES.items():
            categories_with_meta[category] = {
                'meta': meta,
                'settings': settings.get(category, [])
            }
        
        # Add any settings in categories not in SERVICE_CATEGORIES
        for category in settings:
            if category not in categories_with_meta:
                categories_with_meta[category] = {
                    'meta': {
                        'name': category.title(),
                        'icon': 'fas fa-cog',
                        'color': '#6c757d',
                        'description': f'{category.title()} settings'
                    },
                    'settings': settings[category]
                }
        
        return jsonify({
            'success': True,
            'categories': categories_with_meta
        })
        
    except Exception as e:
        logger.error(f"Error getting system settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/system-settings/<category>', methods=['GET'])
@login_required
def admin_get_category_settings(category):
    """Get settings for a specific category (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting, SERVICE_CATEGORIES
        
        settings = SystemSetting.query.filter_by(category=category).all()
        meta = SERVICE_CATEGORIES.get(category, {
            'name': category.title(),
            'icon': 'fas fa-cog',
            'color': '#6c757d',
            'description': f'{category.title()} settings'
        })
        
        # Check if service is enabled
        enabled_setting = next((s for s in settings if s.key == 'enabled'), None)
        is_enabled = enabled_setting and enabled_setting.get_value().lower() in ('true', '1', 'yes')
        
        return jsonify({
            'success': True,
            'category': category,
            'meta': meta,
            'is_enabled': is_enabled,
            'settings': [s.to_dict() for s in settings]
        })
        
    except Exception as e:
        logger.error(f"Error getting category settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/system-settings/<category>/<key>', methods=['PUT'])
@login_required
def admin_update_setting(category, key):
    """Update a specific setting (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Дані не надано'}), 400
        
        value = data.get('value', '')
        
        # Find or create the setting
        setting = SystemSetting.query.filter_by(category=category, key=key).first()
        
        if setting:
            setting.set_value(value)
            setting.updated_by_id = current_user.id
            db.session.commit()
            logger.info(f"✏️ Admin {current_user.username} updated setting {category}.{key}")
        else:
            # Create new setting
            is_sensitive = data.get('is_sensitive', False)
            description = data.get('description', '')
            setting = SystemSetting.set_setting(
                category=category,
                key=key,
                value=value,
                is_sensitive=is_sensitive,
                description=description,
                updated_by_id=current_user.id
            )
            logger.info(f"✏️ Admin {current_user.username} created setting {category}.{key}")
        
        return jsonify({
            'success': True,
            'setting': setting.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating setting: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/system-settings/<category>/bulk', methods=['PUT'])
@login_required
def admin_update_category_settings(category):
    """Update multiple settings for a category at once (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting, SERVICE_CATEGORIES
        
        data = request.get_json()
        if not data or 'settings' not in data:
            return jsonify({'success': False, 'error': 'No settings provided'}), 400
        
        settings_data = data['settings']
        updated = []
        
        for key, value in settings_data.items():
            # Skip empty values for sensitive fields unless explicitly clearing
            setting = SystemSetting.query.filter_by(category=category, key=key).first()
            
            if setting:
                # Don't overwrite sensitive values with empty strings unless marked for clear
                if setting.is_sensitive and value == '' and not data.get('clear_sensitive'):
                    continue
                    
                setting.set_value(str(value))
                setting.updated_by_id = current_user.id
                updated.append(key)
            else:
                # Check if this is a known sensitive field
                is_sensitive = key in ('api_key', 'api_secret', 'secret', 'password', 
                                      'bot_token', 'webhook_secret', 'access_token',
                                      'access_secret', 'vapid_private_key', 'otp_secret')
                SystemSetting.set_setting(
                    category=category,
                    key=key,
                    value=str(value),
                    is_sensitive=is_sensitive,
                    updated_by_id=current_user.id
                )
                updated.append(key)
        
        db.session.commit()
        logger.info(f"✏️ Admin {current_user.username} bulk updated {category}: {updated}")
        
        # Get updated settings
        settings = SystemSetting.query.filter_by(category=category).all()
        
        return jsonify({
            'success': True,
            'updated': updated,
            'settings': [s.to_dict() for s in settings]
        })
        
    except Exception as e:
        logger.error(f"Error bulk updating settings: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/system-settings/<category>/toggle', methods=['POST'])
@login_required
def admin_toggle_service(category):
    """Toggle a service category on/off (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting
        
        data = request.get_json()
        enabled = data.get('enabled', False) if data else False
        
        # Find or create the enabled setting
        setting = SystemSetting.query.filter_by(category=category, key='enabled').first()
        
        if setting:
            setting.set_value('true' if enabled else 'false')
            setting.is_enabled = enabled
            setting.updated_by_id = current_user.id
        else:
            setting = SystemSetting(
                category=category,
                key='enabled',
                is_enabled=enabled,
                is_sensitive=False,
                description=f'Enable/disable {category} service'
            )
            setting.set_value('true' if enabled else 'false')
            setting.updated_by_id = current_user.id
            db.session.add(setting)
        
        db.session.commit()
        
        status = "enabled" if enabled else "disabled"
        logger.info(f"🔄 Admin {current_user.username} {status} service: {category}")
        
        return jsonify({
            'success': True,
            'category': category,
            'enabled': enabled
        })
        
    except Exception as e:
        logger.error(f"Error toggling service: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/system-settings/<category>/test', methods=['POST'])
@login_required
def admin_test_service(category):
    """Test a service connection/configuration (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting
        
        settings = SystemSetting.get_category_settings(category)
        
        if category == 'telegram':
            # Test Telegram bot connection
            bot_token = settings.get('bot_token', '')
            if not bot_token:
                return jsonify({'success': False, 'error': 'Telegram bot token not configured'}), 400
            
            import httpx
            try:
                response = httpx.get(f'https://api.telegram.org/bot{bot_token}/getMe', timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        bot_info = data.get('result', {})
                        return jsonify({
                            'success': True,
                            'message': f"✅ Connected to @{bot_info.get('username', 'Unknown')}",
                            'details': {
                                'username': bot_info.get('username'),
                                'name': bot_info.get('first_name'),
                                'can_read_messages': bot_info.get('can_read_all_group_messages', False)
                            }
                        })
                return jsonify({'success': False, 'error': 'Невірний токен бота або помилка API'}), 400
            except Exception as e:
                return jsonify({'success': False, 'error': f'Connection failed: {str(e)}'}), 400
        
        elif category == 'email':
            # Test SMTP connection
            smtp_server = settings.get('smtp_server', '')
            smtp_port = int(settings.get('smtp_port', 587))
            smtp_username = settings.get('smtp_username', '')
            smtp_password = settings.get('smtp_password', '')
            
            if not all([smtp_server, smtp_username, smtp_password]):
                return jsonify({'success': False, 'error': 'SMTP configuration incomplete'}), 400
            
            import smtplib
            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                    return jsonify({
                        'success': True,
                        'message': f"✅ Connected to {smtp_server}",
                        'details': {'server': smtp_server, 'port': smtp_port}
                    })
            except Exception as e:
                return jsonify({'success': False, 'error': f'SMTP connection failed: {str(e)}'}), 400
        
        elif category == 'payment':
            # Test Plisio API connection
            api_key = settings.get('api_key', '')
            if not api_key:
                return jsonify({'success': False, 'error': 'Plisio API key not configured'}), 400
            
            import httpx
            try:
                response = httpx.get(
                    f'https://plisio.net/api/v1/currencies?api_key={api_key}',
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        return jsonify({
                            'success': True,
                            'message': '✅ Connected to Plisio API',
                            'details': {'currencies_available': len(data.get('data', {}))}
                        })
                return jsonify({'success': False, 'error': 'Невірний API ключ або помилка API'}), 400
            except Exception as e:
                return jsonify({'success': False, 'error': f'Connection failed: {str(e)}'}), 400
        
        elif category == 'openai':
            # Test OpenAI API connection
            api_key = settings.get('api_key', '')
            if not api_key:
                return jsonify({'success': False, 'error': 'OpenAI API key not configured'}), 400
            
            import httpx
            try:
                response = httpx.get(
                    'https://api.openai.com/v1/models',
                    headers={'Authorization': f'Bearer {api_key}'},
                    timeout=10
                )
                if response.status_code == 200:
                    return jsonify({
                        'success': True,
                        'message': '✅ Connected to OpenAI API',
                        'details': {'models_available': True}
                    })
                elif response.status_code == 401:
                    return jsonify({'success': False, 'error': 'Невірний OpenAI API ключ'}), 400
                return jsonify({'success': False, 'error': f'API error: {response.status_code}'}), 400
            except Exception as e:
                return jsonify({'success': False, 'error': f'Connection failed: {str(e)}'}), 400
        
        elif category == 'binance':
            # Test Binance API connection
            api_key = settings.get('api_key', '')
            api_secret = settings.get('api_secret', '')
            testnet = settings.get('testnet', 'false').lower() == 'true'
            
            if not all([api_key, api_secret]):
                return jsonify({'success': False, 'error': 'Binance API credentials not configured'}), 400
            
            try:
                from binance.um_futures import UMFutures
                
                base_url = 'https://testnet.binancefuture.com' if testnet else 'https://fapi.binance.com'
                client = UMFutures(key=api_key, secret=api_secret, base_url=base_url)
                account = client.account()
                
                return jsonify({
                    'success': True,
                    'message': f"✅ Connected to Binance {'Testnet' if testnet else 'Live'}",
                    'details': {
                        'testnet': testnet,
                        'balance': float(account.get('totalWalletBalance', 0)),
                        'unrealized_pnl': float(account.get('totalUnrealizedProfit', 0))
                    }
                })
            except Exception as e:
                return jsonify({'success': False, 'error': f'Binance connection failed: {str(e)}'}), 400
        
        elif category == 'twitter':
            # Test Twitter API - just validate credentials format
            api_key = settings.get('api_key', '')
            api_secret = settings.get('api_secret', '')
            access_token = settings.get('access_token', '')
            access_secret = settings.get('access_secret', '')
            
            if not all([api_key, api_secret, access_token, access_secret]):
                return jsonify({'success': False, 'error': 'Twitter credentials incomplete'}), 400
            
            # Basic format validation
            if len(api_key) < 10 or len(api_secret) < 10:
                return jsonify({'success': False, 'error': 'Невірний формат Twitter API ключа'}), 400
            
            return jsonify({
                'success': True,
                'message': '✅ Twitter credentials configured',
                'details': {'note': 'Full validation requires posting test tweet'}
            })
        
        else:
            return jsonify({
                'success': True,
                'message': f'No test available for {category}',
                'details': {}
            })
        
    except Exception as e:
        logger.error(f"Error testing service {category}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/system-settings/initialize', methods=['POST'])
@login_required
def admin_initialize_settings():
    """Initialize default settings if not present (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting
        
        before_count = SystemSetting.query.count()
        SystemSetting.initialize_defaults()
        after_count = SystemSetting.query.count()
        
        new_settings = after_count - before_count
        
        logger.info(f"✏️ Admin {current_user.username} initialized system settings (+{new_settings})")
        
        return jsonify({
            'success': True,
            'message': f'Initialized {new_settings} new settings',
            'total': after_count
        })
        
    except Exception as e:
        logger.error(f"Error initializing settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/system-settings/export', methods=['GET'])
@login_required
def admin_export_settings():
    """Export all settings (excluding sensitive values) for backup (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting, SERVICE_CATEGORIES
        from datetime import datetime
        
        settings = SystemSetting.query.all()
        
        export_data = {
            'export_date': datetime.now().isoformat(),
            'export_by': current_user.username,
            'settings': []
        }
        
        for s in settings:
            setting_data = {
                'category': s.category,
                'key': s.key,
                'is_sensitive': s.is_sensitive,
                'description': s.description,
            }
            # Only include non-sensitive values
            if not s.is_sensitive:
                setting_data['value'] = s.get_value()
            export_data['settings'].append(setting_data)
        
        return jsonify({
            'success': True,
            'data': export_data
        })
        
    except Exception as e:
        logger.error(f"Error exporting settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/system-settings/service-status', methods=['GET'])
@login_required
def admin_get_service_status():
    """Get quick status overview of all services (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Неавторизовано'}), 403
    
    try:
        from models import SystemSetting, SERVICE_CATEGORIES
        
        services = []
        
        for category, meta in SERVICE_CATEGORIES.items():
            settings = SystemSetting.get_category_settings(category)
            
            # Check if enabled
            enabled_value = settings.get('enabled', 'false')
            is_enabled = enabled_value.lower() in ('true', '1', 'yes')
            
            # Check if configured (has required fields)
            required_fields = {
                'telegram': ['bot_token'],
                'email': ['smtp_server', 'smtp_username', 'smtp_password'],
                'payment': ['api_key'],
                'twitter': ['api_key', 'api_secret', 'access_token', 'access_secret'],
                'openai': ['api_key'],
                'webpush': ['vapid_public_key', 'vapid_private_key'],
                'binance': ['api_key', 'api_secret'],
                'webhook': ['passphrase'],
            }
            
            is_configured = True
            for field in required_fields.get(category, []):
                if not settings.get(field):
                    is_configured = False
                    break
            
            services.append({
                'category': category,
                'name': meta['name'],
                'icon': meta['icon'],
                'color': meta['color'],
                'is_enabled': is_enabled,
                'is_configured': is_configured,
                'status': 'active' if (is_enabled and is_configured) else ('configured' if is_configured else 'unconfigured')
            })
        
        return jsonify({
            'success': True,
            'services': services
        })
        
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== PAYMENT API ROUTES ====================
# Subscription system with Plisio crypto payment integration

import httpx
import hashlib

# Plisio API configuration
PLISIO_API_URL = "https://plisio.net/api/v1"


@app.route('/api/payment/plans', methods=['GET'])
def get_payment_plans():
    """Get available subscription plans with pricing"""
    plans = []
    for plan_id, plan_data in Config.SUBSCRIPTION_PLANS.items():
        plans.append({
            'id': plan_id,
            'name': plan_data['name'],
            'price_usd': plan_data['price'],
            'days': plan_data['days'],
        })
    
    return jsonify({
        'success': True,
        'plans': plans,
        'supported_currencies': ['USDT_TRC20', 'USDT_ERC20', 'BTC', 'ETH', 'LTC']
    })


@app.route('/api/payment/subscription', methods=['GET'])
@login_required
def get_subscription_status():
    """Get current user's subscription status"""
    return jsonify({
        'success': True,
        'is_active': current_user.has_active_subscription(),
        'plan': current_user.subscription_plan or 'free',
        'expires_at': current_user.subscription_expires_at.isoformat() if current_user.subscription_expires_at else None,
        'days_remaining': current_user.subscription_days_remaining(),
        'can_trade': current_user.has_active_subscription() and current_user.is_active
    })


@app.route('/api/payment/create', methods=['POST'])
@login_required
def create_payment():
    """Create a new payment invoice via Plisio"""
    from models import Payment
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Дані не надано'}), 400
    
    plan_id = data.get('plan', 'basic')
    currency = data.get('currency', 'USDT_TRC20')
    
    if plan_id not in Config.SUBSCRIPTION_PLANS:
        return jsonify({'success': False, 'error': f'Invalid plan: {plan_id}'}), 400
    
    plan = Config.SUBSCRIPTION_PLANS[plan_id]
    amount_usd = plan['price']
    days = plan['days']
    
    # Check if Plisio is configured
    if not hasattr(Config, 'PLISIO_API_KEY') or not Config.PLISIO_API_KEY:
        return jsonify({'success': False, 'error': 'Payment service not configured'}), 503
    
    # Generate order number
    order_number = f"SUB-{current_user.id}-{secrets.token_hex(8).upper()}"
    
    # Build callback URL
    callback_url = f"https://mimic.cash/api/payment/webhook"
    
    try:
        # Create Plisio invoice (sync request)
        import requests as req
        params = {
            'api_key': Config.PLISIO_API_KEY,
            'source_currency': 'USD',
            'source_amount': str(amount_usd),
            'currency': currency,
            'order_name': f"MIMIC {plan['name']} Subscription",
            'order_number': order_number,
            'callback_url': callback_url,
        }
        if current_user.email:
            params['email'] = current_user.email
        
        response = req.get(f"{PLISIO_API_URL}/invoices/new", params=params, timeout=30)
        result = response.json()
        
        if result.get('status') != 'success':
            error_msg = result.get('data', {}).get('message', 'Unknown error')
            logger.error(f"Plisio API error: {error_msg}")
            return jsonify({'success': False, 'error': f'Payment provider error: {error_msg}'}), 502
        
        invoice_data = result.get('data', {})
        
        # Parse expiration
        expire_utc = invoice_data.get('expire_utc')
        expires_at = None
        if expire_utc:
            try:
                expires_at = datetime.fromisoformat(expire_utc.replace('Z', '+00:00'))
            except:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            provider='plisio',
            provider_txn_id=invoice_data.get('txn_id'),
            amount_usd=amount_usd,
            amount_crypto=float(invoice_data.get('amount', 0)) if invoice_data.get('amount') else None,
            currency=currency,
            plan=plan_id,
            days=days,
            status='pending',
            wallet_address=invoice_data.get('wallet_hash') or invoice_data.get('wallet'),
            expires_at=expires_at
        )
        
        db.session.add(payment)
        db.session.commit()
        
        logger.info(f"✅ Payment invoice created: {order_number} for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'payment_id': payment.id,
            'provider_txn_id': invoice_data.get('txn_id', ''),
            'invoice_url': invoice_data.get('invoice_url', ''),
            'wallet_address': payment.wallet_address or '',
            'amount_usd': amount_usd,
            'amount_crypto': payment.amount_crypto,
            'currency': currency,
            'plan': plan_id,
            'days': days,
            'expires_at': expires_at.isoformat() if expires_at else None,
            'message': 'Invoice created. Please complete payment within 24 hours.'
        })
        
    except Exception as e:
        logger.error(f"❌ Payment creation failed: {e}")
        return jsonify({'success': False, 'error': 'Не вдалося створити інвойс платежу'}), 500


@app.route('/api/payment/webhook', methods=['GET', 'POST'])
def payment_webhook():
    """
    Handle Plisio webhook callbacks
    
    Called when payment status changes: pending -> completed/expired/error
    GET requests return a status message (for testing)
    """
    # Handle GET request (browser test)
    if request.method == 'GET':
        return jsonify({
            'status': 'ok',
            'message': 'Payment webhook endpoint is active. Use POST to submit payment callbacks.',
            'provider': 'plisio'
        })
    from models import Payment
    
    try:
        # Parse webhook data
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        txn_id = data.get('txn_id')
        status_value = (data.get('status') or '').lower()
        verify_hash = data.get('verify_hash')
        
        logger.info(f"📬 Payment webhook received: txn_id={txn_id}, status={status_value}")
        
        # Verify webhook signature if secret is configured
        if hasattr(Config, 'PLISIO_WEBHOOK_SECRET') and Config.PLISIO_WEBHOOK_SECRET and verify_hash:
            sorted_params = '&'.join(f"{k}={v}" for k, v in sorted(data.items()) if k != 'verify_hash')
            to_hash = sorted_params + Config.PLISIO_WEBHOOK_SECRET
            expected_hash = hashlib.md5(to_hash.encode()).hexdigest()
            
            if expected_hash != verify_hash:
                logger.warning(f"⚠️ Invalid webhook signature for txn_id={txn_id}")
                return jsonify({'status': 'error', 'message': 'Invalid signature'}), 403
        
        # Find payment record
        payment = Payment.query.filter_by(provider_txn_id=txn_id).first()
        
        if not payment:
            logger.warning(f"⚠️ Payment not found for txn_id={txn_id}")
            return jsonify({'status': 'ok', 'message': 'Payment not found'})
        
        old_status = payment.status
        
        if status_value == 'completed':
            payment.status = 'completed'
            payment.completed_at = datetime.now(timezone.utc)
            
            # Activate subscription
            user = User.query.get(payment.user_id)
            if user:
                user.extend_subscription(days=payment.days, plan=payment.plan)
                db.session.commit()
                
                logger.info(f"✅ Subscription activated for user {user.id}: {payment.plan} ({payment.days} days)")
                
                # Send Telegram notification
                if telegram and user.telegram_chat_id and user.telegram_enabled:
                    telegram.notify_subscription_activated(
                        user_chat_id=user.telegram_chat_id,
                        username=user.username,
                        plan=payment.plan,
                        days=payment.days,
                        expires_at=user.subscription_expires_at.strftime('%d.%m.%Y %H:%M') if user.subscription_expires_at else 'N/A'
                    )
        
        elif status_value in ['expired', 'error', 'cancelled']:
            payment.status = status_value
        
        elif status_value in ['pending', 'new']:
            payment.status = 'pending'
        
        db.session.commit()
        
        logger.info(f"📝 Payment {txn_id} status updated: {old_status} -> {payment.status}")
        
        return jsonify({'status': 'ok', 'message': f'Payment status updated to {payment.status}'})
        
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/api/payment/status/<int:payment_id>', methods=['GET'])
@login_required
def get_payment_status(payment_id):
    """Check payment status"""
    from models import Payment
    
    payment = Payment.query.filter_by(id=payment_id, user_id=current_user.id).first()
    
    if not payment:
        return jsonify({'success': False, 'error': 'Платіж не знайдено'}), 404
    
    return jsonify({
        'success': True,
        'payment_id': payment.id,
        'status': payment.status,
        'plan': payment.plan,
        'amount_usd': payment.amount_usd,
        'created_at': payment.created_at.isoformat() if payment.created_at else None,
        'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
        'subscription_expires_at': current_user.subscription_expires_at.isoformat() if payment.status == 'completed' and current_user.subscription_expires_at else None
    })


@app.route('/api/payment/history', methods=['GET'])
@login_required
def get_payment_history():
    """Get user's payment history"""
    from models import Payment
    
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).limit(20).all()
    
    return jsonify({
        'success': True,
        'payments': [p.to_dict() for p in payments]
    })


# ==================== WEB PUSH NOTIFICATIONS ====================

@app.route('/api/push/vapid-key', methods=['GET'])
def get_vapid_public_key():
    """Get VAPID public key for push subscription"""
    vapid_key = getattr(Config, 'VAPID_PUBLIC_KEY', '')
    
    if not vapid_key:
        return jsonify({
            'success': False,
            'error': 'Push notifications not configured'
        }), 503
    
    return jsonify({
        'success': True,
        'publicKey': vapid_key
    })


@app.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    """Subscribe to push notifications"""
    from models import PushSubscription
    
    # Check if push is enabled
    if not getattr(Config, 'WEBPUSH_ENABLED', False):
        return jsonify({
            'success': False,
            'error': 'Push notifications not configured'
        }), 503
    
    data = request.get_json()
    if not data or 'subscription' not in data:
        return jsonify({
            'success': False,
            'error': 'Невірні дані підписки'
        }), 400
    
    subscription = data['subscription']
    endpoint = subscription.get('endpoint')
    keys = subscription.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')
    
    if not all([endpoint, p256dh, auth]):
        return jsonify({
            'success': False,
            'error': 'Missing subscription keys'
        }), 400
    
    try:
        # Check if subscription already exists
        existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
        
        if existing:
            # Update existing subscription
            existing.user_id = current_user.id
            existing.p256dh_key = p256dh
            existing.auth_key = auth
            existing.user_agent = data.get('userAgent')
            existing.language = data.get('language', 'en')
            existing.is_active = True
            existing.error_count = 0
        else:
            # Create new subscription
            new_sub = PushSubscription(
                user_id=current_user.id,
                endpoint=endpoint,
                p256dh_key=p256dh,
                auth_key=auth,
                user_agent=data.get('userAgent'),
                language=data.get('language', 'en'),
                is_active=True
            )
            db.session.add(new_sub)
        
        db.session.commit()
        
        logger.info(f"📱 Push subscription saved for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Subscription saved'
        })
        
    except Exception as e:
        logger.error(f"Push subscription error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Не вдалося зберегти підписку'
        }), 500


@app.route('/api/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    """Unsubscribe from push notifications"""
    from models import PushSubscription
    
    data = request.get_json()
    endpoint = data.get('endpoint')
    
    if not endpoint:
        return jsonify({
            'success': False,
            'error': 'Missing endpoint'
        }), 400
    
    try:
        subscription = PushSubscription.query.filter_by(
            endpoint=endpoint,
            user_id=current_user.id
        ).first()
        
        if subscription:
            db.session.delete(subscription)
            db.session.commit()
            logger.info(f"📱 Push subscription removed for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Unsubscribed successfully'
        })
        
    except Exception as e:
        logger.error(f"Push unsubscribe error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Не вдалося скасувати підписку'
        }), 500


@app.route('/api/push/test', methods=['POST'])
@login_required
def push_test():
    """Send a test push notification to current user"""
    from models import PushSubscription
    
    # Check if push is enabled
    if not getattr(Config, 'WEBPUSH_ENABLED', False):
        return jsonify({
            'success': False,
            'error': 'Push notifications not configured'
        }), 503
    
    try:
        # Import pywebpush
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'pywebpush not installed. Run: pip install pywebpush'
            }), 503
        
        # Get user's active subscriptions
        subscriptions = PushSubscription.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        if not subscriptions:
            return jsonify({
                'success': False,
                'error': 'No active push subscriptions found'
            }), 404
        
        # Prepare notification payload
        payload = json.dumps({
            'title': '🚀 MIMIC Test Notification',
            'body': 'Push notifications are working correctly!',
            'icon': '/static/icons/icon-192x192.png',
            'badge': '/static/icons/badge-72x72.png',
            'tag': 'test-notification',
            'data': {'url': '/dashboard', 'type': 'test'},
            'timestamp': int(time.time() * 1000)
        })
        
        vapid_claims = {
            'sub': Config.VAPID_CLAIM_EMAIL
        }
        
        sent_count = 0
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info=sub.get_subscription_info(),
                    data=payload,
                    vapid_private_key=Config.VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims
                )
                sub.mark_used()
                sent_count += 1
            except WebPushException as e:
                logger.error(f"Push send failed: {e}")
                sub.mark_error()
                # Handle unsubscribed endpoints
                if e.response and e.response.status_code in [404, 410]:
                    sub.is_active = False
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Test notification sent to {sent_count} device(s)'
        })
        
    except Exception as e:
        logger.error(f"Push test error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def send_push_notification(user_id: int, title: str, body: str, data: dict = None, tag: str = None):
    """
    Send push notification to a user.
    
    Args:
        user_id: User ID to send to
        title: Notification title
        body: Notification body text
        data: Optional extra data (url, type, etc.)
        tag: Optional tag for notification grouping
    
    Returns:
        Number of successful sends
    """
    from models import PushSubscription
    
    # Check if push is enabled
    if not getattr(Config, 'WEBPUSH_ENABLED', False):
        return 0
    
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush not installed, skipping push notification")
        return 0
    
    # Get user's active subscriptions
    subscriptions = PushSubscription.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()
    
    if not subscriptions:
        return 0
    
    # Prepare payload
    payload = json.dumps({
        'title': title,
        'body': body,
        'icon': '/static/icons/icon-192x192.png',
        'badge': '/static/icons/badge-72x72.png',
        'tag': tag or 'mimic-notification',
        'data': data or {'url': '/dashboard'},
        'timestamp': int(time.time() * 1000)
    })
    
    vapid_claims = {
        'sub': Config.VAPID_CLAIM_EMAIL
    }
    
    sent_count = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub.get_subscription_info(),
                data=payload,
                vapid_private_key=Config.VAPID_PRIVATE_KEY,
                vapid_claims=vapid_claims
            )
            sub.mark_used()
            sent_count += 1
        except WebPushException as e:
            logger.error(f"Push send failed for user {user_id}: {e}")
            sub.mark_error()
            if e.response and e.response.status_code in [404, 410]:
                sub.is_active = False
    
    try:
        db.session.commit()
    except:
        db.session.rollback()
    
    return sent_count


def send_trade_push_notification(user_id: int, trade_type: str, symbol: str, side: str, 
                                  pnl: float = None, pnl_percent: float = None):
    """
    Send trade-specific push notification.
    
    Args:
        user_id: User ID
        trade_type: 'opened' or 'closed'
        symbol: Trading pair (e.g., 'BTCUSDT')
        side: 'BUY' or 'SELL' / 'LONG' or 'SHORT'
        pnl: Profit/loss amount (for closed trades)
        pnl_percent: Profit/loss percentage (for closed trades)
    """
    if trade_type == 'opened':
        emoji = '📈' if side.upper() in ['BUY', 'LONG'] else '📉'
        title = f'{emoji} New Position Opened'
        body = f'{symbol} {side.upper()} position opened'
        tag = 'trade-opened'
    else:
        if pnl is not None and pnl >= 0:
            emoji = '💰'
            pnl_text = f'+${pnl:.2f}' if pnl else ''
        else:
            emoji = '📊'
            pnl_text = f'-${abs(pnl):.2f}' if pnl else ''
        
        title = f'{emoji} Position Closed'
        body = f'{symbol} closed {pnl_text}'
        if pnl_percent:
            body += f' ({pnl_percent:+.2f}%)'
        tag = 'trade-closed'
    
    return send_push_notification(
        user_id=user_id,
        title=title,
        body=body,
        data={'url': '/dashboard', 'type': f'trade_{trade_type}', 'symbol': symbol},
        tag=tag
    )


# ==================== API KEY MANAGEMENT ====================
# Routes for managing API keys for the public developer API (api.mimic.cash)

@app.route('/api-keys')
@login_required
def api_keys_page():
    """Display API keys management page"""
    from models import ApiKey
    
    # Get user's API keys
    api_keys = ApiKey.get_user_keys(current_user.id, include_revoked=False)
    
    return render_template('api_keys.html', 
                           api_keys=api_keys,
                           max_keys=5)  # Limit of 5 API keys per user


@app.route('/api/v1/keys', methods=['GET'])
@login_required
def api_keys_list():
    """List user's API keys"""
    from models import ApiKey
    
    api_keys = ApiKey.get_user_keys(current_user.id)
    return jsonify({
        'success': True,
        'api_keys': [key.to_dict(include_stats=True) for key in api_keys]
    })


@app.route('/api/v1/keys', methods=['POST'])
@login_required
def api_keys_create():
    """Create a new API key"""
    from models import ApiKey
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Дані не надано'}), 400
    
    # Validate label
    label = data.get('label', 'Default API Key')
    if len(label) > 100:
        return jsonify({'success': False, 'error': 'Label too long (max 100 chars)'}), 400
    
    # Check user's existing keys count (limit to 5)
    existing_keys = ApiKey.query.filter_by(user_id=current_user.id, is_active=True).count()
    if existing_keys >= 5:
        return jsonify({
            'success': False, 
            'error': 'Maximum API keys limit reached (5). Please revoke an existing key first.'
        }), 400
    
    # Check subscription
    if not current_user.has_active_subscription():
        return jsonify({
            'success': False,
            'error': 'Active subscription required to create API keys'
        }), 403
    
    # Parse permissions
    permissions = 0
    if data.get('permission_read', True):
        permissions |= ApiKey.PERMISSION_READ
    if data.get('permission_signal', True):
        permissions |= ApiKey.PERMISSION_SIGNAL
    if data.get('permission_trade', False):
        permissions |= ApiKey.PERMISSION_TRADE
    
    # Parse rate limit
    rate_limit = min(int(data.get('rate_limit', 60)), 120)  # Max 120/min
    rate_limit = max(rate_limit, 10)  # Min 10/min
    
    # Parse IP whitelist
    ip_whitelist = None
    ip_whitelist_str = data.get('ip_whitelist', '').strip()
    if ip_whitelist_str:
        ip_whitelist = [ip.strip() for ip in ip_whitelist_str.split(',') if ip.strip()]
    
    # Parse expiration
    expires_days = None
    expires_str = data.get('expires', 'never')
    if expires_str == '30':
        expires_days = 30
    elif expires_str == '90':
        expires_days = 90
    elif expires_str == '365':
        expires_days = 365
    
    try:
        # Create the API key
        api_key, secret = ApiKey.create_for_user(
            user_id=current_user.id,
            label=label,
            permissions=permissions,
            rate_limit=rate_limit,
            ip_whitelist=ip_whitelist,
            expires_days=expires_days
        )
        
        logger.info(f"API key created for user {current_user.id}: {api_key.key[:12]}...")
        
        return jsonify({
            'success': True,
            'message': 'API key created successfully',
            'api_key': api_key.to_dict(),
            'secret': secret,  # This is shown only once!
            'warning': '⚠️ Save your secret now! It will not be shown again.'
        })
        
    except Exception as e:
        logger.error(f"API key creation failed: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Не вдалося створити API ключ: {str(e)}'
        }), 500


@app.route('/api/v1/keys/<int:key_id>', methods=['DELETE'])
@login_required
def api_keys_revoke(key_id):
    """Revoke an API key"""
    from models import ApiKey
    
    api_key = ApiKey.query.filter_by(id=key_id, user_id=current_user.id).first()
    
    if not api_key:
        return jsonify({'success': False, 'error': 'API key not found'}), 404
    
    try:
        api_key.revoke()
        logger.info(f"API key revoked for user {current_user.id}: {api_key.key[:12]}...")
        
        return jsonify({
            'success': True,
            'message': 'API key revoked successfully'
        })
        
    except Exception as e:
        logger.error(f"API key revocation failed: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Не вдалося відкликати API ключ: {str(e)}'
        }), 500


@app.route('/api/v1/keys/<int:key_id>', methods=['PATCH'])
@login_required
def api_keys_update(key_id):
    """Update an API key (label, permissions, rate limit, IP whitelist)"""
    from models import ApiKey
    
    api_key = ApiKey.query.filter_by(id=key_id, user_id=current_user.id, is_active=True).first()
    
    if not api_key:
        return jsonify({'success': False, 'error': 'API key not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Дані не надано'}), 400
    
    try:
        # Update label
        if 'label' in data:
            api_key.label = data['label'][:100]
        
        # Update permissions
        if any(k.startswith('permission_') for k in data.keys()):
            permissions = 0
            if data.get('permission_read', api_key.can_read()):
                permissions |= ApiKey.PERMISSION_READ
            if data.get('permission_signal', api_key.can_signal()):
                permissions |= ApiKey.PERMISSION_SIGNAL
            if data.get('permission_trade', api_key.can_trade()):
                permissions |= ApiKey.PERMISSION_TRADE
            api_key.permissions = permissions
        
        # Update rate limit
        if 'rate_limit' in data:
            rate_limit = min(int(data['rate_limit']), 120)
            rate_limit = max(rate_limit, 10)
            api_key.rate_limit = rate_limit
        
        # Update IP whitelist
        if 'ip_whitelist' in data:
            ip_whitelist_str = data['ip_whitelist'].strip()
            if ip_whitelist_str:
                api_key.ip_whitelist = [ip.strip() for ip in ip_whitelist_str.split(',') if ip.strip()]
            else:
                api_key.ip_whitelist = None
        
        db.session.commit()
        
        logger.info(f"API key updated for user {current_user.id}: {api_key.key[:12]}...")
        
        return jsonify({
            'success': True,
            'message': 'API key updated successfully',
            'api_key': api_key.to_dict(include_stats=True)
        })
        
    except Exception as e:
        logger.error(f"API key update failed: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Не вдалося оновити API ключ: {str(e)}'
        }), 500


# ==================== LEGACY WORKER ====================
# NOTE: This worker_loop is for backwards compatibility when ARQ is not available.
# In production with Docker, use the separate 'worker' service with ARQ instead.
# The ARQ worker (worker.py) processes tasks from the Redis queue asynchronously.

def worker_loop():
    """
    Legacy background worker for processing trade signals.
    
    This runs in-process and is used when:
    - ARQ is not available
    - Running in development without Docker
    - Fallback mode when ARQ queue fails
    
    For production, use: arq worker.WorkerSettings
    """
    engine.init_master()
    
    with app.app_context():
        db.create_all()
        engine.load_slaves()
    
    mode = 'REDIS' if redis_client else 'IN-MEMORY'
    logger.info(f"👷 Worker started. Queue mode: {mode}")
    
    if telegram:
        telegram.notify_system_event("Система запущена", f"Mode: {mode}")
    
    while True:
        try:
            task = None
            
            if redis_client:
                result = redis_client.blpop('trade_signals', timeout=5)
                if result:
                    _, data = result
                    task = json.loads(data)
            else:
                task = signal_queue.get()
            
            if task:
                engine.process_signal(task)
                
        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(1)


# ==================== MAIN ====================

if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or os.environ.get('FLASK_RUN_MAIN') == 'true' or not app.debug:
    start_cache_warmers()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create admin if not exists
        if not User.query.filter_by(role='admin').first():
            admin = User(username='admin', role='admin', is_active=True)
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            logger.info("✅ Admin user created (admin/admin)")
        
        # Initialize exchange configurations
        init_exchange_configs()
        logger.info("✅ Exchange configurations initialized")
    
    # Start worker thread
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    
    print("""
    +===================================================================+
    |                                                                   |
    |                  M I M I C   C O P Y   T R A D I N G              |
    |                                                                   |
    |                  ================================                  |
    |                    B R A I N   C A P I T A L                      |
    |                          v 9 . 0                                  |
    |                  ================================                  |
    |                   Copy Trading Platform                           |
    |                                                                   |
    +===================================================================+
    |                                                                   |
    |   [*] Server:     http://0.0.0.0:80                                |
    |   [*] Admin:      http://localhost/login (admin/admin)            |
    |   [*] Webhook:    POST http://your-domain/webhook                 |
    |                                                                   |
    |   [OK] Status:    Ready to accept connections                     |
    |                                                                   |
    +===================================================================+
    """)
    
    socketio.run(app, host='0.0.0.0', port=80, debug=False, allow_unsafe_werkzeug=True)
