#!/usr/bin/env python3
"""
Brain Capital - Standalone Telegram Bot Runner
==============================================

This script runs the Telegram bot as a completely separate process,
isolated from the web server (Gunicorn) and worker (ARQ).

IMPORTANT: This is the ONLY process that should run the Telegram bot polling!

Features:
- Cross-platform file locking (prevents multiple instances)
- Graceful shutdown handling (SIGTERM, SIGINT)
- Auto-restart on 409 Conflict (with exponential backoff)
- Comprehensive error logging
- Database connection for command handlers
- Panic close integration with trading engine

Usage:
    # Development
    python run_bot.py

    # Production (via systemd)
    sudo systemctl start mimic-bot
    sudo systemctl status mimic-bot
    sudo systemctl stop mimic-bot

Systemd Service:
    See mimic-bot.service for systemd integration

Author: Brain Capital Team
Version: 1.0.0
"""

import os
import sys
import signal
import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

# Setup logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/telegram_bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("TelegramBotRunner")

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Banner
print("""
+===================================================================+
|                                                                   |
|        M I M I C   T E L E G R A M   B O T   R U N N E R          |
|                                                                   |
|                  ================================                  |
|                    B R A I N   C A P I T A L                      |
|                          v 1 . 0 . 0                              |
|                  ================================                  |
|                                                                   |
|   [*] Status:    Starting bot in ISOLATED mode...                |
|   [*] Polling:   Singleton instance with file lock               |
|   [*] Safety:    409 Conflict detection & auto-restart           |
|                                                                   |
+===================================================================+
""")

# Load environment variables from .env
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    logger.info(f"📄 Loading environment from {env_file}")
    with open(env_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
else:
    logger.warning(f"⚠️ No .env file found at {env_file}")

# ==================== CONFIGURATION ====================
from config import Config

BOT_TOKEN = getattr(Config, 'TG_TOKEN', None)
ADMIN_CHAT_ID = getattr(Config, 'TG_CHAT_ID', None)
OTP_SECRET = getattr(Config, 'PANIC_OTP_SECRET', '') or ''
AUTHORIZED_USERS = getattr(Config, 'PANIC_AUTHORIZED_USERS', [])
STARTUP_DELAY = getattr(Config, 'TG_POLLING_STARTUP_DELAY', 30)

# Validate configuration
if not BOT_TOKEN:
    logger.error("❌ CRITICAL: TG_TOKEN not configured!")
    logger.error("   Set TG_TOKEN in .env or config.ini")
    logger.error("   Get your token from @BotFather on Telegram")
    sys.exit(1)

if ':' not in BOT_TOKEN or len(BOT_TOKEN) < 30:
    logger.error(f"❌ CRITICAL: Invalid bot token format!")
    logger.error("   Token should look like: 123456789:ABCdefGHI...")
    sys.exit(1)

logger.info("✅ Configuration loaded successfully")
logger.info(f"   - Bot Token: {BOT_TOKEN[:15]}...{BOT_TOKEN[-5:]}")
logger.info(f"   - Admin Chat ID: {ADMIN_CHAT_ID}")
logger.info(f"   - OTP Enabled: {bool(OTP_SECRET)}")
logger.info(f"   - Authorized Users: {len(AUTHORIZED_USERS)}")
logger.info(f"   - Startup Delay: {STARTUP_DELAY}s")

# ==================== SHUTDOWN HANDLING ====================
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    sig_name = signal.Signals(signum).name
    logger.info(f"🛑 Received {sig_name} signal, initiating graceful shutdown...")
    
    # Set the shutdown event to break the main loop
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(shutdown_event.set)
    except RuntimeError:
        # No running loop, set the event directly
        shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
if sys.platform != 'win32':
    signal.signal(signal.SIGTERM, signal_handler)  # systemctl stop
    signal.signal(signal.SIGHUP, signal_handler)   # systemctl reload

# ==================== DATABASE & FLASK CONTEXT ====================
def init_flask_app():
    """Initialize minimal Flask app for database access"""
    from flask import Flask
    from models import db
    
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize database
    db.init_app(app)
    
    # Create tables if needed
    with app.app_context():
        db.create_all()
    
    logger.info("✅ Flask app and database initialized")
    return app, db

# ==================== MAIN BOT LOGIC ====================
async def run_telegram_bot():
    """
    Main async function that runs the Telegram bot.
    
    This function:
    1. Imports the bot module (contains all handlers and logic)
    2. Directly calls the process main function that handles everything:
       - File locking (singleton enforcement)
       - Session invalidation (prevents 409 conflicts)
       - Polling setup with retry logic
       - Command handlers (/start, /help, /panic_close_all, etc.)
       - Graceful shutdown
    """
    from telegram_bot import _telegram_bot_process_main
    
    logger.info("🤖 Launching Telegram bot process...")
    
    # The _telegram_bot_process_main function is designed to run in a separate
    # process, but we're calling it directly here since THIS script IS the
    # separate process (isolated from Gunicorn and ARQ worker)
    #
    # It will handle:
    # - Cross-platform file locking to prevent multiple instances
    # - Aggressive session invalidation to avoid 409 conflicts
    # - Full bot initialization with all command handlers
    # - Health monitoring and auto-restart on errors
    # - Graceful shutdown on SIGTERM/SIGINT
    
    try:
        # Run the bot in the current process (not a subprocess)
        # We need to call it in a way that works with asyncio
        
        # Since _telegram_bot_process_main uses asyncio.run() internally,
        # we need to run it in a thread executor to avoid nested event loops
        import concurrent.futures
        
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await loop.run_in_executor(
                pool,
                _telegram_bot_process_main,
                BOT_TOKEN,
                ADMIN_CHAT_ID or '',
                AUTHORIZED_USERS,
                OTP_SECRET,
                STARTUP_DELAY
            )
    except Exception as e:
        logger.error(f"❌ Bot process error: {e}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise

async def main():
    """Main entry point with Flask context and trading engine integration"""
    
    # Initialize Flask app and database
    app, db = init_flask_app()
    
    # Push application context
    app_context = app.app_context()
    app_context.push()
    
    try:
        # Initialize Trading Engine (needed for panic callback)
        from trading_engine import TradingEngine
        from telegram_notifier import get_notifier
        
        telegram_notifier = get_notifier()
        engine = TradingEngine(app, socketio_instance=None, telegram_notifier=telegram_notifier)
        
        # Initialize master and load slaves
        engine.init_master()
        engine.load_slaves()
        
        logger.info(f"✅ Trading engine initialized")
        logger.info(f"   - Master clients: {len(engine.master_clients)}")
        logger.info(f"   - Slave clients: {len(engine.slave_clients)}")
        
        # Import panic callback integration
        # Note: The bot will call engine.close_all_positions_all_accounts when panic is triggered
        # We don't need to pass it here since the bot accesses it through imports
        
        # Run the bot
        logger.info("🚀 Starting Telegram bot polling...")
        await run_telegram_bot()
        
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise
    finally:
        logger.info("🧹 Cleaning up...")
        
        # Pop application context
        try:
            app_context.pop()
        except Exception as e:
            logger.debug(f"Context cleanup error: {e}")
        
        logger.info("✅ Shutdown complete")

# ==================== ENTRY POINT ====================
if __name__ == '__main__':
    try:
        # Python 3.7+ compatible asyncio.run()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
        sys.exit(1)
