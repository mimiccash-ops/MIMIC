"""
Brain Capital - ARQ Worker
Background task processor for trading signals

This worker runs separately from the Flask web server and processes
trading signals from the Redis queue using ARQ.

Observability Features:
- Prometheus metrics on port 9091
- JSON structured logging for Loki integration
- Async metrics for trade execution

Usage:
    # Development
    arq worker.WorkerSettings

    # Production (with multiple workers)
    arq worker.WorkerSettings --watch

    # Or run directly
    python worker.py
"""

import asyncio
import logging
import os
import sys
from datetime import timedelta, datetime, timezone

from arq import create_pool, cron
from arq.connections import RedisSettings

# Import metrics for Prometheus
from metrics import (
    start_metrics_server, record_worker_task, set_worker_queue_size,
    WORKER_TASKS_PROCESSED, set_app_info
)

# ============================================================================
# JSON STRUCTURED LOGGING FOR LOKI
# ============================================================================
from pythonjsonlogger import jsonlogger

class LokiJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter optimized for Loki ingestion."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields for Loki
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['service'] = 'brain_capital_worker'
        log_record['environment'] = os.environ.get('FLASK_ENV', 'production')
        
        # Add source location
        log_record['source'] = {
            'file': record.filename,
            'line': record.lineno,
            'function': record.funcName
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)


def setup_json_logging():
    """Configure JSON logging for Loki integration."""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # JSON file handler for Loki/Promtail
    json_handler = logging.FileHandler(
        os.path.join(logs_dir, 'worker.json'),
        encoding='utf-8'
    )
    json_handler.setLevel(logging.INFO)
    json_handler.setFormatter(LokiJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    ))
    
    # Console handler for human-readable output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(json_handler)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger("ARQ.Worker")


# Setup logging with JSON support for Loki
logger = setup_json_logging()

# Get Redis URL from environment or default
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')


def parse_redis_url(url: str) -> RedisSettings:
    """Parse Redis URL into RedisSettings with Windows-compatible settings"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    
    # Use 127.0.0.1 instead of localhost for better Windows compatibility
    host = parsed.hostname or 'localhost'
    if host == 'localhost':
        host = '127.0.0.1'
    
    return RedisSettings(
        host=host,
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip('/') or 0) if parsed.path else 0,
        password=parsed.password,
        ssl=parsed.scheme == 'rediss',
        conn_timeout=30,  # Longer timeout for Windows
        conn_retries=10,  # More retries
    )


async def startup(ctx: dict):
    """
    Initialize resources when the worker starts.
    
    This runs once when the worker process starts, setting up:
    - Prometheus metrics server on port 9091
    - Flask application context
    - Database connection
    - Trading engine with all exchange clients
    - Telegram notifier
    """
    logger.info("🚀 ARQ Worker starting up...")
    
    # Start Prometheus metrics server
    try:
        start_metrics_server(port=9091)
        logger.info("📊 Prometheus metrics server started on port 9091")
        set_app_info(version='3.0.0', environment=os.environ.get('FLASK_ENV', 'production'))
    except Exception as e:
        logger.warning(f"⚠️ Could not start metrics server: {e}")
    
    # Import here to avoid circular imports and ensure proper initialization
    from flask import Flask
    from config import Config
    from models import db
    from trading_engine import TradingEngine
    from telegram_notifier import init_notifier
    
    # Create minimal Flask app for database context
    app = Flask(__name__)
    app.config.from_object(Config)
    # Ensure REDIS_URL is present for worker (Config may not set it if env var missing)
    if not app.config.get('REDIS_URL'):
        app.config['REDIS_URL'] = REDIS_URL
        logger.info(f"✅ Worker REDIS_URL set from env/default: {REDIS_URL}")
    
    # Initialize database
    db.init_app(app)
    ctx['app'] = app
    ctx['db'] = db
    
    # Ensure tables exist within a scoped app context
    with app.app_context():
        db.create_all()
    
    # Initialize Telegram notifier
    telegram = None
    if hasattr(Config, 'TG_ENABLED') and Config.TG_ENABLED:
        telegram = init_notifier(Config.TG_TOKEN, Config.TG_CHAT_ID, True)
        if telegram and telegram.enabled:
            logger.info("✅ Telegram notifications enabled in worker")
            
            # Initialize error logging to Telegram for worker
            try:
                from telegram_notifier import setup_comprehensive_error_logging
                setup_comprehensive_error_logging(
                    telegram_notifier=telegram,
                    log_dir="logs",
                    include_warnings=True
                )
                logger.info("✅ Worker error notifications to Telegram enabled")
            except Exception as e:
                logger.warning(f"⚠️ Could not setup Telegram error logging in worker: {e}")
    ctx['telegram'] = telegram
    
    # ==================== TELEGRAM BOT (REMOVED FROM WORKER) ====================
    # The Telegram Bot now runs as a SEPARATE SERVICE via run_bot.py
    # to prevent 409 Conflict errors with Gunicorn workers.
    #
    # WHY: Running the bot in the worker still risks conflicts if:
    #   - Multiple worker instances are deployed
    #   - Worker restarts while bot is still connected
    #   - Development/staging environments use the same token
    #
    # SOLUTION: Bot runs in complete isolation via run_bot.py
    #   - Start with: sudo systemctl start mimic-bot
    #   - Completely independent from web server and worker
    #   - Single responsibility: handle Telegram polling ONLY
    #
    # The worker focuses purely on:
    #   ✓ Processing trading signals from Redis queue
    #   ✓ Running cron jobs (DCA, subscriptions, gamification)
    #   ✓ Trailing stop-loss monitoring
    #   ✓ Database tasks
    #
    telegram_bot = None
    ctx['telegram_bot'] = None
    logger.info("ℹ️ Telegram Bot runs as separate service (see mimic-bot.service)")
    
    # Initialize Trading Engine (no socketio needed in worker)
    engine = TradingEngine(app, socketio_instance=None, telegram_notifier=telegram)
    
    # Initialize master exchange client(s)
    engine.init_master()
    
    # Load slave clients from database
    engine.load_slaves()
    
    # Load global settings - prefer Redis (source of truth), then app module, then defaults
    settings_loaded = False
    try:
        import redis
        redis_client = redis.from_url(REDIS_URL)
        # Read settings from Redis (stored as strings)
        redis_settings = {
            'risk_perc': redis_client.get('global_settings:risk_perc'),
            'leverage': redis_client.get('global_settings:leverage'),
            'tp_perc': redis_client.get('global_settings:tp_perc'),
            'sl_perc': redis_client.get('global_settings:sl_perc'),
            'max_positions': redis_client.get('global_settings:max_positions'),
            'min_order_cost': redis_client.get('global_settings:min_balance'),
            'min_balance': redis_client.get('global_settings:min_balance'),
        }
        # Decode bytes to strings and keep only non-empty values
        cleaned = {}
        for k, v in redis_settings.items():
            if v is None:
                continue
            if isinstance(v, (bytes, bytearray)):
                v = v.decode('utf-8')
            cleaned[k] = v
        if cleaned:
            engine.set_global_settings(cleaned)
            logger.info("✅ Global settings loaded from Redis for worker")
            settings_loaded = True
    except Exception as e:
        logger.warning(f"⚠️ Could not load global settings from Redis: {e}")

    if not settings_loaded:
        try:
            from app import GLOBAL_TRADE_SETTINGS
            engine.set_global_settings(GLOBAL_TRADE_SETTINGS)
            logger.info("✅ Global settings loaded from app module")
        except ImportError:
            logger.warning("⚠️ Could not import GLOBAL_TRADE_SETTINGS, using defaults")
            engine.set_global_settings({
                'risk_perc': 3.0,
                'leverage': 20,
                'tp_perc': 5.0,
                'sl_perc': 2.0,
                'max_positions': 2,
                'min_order_cost': 1.0,
                'min_balance': 1.0
            })
    
    ctx['engine'] = engine
    
    # NOTE: Panic callback is set in run_bot.py, not here
    # The bot service has its own trading engine instance for panic commands

    # Initialize Smart Features (Trailing SL, DCA) with Redis
    try:
        import redis.asyncio as aioredis
        settings = parse_redis_url(REDIS_URL)
        redis_client = aioredis.Redis(
            host=settings.host,
            port=settings.port,
            db=settings.database,
            password=settings.password,
            socket_timeout=10,
        )
        await redis_client.ping()
        engine.set_redis_client(redis_client, redis_url=REDIS_URL)
        ctx['redis_client'] = redis_client
        logger.info("✅ Smart Features Redis client initialized")
        
        # Start trailing stop-loss monitor
        await engine.start_trailing_sl_monitor()
        logger.info("🎯 Trailing stop-loss monitor started")
        
        # Initialize AI Sentiment Manager
        try:
            from sentiment import SentimentManager, set_sentiment_manager
            sentiment_manager = SentimentManager(redis_client)
            set_sentiment_manager(sentiment_manager)
            engine.set_sentiment_manager(sentiment_manager)
            
            # Fetch initial sentiment on startup
            initial_sentiment = await sentiment_manager.update_sentiment()
            logger.info(f"🧠 AI Sentiment Filter initialized: Fear & Greed Index = {initial_sentiment.get('value')}")
        except Exception as sentiment_e:
            logger.warning(f"⚠️ AI Sentiment Filter not available: {sentiment_e}")
            
    except Exception as e:
        logger.warning(f"⚠️ Smart Features not available: {e}")
    
    logger.info(f"✅ ARQ Worker initialized successfully")
    logger.info(f"   - Master clients: {len(engine.master_clients)}")
    logger.info(f"   - Slave clients: {len(engine.slave_clients)}")
    
    # Notify via Telegram
    if telegram:
        telegram.notify_system_event(
            "Worker Started",
            f"ARQ worker initialized with {len(engine.master_clients)} master(s), {len(engine.slave_clients)} slave(s)"
        )


async def shutdown(ctx: dict):
    """
    Cleanup resources when the worker shuts down.
    """
    logger.info("🛑 ARQ Worker shutting down...")
    
    engine = ctx.get('engine')
    telegram = ctx.get('telegram')
    app = ctx.get('app')
    db = ctx.get('db')
    redis_client = ctx.get('redis_client')
    
    # Stop trailing SL monitor
    if engine:
        try:
            await engine.stop_trailing_sl_monitor()
            logger.info("🛑 Trailing stop-loss monitor stopped")
        except Exception as e:
            logger.warning(f"⚠️ Error stopping trailing SL monitor: {e}")
    
    # Close Redis client
    if redis_client:
        try:
            await redis_client.aclose()
            logger.info("🛑 Redis client closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing Redis client: {e}")
    
    # Close all async exchange connections
    if engine:
        # Close master CCXT async clients
        for master_data in engine.master_clients:
            if master_data.get('is_async') and master_data.get('is_ccxt'):
                try:
                    await master_data['client'].close()
                    logger.info(f"Closed master exchange: {master_data.get('exchange_name', 'Unknown')}")
                except Exception as e:
                    logger.error(f"Error closing master exchange: {e}")
        
        # Close slave CCXT async clients
        for slave_data in engine.slave_clients:
            if slave_data.get('is_async') and slave_data.get('is_ccxt'):
                try:
                    await slave_data['client'].close()
                    logger.info(f"Closed slave exchange: {slave_data.get('name', 'Unknown')}")
                except Exception as e:
                    logger.error(f"Error closing slave exchange: {e}")
    
    # NOTE: Telegram Bot runs as separate service, not managed by worker
    # It will be stopped independently via: sudo systemctl stop mimic-bot
    
    # Notify via Telegram
    if telegram:
        telegram.notify_system_event("Worker Stopped", "ARQ worker has been shut down")
    
    # Clean up SQLAlchemy sessions safely without relying on a stored context
    if app and db:
        try:
            with app.app_context():
                db.session.remove()
        except Exception as e:
            logger.debug(f"App context cleanup: {e}")

    # If a legacy app context was stored in ctx, pop it safely
    app_context = ctx.pop('app_context', None)
    if app_context:
        try:
            app_context.pop()
        except (LookupError, RuntimeError):
            # Context was already gone or never pushed
            logger.debug("App context already popped during shutdown")
        except Exception as e:
            logger.debug(f"App context pop error: {e}")
    
    logger.info("✅ ARQ Worker shutdown complete")


# Import task functions
from tasks import (
    execute_signal_task, 
    health_check_task, 
    check_subscription_expiry_task,
    monitor_trailing_stops_task,
    execute_dca_check_task,
    smart_features_status_task,
    # Risk Guardrails tasks
    reset_daily_balances_task,
    check_risk_guardrails_status_task,
    # AI Sentiment Filter tasks
    update_market_sentiment_task,
    get_sentiment_status_task,
    # Gamification tasks
    calculate_user_xp_task,
    check_achievements_task,
    get_gamification_status_task,
)


class WorkerSettings:
    """
    ARQ Worker configuration.
    
    This class is used by the 'arq' command to configure the worker.
    """
    
    # Task functions to register
    functions = [
        execute_signal_task,
        health_check_task,
        check_subscription_expiry_task,
        # Smart Features tasks
        monitor_trailing_stops_task,
        execute_dca_check_task,
        smart_features_status_task,
        # Risk Guardrails tasks
        reset_daily_balances_task,
        check_risk_guardrails_status_task,
        # AI Sentiment Filter tasks
        update_market_sentiment_task,
        get_sentiment_status_task,
        # Gamification tasks
        calculate_user_xp_task,
        check_achievements_task,
        get_gamification_status_task,
    ]
    
    # Cron jobs - scheduled tasks
    cron_jobs = [
        # Check subscription expiry daily at 9:00 AM UTC
        cron(check_subscription_expiry_task, hour=9, minute=0),
        # Check DCA opportunities every 5 minutes
        cron(execute_dca_check_task, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        # Reset daily balances at 00:00 UTC (midnight) - Risk Guardrails
        cron(reset_daily_balances_task, hour=0, minute=0),
        # Update market sentiment every hour (AI Sentiment Filter)
        cron(update_market_sentiment_task, minute=0),
        # Calculate user XP daily at 01:00 UTC (Gamification)
        cron(calculate_user_xp_task, hour=1, minute=0),
    ]
    
    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown
    
    # Redis connection settings
    redis_settings = parse_redis_url(REDIS_URL)
    
    # Queue name (matches what webhook pushes to)
    queue_name = 'arq:queue'
    
    # Worker settings
    max_jobs = 10  # Max concurrent jobs
    job_timeout = timedelta(minutes=5)  # Max time per job
    max_tries = 3  # Retry failed jobs up to 3 times
    retry_jobs = True  # Enable job retries
    
    # Health check interval (in seconds)
    health_check_interval = 30
    
    # Graceful shutdown timeout
    job_shutdown_timeout = timedelta(seconds=30)
    
    # Keep finished job results for 1 hour
    keep_result = timedelta(hours=1)
    
    # Logging
    log_results = True


if __name__ == '__main__':
    """
    Run the worker directly with: python worker.py
    
    For production, use: arq worker.WorkerSettings
    """
    from arq.worker import Worker, create_worker
    
    print("""
    +===================================================================+
    |                                                                   |
    |             M I M I C   A R Q   W O R K E R                       |
    |                                                                   |
    |                  ================================                  |
    |                    B R A I N   C A P I T A L                      |
    |                          v 9 . 0                                  |
    |                  ================================                  |
    |              Background Task Processor                            |
    |                                                                   |
    +===================================================================+
    |                                                                   |
    |   [*] Redis:      {redis_url}
    |   [*] Queue:      arq:queue                                       |
    |   [*] Max Jobs:   10 concurrent                                   |
    |                                                                   |
    |   [OK] Status:    Starting worker...                              |
    |                                                                   |
    +===================================================================+
    """.format(redis_url=REDIS_URL[:50] + '...' if len(REDIS_URL) > 50 else REDIS_URL))
    
    # Python 3.10+ compatible way to run the worker
    async def test_redis_async():
        """Test async Redis connection before starting worker."""
        import redis.asyncio as aioredis
        
        settings = WorkerSettings.redis_settings
        print(f"    [*] Testing async Redis: {settings.host}:{settings.port}")
        
        try:
            client = aioredis.Redis(
                host=settings.host,
                port=settings.port,
                db=settings.database,
                password=settings.password,
                socket_timeout=10,
                socket_connect_timeout=10,
            )
            await client.ping()
            await client.aclose()
            print(f"    [OK] Async Redis connection successful!")
            return True
        except Exception as e:
            print(f"    [!] Async Redis failed: {e}")
            return False
    
    async def main():
        """Run the ARQ worker with proper event loop handling."""
        from arq.worker import Worker
        
        # Test Redis connection first
        if not await test_redis_async():
            print("\n[!] Cannot connect to Redis. Please check:")
            print("    1. Redis is running: redis-cli ping")
            print("    2. Redis is listening on 127.0.0.1:6379")
            print("    3. Windows Firewall allows Redis connections")
            print("    4. Try: redis-server --bind 127.0.0.1")
            return
        
        # Get worker kwargs from settings
        kwargs = {
            'functions': WorkerSettings.functions,
            'on_startup': WorkerSettings.on_startup,
            'on_shutdown': WorkerSettings.on_shutdown,
            'redis_settings': WorkerSettings.redis_settings,
            'queue_name': WorkerSettings.queue_name,
            'max_jobs': WorkerSettings.max_jobs,
            'job_timeout': WorkerSettings.job_timeout,
            'max_tries': WorkerSettings.max_tries,
            'retry_jobs': WorkerSettings.retry_jobs,
            'health_check_interval': WorkerSettings.health_check_interval,
            'keep_result': WorkerSettings.keep_result,
            'log_results': WorkerSettings.log_results,
        }
        
        worker = Worker(**kwargs)
        await worker.main()
    
    # Run with asyncio.run() for Python 3.10+ compatibility
    asyncio.run(main())

