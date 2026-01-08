"""
Brain Capital - Copy Trading Platform
Main Flask Application with Enhanced Security
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort, g, send_from_directory
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room
from config import Config
from models import db, User, TradeHistory, BalanceHistory, Message, PasswordResetToken, UserExchange, ExchangeConfig, Payment
from sqlalchemy import text
from trading_engine import TradingEngine
from telegram_notifier import init_notifier, get_notifier, init_email_sender, get_email_sender
from telegram_bot import init_telegram_bot, get_telegram_bot
from metrics import get_metrics, init_flask_metrics, set_app_info
from security import (
    login_tracker, login_limiter, api_limiter, webhook_limiter,
    InputValidator, add_security_headers, get_client_ip,
    init_session_security, verify_session, generate_csrf_token,
    audit, rate_limit, validate_webhook
)
import asyncio
import threading
from queue import Queue
from datetime import datetime, timedelta, timezone
import random
import logging
import re
import time
import os
import json
import secrets

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BrainCapital")

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
        "http://mimic.cash",
        "https://mimic.cash",
        "http://www.mimic.cash",
        "https://www.mimic.cash",
    ]

# Add custom origins from environment if set (for additional origins)
if os.environ.get('ALLOWED_ORIGINS'):
    SOCKETIO_ALLOWED_ORIGINS.extend(os.environ.get('ALLOWED_ORIGINS', '').split(','))

socketio = SocketIO(
    app, 
    async_mode='threading', 
    ping_timeout=60, 
    cors_allowed_origins=SOCKETIO_ALLOWED_ORIGINS,
    cookie='io',  # Fixed: must be string cookie name, not boolean
    manage_session=False
)

# Initialize Redis (optional) and ARQ for task queue
redis_client = None
arq_pool = None
signal_queue = Queue()

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
    else:
        logger.warning("⚠️ Telegram notifications NOT active (check bot token/chat_id)")

# Initialize Email sender
email_sender = None
EMAIL_CONFIGURED = False
if hasattr(Config, 'EMAIL_ENABLED') and Config.EMAIL_ENABLED:
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
        logger.warning("⚠️ Email sender NOT active (check SMTP settings)")
else:
    logger.info("ℹ️ Email not configured in config.ini - password reset via email disabled")
    email_sender = get_email_sender()  # May be None

# Initialize Trading Engine
engine = TradingEngine(app, socketio, telegram)

# Initialize Telegram Bot Handler (for panic commands with OTP)
telegram_bot = None
if hasattr(Config, 'TG_TOKEN') and Config.TG_TOKEN and hasattr(Config, 'PANIC_OTP_SECRET'):
    try:
        telegram_bot = init_telegram_bot(
            bot_token=Config.TG_TOKEN,
            otp_secret=Config.PANIC_OTP_SECRET,
            authorized_users=getattr(Config, 'PANIC_AUTHORIZED_USERS', []),
            panic_callback=engine.close_all_positions_all_accounts,
            admin_chat_id=Config.TG_CHAT_ID
        )
        if telegram_bot:
            logger.info("✅ Telegram Bot Handler started (panic commands enabled)")
        else:
            logger.info("ℹ️ Telegram Bot Handler not started (OTP not configured)")
    except Exception as e:
        logger.warning(f"⚠️ Telegram Bot Handler failed to start: {e}")

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
    socketio.emit('new_log', entry, room="admin_room")
    if user_id and user_id != 'master':
        socketio.emit('new_log', entry, room=f"user_{user_id}")

engine.log_error_callback = log_system_event


def get_user_exchange_balances(user_id: int) -> dict:
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
    
    # Check for injection attempts in request data
    if request.method == 'POST':
        for key, value in request.form.items():
            if isinstance(value, str) and InputValidator.check_injection(value):
                audit.log_security_event("INJECTION_ATTEMPT", f"IP: {ip}, Field: {key}", "CRITICAL")
                login_tracker.block_ip(ip)
                abort(403)


@app.after_request
def apply_security_headers(response):
    """Add security headers to all responses"""
    return add_security_headers(response)


@app.context_processor
def inject_csrf_token():
    """Inject CSRF token into templates"""
    return {'csrf_token': generate_csrf_token}


# ==================== SOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
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
                socketio.emit('update_data', {'balance': "0.00", 'positions': []}, room=room)


# ==================== SEO ROUTES ====================

@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for search engines"""
    return send_from_directory(app.static_folder, 'robots.txt', mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap_xml():
    """Serve sitemap.xml for search engines"""
    return send_from_directory(app.static_folder, 'sitemap.xml', mimetype='application/xml')

@app.route('/manifest.json')
def manifest_json():
    """Serve PWA manifest"""
    return send_from_directory(app.static_folder, 'manifest.json', mimetype='application/json')


# ==================== ROUTES ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


# ==================== PUBLIC LEADERBOARD ====================

@app.route('/leaderboard')
def leaderboard():
    """Public leaderboard page - SEO optimized landing page showing trading stats"""
    return render_template('leaderboard.html')


@app.route('/api/leaderboard/stats')
def get_leaderboard_stats():
    """Public API endpoint for leaderboard statistics - no auth required"""
    try:
        # Calculate time periods
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        last_7_days = datetime.now(timezone.utc) - timedelta(days=7)
        last_30_days = datetime.now(timezone.utc) - timedelta(days=30)
        
        # ===== GLOBAL STATS =====
        
        # Total Users (active users only)
        total_users = User.query.filter(User.role == 'user').count()
        active_users = User.query.filter(User.role == 'user', User.is_active == True).count()
        
        # Total Profit (sum of all positive PnL trades)
        total_profit = db.session.query(db.func.sum(TradeHistory.pnl)).filter(
            TradeHistory.pnl > 0
        ).scalar() or 0
        
        # Total Volume (approximate from trades - sum of absolute PnL as proxy for volume)
        total_volume = db.session.query(db.func.sum(db.func.abs(TradeHistory.pnl))).scalar() or 0
        # Multiply by approximate leverage factor for more realistic volume
        total_volume = total_volume * 15  # Assume average 15x leverage
        
        # Total trades
        total_trades = TradeHistory.query.count()
        
        # ===== TOP COPIERS TODAY (by ROE%) =====
        # Get users with trades today, ranked by average ROE
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
                # Mask username: first 1 char + *** + last 1 char
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
        
        # If no trades today, get top performers from last 7 days
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
        # Master trades have user_id = None
        master_trades_30d = TradeHistory.query.filter(
            TradeHistory.user_id == None,
            TradeHistory.close_time >= last_30_days
        ).all()
        
        master_pnl = sum(t.pnl for t in master_trades_30d) if master_trades_30d else 0
        master_trades_count = len(master_trades_30d)
        master_winning = len([t for t in master_trades_30d if t.pnl > 0])
        master_winrate = (master_winning / master_trades_count * 100) if master_trades_count > 0 else 0
        master_avg_roi = sum(t.roi for t in master_trades_30d) / len(master_trades_30d) if master_trades_30d else 0
        
        # Get master balance history for chart (last 30 days)
        master_balance_history = BalanceHistory.query.filter(
            BalanceHistory.user_id == None,
            BalanceHistory.timestamp >= last_30_days
        ).order_by(BalanceHistory.timestamp.asc()).all()
        
        balance_chart_data = [{
            'time': h.timestamp.strftime('%d/%m'),
            'balance': round(h.balance, 2)
        } for h in master_balance_history]
        
        # Calculate master ROE based on starting vs current balance
        master_roe = 0
        if master_balance_history and len(master_balance_history) >= 2:
            start_balance = master_balance_history[0].balance
            end_balance = master_balance_history[-1].balance
            if start_balance > 0:
                master_roe = ((end_balance - start_balance) / start_balance) * 100
        
        return jsonify({
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
        })
        
    except Exception as e:
        logger.error(f"Error getting leaderboard stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load leaderboard data'
        }), 500


@app.route('/favicon.ico')
def favicon():
    return '', 204  # No content - prevents 404 errors


@app.route('/health')
def health_check():
    """Health check endpoint for Docker/Kubernetes probes"""
    try:
        # Verify database connection
        db.session.execute(text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    return jsonify({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'database': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200 if db_status == 'healthy' else 503


@app.route('/metrics')
def prometheus_metrics():
    """Prometheus metrics endpoint for observability stack."""
    from flask import Response
    metrics_output, content_type = get_metrics()
    return Response(metrics_output, mimetype=content_type)


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
            
            engine.load_slaves()
            
            audit.log_security_event("NEW_REGISTRATION", f"User: {phone}, Exchange: {exchange_name}, IP: {ip}", "INFO")
            logger.info(f"✅ New user registered: {phone} with {exchange_config.display_name}")
            
            if telegram:
                telegram.notify_system_event(
                    "🆕 Новий користувач", 
                    f"{first_name} {last_name}\n📱 {phone}\n🏦 {exchange_config.display_name}"
                )
            
            flash(f'Реєстрація успішна! Ваша заявка на підключення до {exchange_config.display_name} надіслана адміністратору.', 'success')
            return redirect(url_for('login'))
            
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
        m_bal = "Connecting..."
        if engine.master_client:
            try:
                balances = engine.master_client.futures_account_balance()
                for b in balances:
                    if b['asset'] == 'USDT':
                        m_bal = f"{float(b['balance']):,.2f}"
                        break
            except Exception:
                m_bal = "Error"
        
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
        try:
            master_positions = engine.get_all_master_positions()
            master_exchange_balances = engine.get_all_master_balances()
            # Update m_bal with total from all exchanges
            total_balance = sum(b['balance'] for b in master_exchange_balances if b['balance'] is not None)
            if total_balance > 0:
                m_bal = f"{total_balance:,.2f}"
        except Exception as e:
            logger.warning(f"Failed to fetch master data: {e}")
        
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
                u_bal = "Error"
        
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
        
        if chat_id and enabled and telegram:
            # Test connection by sending welcome message
            user_display = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.username
            success, error = telegram.test_connection(chat_id, user_display)
            
            if not success:
                if error == "chat_not_found":
                    # Get bot username for the link
                    bot_username = telegram.get_bot_username()
                    if bot_username:
                        flash(f'❌ Чат не знайдено! Спочатку напишіть боту @{bot_username} команду /start, потім спробуйте знову.', 'error')
                    else:
                        flash('❌ Чат не знайдено! Спочатку напишіть боту будь-яке повідомлення, потім спробуйте знову.', 'error')
                elif error == "bot_blocked":
                    flash('❌ Ви заблокували бота! Розблокуйте його і спробуйте знову.', 'error')
                else:
                    flash(f'❌ Помилка підключення: {error}', 'error')
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
            flash('Telegram ID збережено, сповіщення вимкнено', 'info')
        else:
            # Clear telegram settings
            current_user.telegram_chat_id = None
            current_user.telegram_enabled = False
            db.session.commit()
            flash('Telegram налаштування очищено', 'info')
    except Exception as e:
        logger.error(f"Error updating telegram settings: {e}")
        flash(f'Помилка: {e}', 'error')
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
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    try:
        avatar_type = request.form.get('avatar_type', 'emoji')
        
        if avatar_type == 'emoji':
            emoji = request.form.get('emoji', '🧑‍💻')
            if emoji in AVATAR_EMOJIS:
                user.avatar = emoji
                user.avatar_type = 'emoji'
                db.session.commit()
                return jsonify({'success': True, 'message': 'Avatar updated'})
            else:
                return jsonify({'success': False, 'error': 'Invalid emoji'}), 400
        
        elif avatar_type == 'image':
            if 'avatar_file' not in request.files:
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            
            file = request.files['avatar_file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            
            if file_ext not in allowed_extensions:
                return jsonify({'success': False, 'error': 'Only PNG, JPG, GIF, WEBP allowed'}), 400
            
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            
            if size > 2 * 1024 * 1024:
                return jsonify({'success': False, 'error': 'Max file size: 2MB'}), 400
            
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
            
            return jsonify({'success': True, 'message': 'Avatar uploaded', 'avatar': filename})
        
        return jsonify({'success': False, 'error': 'Invalid avatar type'}), 400
        
    except Exception as e:
        logger.error(f"Error updating user avatar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/user/<int:user_id>/details')
@login_required
def get_user_details(user_id):
    """Get detailed user information for admin panel"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
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
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot delete yourself'}), 400
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    # Prevent deleting other admins
    if user.role == 'admin':
        return jsonify({'success': False, 'error': 'Cannot delete admin users'}), 400
    
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
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
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
        return jsonify({'error': 'Access denied'}), 403
    
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
        return jsonify({'error': 'Access denied'}), 403
    
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
        return jsonify({'error': 'Access denied'}), 403
    
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
                
                html_parts.append(f'''
                <div class="position-card">
                    <div class="position-info">
                        <div class="side-badge {side_class}">
                            <i class="fas fa-{arrow}"></i>
                        </div>
                        <div>
                            <div class="symbol">{p['symbol']}</div>
                            <div class="details">{p['side']} · x{p['leverage']}{' · ' + p.get('exchange', '') if p.get('exchange') else ''}</div>
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


# ==================== WEBHOOK ====================

# ARQ task queueing helper
async def enqueue_signal_task(signal: dict) -> str:
    """
    Queue a trading signal to the ARQ worker.
    Returns job_id on success.
    """
    try:
        from arq import create_pool
        pool = await create_pool(ARQ_REDIS_SETTINGS)
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
            # Try to parse as plain text if JSON parsing failed
            if raw_data:
                logger.warning(f"Webhook: Data received but not valid JSON: {raw_data[:200]}")
                return jsonify({'error': 'Invalid JSON format'}), 400
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
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Parse and validate signal
        raw_symbol = re.sub(r'\.P|\.p|\.S|\.s$', '', str(data.get('symbol', ''))).upper()
        valid, symbol = InputValidator.validate_symbol(raw_symbol)
        if not valid:
            return jsonify({'error': f'Invalid symbol: {symbol}'}), 400
        
        action = data.get('action', 'close').lower()
        if action not in ['long', 'short', 'close']:
            return jsonify({'error': 'Invalid action'}), 400
        
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
        
        signal = {
            'symbol': symbol,
            'action': action,
            'risk': task_risk,
            'lev': task_leverage,
            'tp_perc': tp_perc,
            'sl_perc': sl_perc
        }
        
        logger.info(f"📥 Webhook received: {action.upper()} {symbol}")
        logger.info(f"📊 Signal created: Risk={signal['risk']}%, Leverage={signal['lev']}x, TP={signal['tp_perc']}%, SL={signal['sl_perc']}%")
        logger.info(f"📊 (Webhook values: risk={webhook_risk}%, lev={webhook_leverage}x, using global: {webhook_leverage <= 1})")
        log_system_event(None, symbol, f"SIGNAL: {action.upper()} (Risk: {signal['risk']}%, Lev: {signal['lev']}x)")
        
        # Queue the task via ARQ (preferred) or legacy Redis/memory queue
        queue_mode = 'memory'
        job_id = None
        
        if ARQ_REDIS_SETTINGS:
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
    if current_user.role != 'admin':
        socketio.emit('new_message', message.to_dict(), room='admin_room')
    elif recipient_id:
        socketio.emit('new_message', message.to_dict(), room=f'user_{recipient_id}')
    
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
    if is_from_admin and recipient_id:
        socketio.emit('new_message', reply.to_dict(), room=f'user_{recipient_id}')
    else:
        socketio.emit('new_message', reply.to_dict(), room='admin_room')
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
    users = User.query.filter(User.role != 'admin').all()
    users_data = [{
        'id': u.id,
        'name': f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username,
        'username': u.username
    } for u in users]
    
    return jsonify(users_data)


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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
    count = UserExchange.query.filter_by(status='PENDING').count()
    return jsonify({'count': count})


# ==================== ADMIN USER EXCHANGE TRADING MANAGEMENT ====================

@app.route('/api/admin/exchanges/<int:exchange_id>/start-trading', methods=['POST'])
@login_required
def admin_start_user_trading(exchange_id):
    """Admin enables trading for a user's exchange"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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


@app.route('/api/admin/user/<int:user_id>/balances', methods=['GET'])
@login_required
def admin_get_user_balances(user_id):
    """Get balances for all connected exchanges of a user (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'error': 'Unauthorized'}), 403
    
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
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
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
        return jsonify({'success': False, 'error': 'Failed to create payment invoice'}), 500


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
        return jsonify({'success': False, 'error': 'Payment not found'}), 404
    
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
