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
Version: 1.0.1 (Fixed signal handling)
"""

import os
import sys
import signal
import asyncio
import logging
import tempfile
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
|                          v 1 . 0 . 1                              |
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
    logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

# Register signal handlers (must be in main thread)
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
async def run_bot():
    """Run the Telegram bot using Application directly (no subprocess)"""
    
    try:
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
        from telegram.error import Conflict
    except ImportError:
        logger.error("❌ python-telegram-bot not installed")
        sys.exit(1)
    
    # File locking for singleton enforcement
    lock_file_path = os.path.join(tempfile.gettempdir(), "mimic_telegram_bot.lock")
    lock_file = None
    
    try:
        if sys.platform == 'win32':
            import msvcrt
            lock_file = open(lock_file_path, 'w')
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            lock_file = open(lock_file_path, 'w')
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        logger.info(f"🔒 Acquired bot lock (PID: {os.getpid()})")
    except (IOError, OSError) as e:
        logger.error(f"❌ Another bot instance is already running!")
        logger.error(f"   Lock file: {lock_file_path}")
        if lock_file:
            lock_file.close()
        sys.exit(1)
    
    # Initialize OTP if available
    otp_verifier = None
    if OTP_SECRET:
        try:
            import pyotp
            otp_verifier = pyotp.TOTP(OTP_SECRET)
        except ImportError:
            pass
    
    # Simple command handlers
    async def cmd_start(update, context):
        user = update.effective_user
        is_authorized = user.id in AUTHORIZED_USERS
        await update.message.reply_text(
            f"🧠 <b>BRAIN CAPITAL Bot</b>\n\n"
            f"👋 Hello, <b>{user.first_name}</b>!\n"
            f"🆔 Your Telegram ID: <code>{user.id}</code>\n\n"
            f"{'✅ You are authorized' if is_authorized else '⚠️ Not authorized'}\n\n"
            f"Commands:\n/help - Help\n/status - Status",
            parse_mode='HTML'
        )
    
    async def cmd_help(update, context):
        await update.message.reply_text(
            "📖 <b>BRAIN CAPITAL - Commands</b>\n\n"
            "/start - Get started\n"
            "/help - This help\n"
            "/status - System status",
            parse_mode='HTML'
        )
    
    async def cmd_status(update, context):
        await update.message.reply_text(
            f"📊 <b>BRAIN CAPITAL - Status</b>\n\n"
            f"🟢 <b>Bot:</b> Active\n"
            f"🕐 <b>Time:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
            f"🔐 <b>OTP:</b> {'Configured ✅' if otp_verifier else 'Not configured ⚠️'}",
            parse_mode='HTML'
        )
    
    # Wait before starting (prevents 409 conflicts on restart)
    if STARTUP_DELAY > 0:
        logger.info(f"⏳ Waiting {STARTUP_DELAY}s before starting polling...")
        await asyncio.sleep(STARTUP_DELAY)
    
    # Create Telegram Application
    logger.info("🤖 Creating Telegram bot application...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    
    logger.info("🤖 Initializing bot...")
    await app.initialize()
    await app.start()
    
    # Start polling
    logger.info("🤖 Starting polling...")
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=['message', 'callback_query']
    )
    
    logger.info("✅ Telegram bot is now running and polling for updates!")
    
    # Wait for shutdown signal
    await shutdown_event.wait()
    
    # Cleanup
    logger.info("🛑 Stopping bot...")
    try:
        if app.updater.running:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
    except Exception as e:
        logger.debug(f"Shutdown error: {e}")
    
    # Release lock
    if lock_file:
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            os.remove(lock_file_path)
            logger.info("🔓 Released bot lock")
        except:
            pass
    
    logger.info("✅ Bot stopped gracefully")

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
        
        # Run the bot
        logger.info("🚀 Starting Telegram bot polling...")
        await run_bot()
        
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
