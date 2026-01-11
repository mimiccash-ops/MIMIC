"""
Brain Capital Telegram Bot - Kill Switch Handler

This module provides a Telegram bot that can receive commands for emergency actions,
including the panic close all positions command with 2FA (OTP) verification.

SECURITY FEATURES:
- OTP (TOTP) verification for panic commands
- Authorized user whitelist
- Command rate limiting
- Full audit logging
"""

import logging
import time
import threading
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from functools import wraps

logger = logging.getLogger("TelegramBot")

# Try to import required packages
try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    PYOTP_AVAILABLE = False
    logger.warning("⚠️ pyotp not installed. OTP verification disabled. Install with: pip install pyotp")

try:
    from telegram import Update, Bot
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False
    logger.warning("⚠️ python-telegram-bot[ext] not installed. Telegram bot commands disabled.")


def _telegram_bot_process_main(bot_token: str, admin_chat_id: str, authorized_users: list, otp_secret: str, startup_delay: int = 30):
    """
    Main function that runs the Telegram bot in a separate process.
    This function MUST be at module level to be picklable by multiprocessing.
    
    Runs a simplified bot with basic commands when eventlet is active.
    
    Args:
        bot_token: Telegram bot token
        admin_chat_id: Admin chat ID for notifications
        authorized_users: List of authorized user IDs
        otp_secret: OTP secret for 2FA
        startup_delay: Seconds to wait before starting polling (helps avoid 409 conflicts on restart)
    """
    import asyncio
    import logging
    import signal
    import sys
    import time
    import os
    import fcntl
    from datetime import datetime
    from pathlib import Path
    
    # Set up logging for this process
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    proc_logger = logging.getLogger("TelegramBotProcess")
    
    # ============ FILE-BASED LOCK TO PREVENT MULTIPLE INSTANCES ============
    # This ensures only ONE bot process can run at a time
    lock_file_path = "/tmp/mimic_telegram_bot.lock"
    lock_file = None
    
    try:
        lock_file = open(lock_file_path, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        proc_logger.info(f"🔒 Acquired bot lock (PID: {os.getpid()})")
    except (IOError, OSError) as e:
        proc_logger.error(f"❌ Another Telegram bot instance is already running! Cannot acquire lock.")
        proc_logger.error(f"   Lock file: {lock_file_path}")
        proc_logger.error(f"   Error: {e}")
        proc_logger.error(f"   To fix: Check for existing bot processes or delete {lock_file_path}")
        if lock_file:
            lock_file.close()
        return
    except Exception as e:
        # On Windows or if fcntl isn't available, continue without lock
        proc_logger.warning(f"⚠️ Could not acquire file lock (non-fatal on Windows): {e}")
    
    # Handle termination signals gracefully
    shutdown_requested = False
    
    def handle_signal(signum, frame):
        nonlocal shutdown_requested
        proc_logger.info(f"🤖 Received signal {signum}, initiating graceful shutdown...")
        shutdown_requested = True
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
        from telegram.error import Conflict, NetworkError, TimedOut
    except ImportError:
        proc_logger.error("python-telegram-bot not installed")
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                os.remove(lock_file_path)
            except:
                pass
        return
    
    # Initialize OTP if available
    otp_verifier = None
    try:
        import pyotp
        if otp_secret:
            otp_verifier = pyotp.TOTP(otp_secret)
    except ImportError:
        pass
    
    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        is_authorized = user.id in authorized_users
        await update.message.reply_text(
            f"🧠 <b>BRAIN CAPITAL Bot</b>\n\n"
            f"👋 Вітаю, <b>{user.first_name}</b>!\n"
            f"🆔 Ваш Telegram ID: <code>{user.id}</code>\n\n"
            f"{'✅ <b>Ви авторизовані</b>' if is_authorized else '⚠️ Ви не авторизовані'}\n\n"
            f"Команди:\n/help - Довідка\n/status - Статус",
            parse_mode='HTML'
        )
    
    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📖 <b>BRAIN CAPITAL - Команди</b>\n\n"
            "/start - Початок\n"
            "/help - Довідка\n"
            "/status - Статус системи",
            parse_mode='HTML'
        )
    
    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"📊 <b>BRAIN CAPITAL - Статус</b>\n\n"
            f"🟢 <b>Бот:</b> Активний\n"
            f"🕐 <b>Час:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
            f"🔐 <b>OTP:</b> {'Налаштовано ✅' if otp_verifier else 'Не налаштовано ⚠️'}",
            parse_mode='HTML'
        )
    
    async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "❓ Невідома команда.\n\nВведіть /help для списку команд.",
            parse_mode='HTML'
        )
    
    async def force_invalidate_telegram_session(client, token: str, max_attempts: int = 5) -> bool:
        """
        Forcefully invalidate any existing Telegram polling session.
        Uses multiple short getUpdates calls to take over from any other instance.
        
        Returns True if successfully took over, False if persistent conflict.
        """
        for attempt in range(max_attempts):
            try:
                # Delete webhook first
                await client.post(
                    f"https://api.telegram.org/bot{token}/deleteWebhook",
                    json={"drop_pending_updates": True},
                    timeout=10.0
                )
                
                # Short timeout getUpdates to invalidate other sessions
                # The key is to use timeout=0 which returns immediately
                # and tells Telegram we want to take over polling
                response = await client.post(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    json={"limit": 1, "timeout": 0, "offset": -1},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        # Success! Clear any pending updates
                        if data.get("result"):
                            latest_id = data["result"][-1]["update_id"]
                            await client.post(
                                f"https://api.telegram.org/bot{token}/getUpdates",
                                json={"offset": latest_id + 1, "limit": 1, "timeout": 0},
                                timeout=10.0
                            )
                            proc_logger.info(f"✅ Cleared updates up to ID {latest_id}")
                        else:
                            proc_logger.info("✅ Session invalidated, no pending updates")
                        return True
                        
                elif response.status_code == 409:
                    proc_logger.warning(f"⚠️ 409 Conflict during invalidation (attempt {attempt + 1}/{max_attempts})")
                    # Wait a bit and try again - other bot should stop soon
                    await asyncio.sleep(3)
                    continue
                    
            except Exception as e:
                proc_logger.warning(f"⚠️ Invalidation attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2)
        
        return False
    
    async def main():
        import httpx
        
        proc_logger.info("🤖 Starting Telegram bot in isolated process...")
        
        # Wait before starting to allow any previous instance to fully terminate
        # This prevents 409 Conflict errors on service restart
        if startup_delay > 0:
            proc_logger.info(f"⏳ Waiting {startup_delay}s before starting polling (prevents 409 conflicts)...")
            await asyncio.sleep(startup_delay)
        
        # ============ AGGRESSIVE SESSION INVALIDATION ============
        # This is critical for avoiding 409 conflicts
        proc_logger.info("🔄 Invalidating any existing Telegram polling sessions...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            session_ok = await force_invalidate_telegram_session(client, bot_token, max_attempts=5)
            
            if not session_ok:
                proc_logger.warning("⚠️ Could not cleanly invalidate session, will try to start anyway...")
                # Extra wait before proceeding
                await asyncio.sleep(5)
        
        # Build the application with custom error handling
        app = Application.builder().token(bot_token).build()
        
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
        
        proc_logger.info("🤖 Telegram bot initializing...")
        
        await app.initialize()
        await app.start()
        
        # ============ START POLLING WITH ADVANCED RETRY LOGIC ============
        max_retries = 10
        base_delay = 5
        conflict_detected = False
        
        # Custom error handler to detect 409 conflicts early
        async def error_handler(update, context):
            nonlocal conflict_detected
            if isinstance(context.error, Conflict):
                conflict_detected = True
                proc_logger.warning(f"⚠️ Conflict detected in error handler: {context.error}")
        
        app.add_error_handler(error_handler)
        
        for attempt in range(max_retries):
            try:
                conflict_detected = False
                
                # Start polling with drop_pending_updates to avoid processing old messages
                await app.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=['message', 'callback_query'],
                )
                proc_logger.info("🤖 Telegram bot is now running and polling for updates")
                
                # Wait and actively check for conflicts over multiple intervals
                # This is more reliable than a single check
                stable_checks = 0
                required_stable_checks = 5  # Need 5 consecutive stable checks (10 seconds total)
                
                for check_num in range(10):  # Check for up to 20 seconds
                    await asyncio.sleep(2)
                    
                    if conflict_detected:
                        proc_logger.warning(f"⚠️ Conflict detected during stability check {check_num + 1}")
                        raise Conflict("409 Conflict detected during polling")
                    
                    if not app.updater.running:
                        proc_logger.warning(f"⚠️ Updater stopped during stability check {check_num + 1}")
                        raise Conflict("Updater stopped unexpectedly")
                    
                    stable_checks += 1
                    if stable_checks >= required_stable_checks:
                        proc_logger.info(f"✅ Telegram bot polling confirmed stable after {stable_checks} checks ({stable_checks * 2}s)")
                        break
                
                if stable_checks >= required_stable_checks:
                    break  # Exit retry loop - we're stable
                else:
                    raise Conflict("Failed to achieve stable polling")
                    
            except Conflict as e:
                proc_logger.warning(f"⚠️ 409 Conflict (attempt {attempt + 1}/{max_retries}): {e}")
                
                # Stop the updater if it's running
                try:
                    if app.updater.running:
                        await app.updater.stop()
                except:
                    pass
                
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    import random
                    wait_time = base_delay * (2 ** min(attempt, 5)) + random.uniform(0, 5)
                    proc_logger.info(f"⏳ Waiting {wait_time:.1f}s before retry...")
                    await asyncio.sleep(wait_time)
                    
                    # Try to invalidate the session again before retrying
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        await force_invalidate_telegram_session(client, bot_token, max_attempts=3)
                else:
                    proc_logger.error("=" * 60)
                    proc_logger.error("❌ FAILED TO START TELEGRAM BOT AFTER MAX RETRIES")
                    proc_logger.error("=" * 60)
                    proc_logger.error("❌ CRITICAL: Another bot instance is blocking polling!")
                    proc_logger.error("❌ Check for:")
                    proc_logger.error("❌   - Another server using the same bot token")
                    proc_logger.error("❌   - A developer's local machine running the bot")
                    proc_logger.error("❌   - Docker container with the bot")
                    proc_logger.error("❌   - Orphaned processes on this server")
                    proc_logger.error("=" * 60)
                    await app.stop()
                    await app.shutdown()
                    return
                    
            except Exception as e:
                proc_logger.error(f"❌ Unexpected error starting polling: {e}")
                import traceback
                proc_logger.error(traceback.format_exc())
                raise
        
        # Keep running until interrupted
        proc_logger.info("🤖 Bot is running. Press Ctrl+C to stop.")
        
        # Track consecutive 409 errors for smart backoff
        consecutive_conflicts = 0
        last_conflict_time = None
        
        try:
            while not shutdown_requested:
                await asyncio.sleep(1)
                
                # Check if conflict was detected by error handler
                if conflict_detected:
                    consecutive_conflicts += 1
                    last_conflict_time = datetime.now()
                    proc_logger.warning(f"⚠️ 409 Conflict detected (#{consecutive_conflicts})")
                    
                    if consecutive_conflicts >= 3:
                        proc_logger.error("=" * 60)
                        proc_logger.error("❌ PERSISTENT 409 CONFLICT - ANOTHER BOT IS RUNNING!")
                        proc_logger.error("=" * 60)
                        proc_logger.error("This usually means:")
                        proc_logger.error("  1. Another server is using the SAME bot token")
                        proc_logger.error("  2. A developer's machine has the bot running")
                        proc_logger.error("  3. A Docker container or staging server")
                        proc_logger.error("  4. BotFather shows your token - REGENERATE it!")
                        proc_logger.error("")
                        proc_logger.error("To fix:")
                        proc_logger.error("  1. Stop ALL other instances using this token")
                        proc_logger.error("  2. Or regenerate token: @BotFather → /mybots → API Token")
                        proc_logger.error("=" * 60)
                        
                        # Stop this bot to prevent infinite 409 spam
                        break
                    
                    # Wait before next check
                    await asyncio.sleep(10)
                    conflict_detected = False  # Reset for next check
                    continue
                else:
                    # Reset counter if stable for a while
                    if last_conflict_time and (datetime.now() - last_conflict_time).seconds > 60:
                        if consecutive_conflicts > 0:
                            proc_logger.info(f"✅ No conflicts for 60s, resetting counter (was {consecutive_conflicts})")
                        consecutive_conflicts = 0
                
                # Periodically check if updater is still running
                if not app.updater.running:
                    proc_logger.warning("⚠️ Updater stopped unexpectedly, attempting restart...")
                    try:
                        # Wait before attempting restart to avoid rapid loops
                        await asyncio.sleep(5)
                        await app.updater.start_polling(
                            drop_pending_updates=False,
                            allowed_updates=['message', 'callback_query']
                        )
                        proc_logger.info("✅ Updater restarted")
                    except Conflict:
                        proc_logger.error("❌ 409 Conflict on restart - another bot took over")
                        consecutive_conflicts += 1
                        if consecutive_conflicts >= 3:
                            break
                    except Exception as e:
                        proc_logger.error(f"❌ Failed to restart updater: {e}")
                        break
                        
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            proc_logger.info("🤖 Telegram bot shutting down...")
            try:
                if app.updater.running:
                    await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except Exception as e:
                proc_logger.debug(f"Shutdown error (can be ignored): {e}")
    
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        proc_logger.error(f"Bot process error: {e}")
        import traceback
        proc_logger.error(traceback.format_exc())
    finally:
        # Release the file lock
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                os.remove(lock_file_path)
                proc_logger.info("🔓 Released bot lock")
            except Exception as e:
                proc_logger.debug(f"Lock cleanup error: {e}")


class OTPVerifier:
    """
    TOTP (Time-based One-Time Password) verifier for 2FA
    
    Compatible with Google Authenticator, Authy, and other TOTP apps.
    """
    
    def __init__(self, secret: str):
        """
        Initialize OTP verifier with a base32-encoded secret.
        
        Args:
            secret: Base32-encoded secret key (generate with pyotp.random_base32())
        """
        self.secret = secret
        self.totp = None
        
        if PYOTP_AVAILABLE and secret:
            try:
                self.totp = pyotp.TOTP(secret)
                logger.info("✅ OTP Verifier initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OTP: {e}")
    
    def verify(self, code: str) -> bool:
        """
        Verify an OTP code.
        
        Args:
            code: 6-digit OTP code from authenticator app
            
        Returns:
            True if code is valid, False otherwise
        """
        if not self.totp:
            logger.warning("OTP verification attempted but not configured")
            return False
        
        try:
            # Clean the code (remove spaces, dashes)
            clean_code = ''.join(filter(str.isdigit, str(code)))
            
            # Verify with a small window for clock drift (±30 seconds)
            is_valid = self.totp.verify(clean_code, valid_window=1)
            
            if is_valid:
                logger.info("✅ OTP verification successful")
            else:
                logger.warning(f"❌ OTP verification failed for code: {clean_code[:2]}****")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"OTP verification error: {e}")
            return False
    
    def get_provisioning_uri(self, name: str = "BrainCapital", issuer: str = "MIMIC") -> str:
        """
        Get the provisioning URI for QR code generation.
        
        This URI can be converted to a QR code that users scan with their
        authenticator app (Google Authenticator, Authy, etc.)
        
        Args:
            name: Account name to display in the authenticator app
            issuer: Issuer name to display
            
        Returns:
            otpauth:// URI string
        """
        if not self.totp:
            return ""
        
        return self.totp.provisioning_uri(name=name, issuer_name=issuer)
    
    def get_current_code(self) -> str:
        """
        Get the current OTP code (for testing/debugging only).
        
        WARNING: Only use this for initial setup verification!
        
        Returns:
            Current 6-digit OTP code
        """
        if not self.totp:
            return ""
        return self.totp.now()


class RateLimiter:
    """Simple rate limiter for command protection"""
    
    def __init__(self, max_attempts: int = 3, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: Dict[int, list] = {}
        self._lock = threading.Lock()
    
    def check(self, user_id: int) -> bool:
        """Check if user is within rate limits"""
        with self._lock:
            now = time.time()
            
            # Clean old attempts
            if user_id in self.attempts:
                self.attempts[user_id] = [
                    t for t in self.attempts[user_id]
                    if now - t < self.window_seconds
                ]
            else:
                self.attempts[user_id] = []
            
            # Check limit
            if len(self.attempts[user_id]) >= self.max_attempts:
                return False
            
            # Record attempt
            self.attempts[user_id].append(now)
            return True
    
    def get_remaining_time(self, user_id: int) -> int:
        """Get remaining seconds until rate limit resets"""
        if user_id not in self.attempts or not self.attempts[user_id]:
            return 0
        
        oldest = min(self.attempts[user_id])
        remaining = self.window_seconds - (time.time() - oldest)
        return max(0, int(remaining))


class TelegramBotHandler:
    """
    Telegram Bot Handler for Brain Capital
    
    Provides command handling for emergency actions with 2FA verification.
    
    Commands:
    - /start - Bot introduction and help
    - /help - List available commands
    - /status - Check system status
    - /panic_close_all <OTP> - Emergency close all positions (requires 2FA)
    """
    
    def __init__(
        self,
        bot_token: str,
        otp_secret: str,
        authorized_users: list,
        panic_callback: Callable = None,
        admin_chat_id: str = None
    ):
        """
        Initialize the Telegram bot handler.
        
        Args:
            bot_token: Telegram bot token from @BotFather
            otp_secret: Base32-encoded TOTP secret for 2FA
            authorized_users: List of Telegram user IDs authorized to use panic commands
            panic_callback: Callback function to execute panic close (should be engine.close_all_positions_all_accounts)
            admin_chat_id: Chat ID for admin notifications
        """
        self.bot_token = bot_token
        self.authorized_users = authorized_users
        self.panic_callback = panic_callback
        self.admin_chat_id = admin_chat_id
        self.application = None
        self.bot = None
        self._running = False
        
        # Initialize OTP verifier
        self.otp_verifier = OTPVerifier(otp_secret) if otp_secret else None
        
        # Rate limiter for panic commands (3 attempts per 5 minutes)
        self.panic_limiter = RateLimiter(max_attempts=3, window_seconds=300)
        
        # OTP failure limiter (5 wrong codes = blocked for 15 minutes)
        self.otp_failure_limiter = RateLimiter(max_attempts=5, window_seconds=900)
        
        # Pending panic confirmations (user_id -> timestamp)
        self.pending_confirmations: Dict[int, float] = {}
        
        if not TELEGRAM_BOT_AVAILABLE:
            logger.error("❌ Telegram bot dependencies not available")
            return
        
        if not bot_token:
            logger.warning("⚠️ Telegram bot token not provided")
            return
        
        # Note: Application is now created in the background thread to avoid event loop issues
        logger.info("✅ Telegram Bot Handler initialized (application will be created on start)")
    
    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized for panic commands"""
        return user_id in self.authorized_users
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        user_id = user.id
        
        is_authorized = self._is_authorized(user_id)
        
        welcome_msg = f"""
🧠 <b>BRAIN CAPITAL Bot</b>

👋 Вітаю, <b>{user.first_name}</b>!

🆔 Ваш Telegram ID: <code>{user_id}</code>

{"✅ <b>Ви авторизовані</b> для використання panic-команд." if is_authorized else "⚠️ Ви <b>не авторизовані</b> для panic-команд."}

Доступні команди:
/help - Показати довідку
/status - Статус системи
/support &lt;питання&gt; - 🤖 AI Support Bot
{"/panic_close_all <OTP> - ⚠️ ЕКСТРЕНЕ закриття всіх позицій" if is_authorized else ""}

<i>Для авторизації зверніться до адміністратора.</i>
"""
        await update.message.reply_text(welcome_msg.strip(), parse_mode='HTML')
        
        logger.info(f"[TG] /start from {user.username} (ID: {user_id}), authorized: {is_authorized}")
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user = update.effective_user
        is_authorized = self._is_authorized(user.id)
        
        help_msg = """
📖 <b>BRAIN CAPITAL - Команди</b>

<b>Загальні команди:</b>
/start - Початок роботи
/help - Ця довідка
/status - Перевірити статус системи
/support &lt;питання&gt; - Запитати AI Support Bot

<b>Приклади запитань для /support:</b>
• /support Як підключити Binance?
• /support Що таке DCA?
• /support Як працює реферальна система?

"""
        
        if is_authorized:
            help_msg += """
<b>🚨 Panic-команди (потребують OTP):</b>
/panic_close_all &lt;OTP&gt; - Закрити ВСІ позиції

<b>Як використовувати panic:</b>
1. Відкрийте ваш Authenticator
2. Знайдіть код для "MIMIC/BrainCapital"
3. Введіть: /panic_close_all 123456

⚠️ <b>УВАГА:</b> Ця команда закриє ВСІ позиції на ВСІХ акаунтах (Master + Slaves)!

<b>Налаштування:</b>
/otp_setup - Показати URI для налаштування OTP
"""
        else:
            help_msg += """
<i>Panic-команди доступні лише авторизованим користувачам.</i>
<i>Ваш ID: </i><code>""" + str(user.id) + """</code>
"""
        
        await update.message.reply_text(help_msg.strip(), parse_mode='HTML')
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user = update.effective_user
        is_authorized = self._is_authorized(user.id)
        
        status_msg = f"""
📊 <b>BRAIN CAPITAL - Статус</b>

🟢 <b>Бот:</b> Активний
🕐 <b>Час:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
🔐 <b>OTP:</b> {"Налаштовано ✅" if self.otp_verifier and self.otp_verifier.totp else "Не налаштовано ⚠️"}
👤 <b>Ваш статус:</b> {"Авторизований ✅" if is_authorized else "Не авторизований ❌"}

{"🚨 <i>Panic-команди доступні</i>" if is_authorized else ""}
"""
        await update.message.reply_text(status_msg.strip(), parse_mode='HTML')
    
    async def _cmd_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /support command - AI Support Bot
        
        Uses RAG to answer user questions based on documentation.
        """
        user = update.effective_user
        args = context.args
        
        if not args:
            await update.message.reply_text(
                "🤖 <b>AI Support Bot</b>\n\n"
                "Задайте мені питання про платформу MIMIC!\n\n"
                "<b>Використання:</b>\n"
                "<code>/support Ваше питання тут</code>\n\n"
                "<b>Приклади:</b>\n"
                "• /support Як підключити Binance?\n"
                "• /support Що таке trailing stop-loss?\n"
                "• /support Як працює реферальна система?\n"
                "• /support Які біржі підтримуються?",
                parse_mode='HTML'
            )
            return
        
        question = ' '.join(args)
        
        # Indicate typing
        await update.message.chat.send_action('typing')
        
        # Get response from support bot
        try:
            from support_bot import chat_with_support
            
            response = chat_with_support(
                message=question,
                session_id=f"tg_{user.id}",
                user_id=None,  # Could link to MIMIC user if telegram_chat_id matches
                channel='telegram',
                telegram_chat_id=str(user.id)
            )
            
            answer = response.get('answer', 'Вибачте, не вдалося отримати відповідь.')
            confidence = response.get('confidence', 0)
            needs_review = response.get('needs_human_review', False)
            
            # Build response message
            reply_msg = f"🤖 <b>AI Support Bot</b>\n\n"
            reply_msg += f"<b>Питання:</b> {question[:100]}{'...' if len(question) > 100 else ''}\n\n"
            reply_msg += f"<b>Відповідь:</b>\n{answer}\n\n"
            
            # Add confidence indicator
            if confidence >= 0.8:
                confidence_icon = "🟢"
                confidence_text = "Висока впевненість"
            elif confidence >= 0.6:
                confidence_icon = "🟡"
                confidence_text = "Середня впевненість"
            else:
                confidence_icon = "🔴"
                confidence_text = "Низька впевненість"
            
            reply_msg += f"{confidence_icon} <i>{confidence_text} ({confidence:.0%})</i>\n"
            
            if needs_review:
                reply_msg += "\n⚠️ <i>Це питання передано на перевірку адміністратору.</i>"
            
            await update.message.reply_text(reply_msg, parse_mode='HTML')
            
            logger.info(f"[TG] Support question from {user.username}: {question[:50]}... (confidence: {confidence:.2f})")
            
        except ImportError as e:
            logger.error(f"Support bot import error: {e}")
            await update.message.reply_text(
                "❌ <b>AI Support Bot недоступний</b>\n\n"
                "Модуль підтримки не налаштовано.\n"
                "Зверніться до адміністратора.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Support bot error: {e}")
            await update.message.reply_text(
                "❌ <b>Помилка</b>\n\n"
                "Не вдалося обробити ваше питання.\n"
                "Спробуйте пізніше або зверніться до адміністратора.",
                parse_mode='HTML'
            )
    
    async def _cmd_panic_close_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /panic_close_all command - Emergency close all positions
        
        Requires:
        1. User to be in authorized_users list
        2. Valid OTP code from authenticator app
        """
        user = update.effective_user
        user_id = user.id
        
        logger.warning(f"🚨 [TG] PANIC command from {user.username} (ID: {user_id})")
        
        # Check authorization
        if not self._is_authorized(user_id):
            await update.message.reply_text(
                "⛔ <b>ДОСТУП ЗАБОРОНЕНО</b>\n\n"
                "Ви не авторизовані для використання цієї команди.\n"
                f"Ваш ID: <code>{user_id}</code>",
                parse_mode='HTML'
            )
            logger.warning(f"🚫 [TG] Unauthorized panic attempt from {user.username} (ID: {user_id})")
            
            # Notify admin
            if self.admin_chat_id:
                await self._notify_admin(
                    f"🚨 <b>НЕСАНКЦІОНОВАНА СПРОБА PANIC</b>\n\n"
                    f"Користувач: @{user.username}\n"
                    f"ID: <code>{user_id}</code>\n"
                    f"Час: {datetime.now().strftime('%H:%M:%S')}"
                )
            return
        
        # Check rate limit
        if not self.panic_limiter.check(user_id):
            remaining = self.panic_limiter.get_remaining_time(user_id)
            await update.message.reply_text(
                f"⏳ <b>Занадто багато спроб</b>\n\n"
                f"Зачекайте {remaining} секунд перед повторною спробою.",
                parse_mode='HTML'
            )
            return
        
        # Check OTP failure rate limit
        if not self.otp_failure_limiter.check(user_id):
            remaining = self.otp_failure_limiter.get_remaining_time(user_id)
            await update.message.reply_text(
                f"🔒 <b>Акаунт тимчасово заблоковано</b>\n\n"
                f"Занадто багато невірних OTP кодів.\n"
                f"Зачекайте {remaining // 60} хвилин.",
                parse_mode='HTML'
            )
            logger.warning(f"🔒 [TG] User {user_id} blocked due to OTP failures")
            return
        
        # Get OTP code from command arguments
        args = context.args
        
        if not args:
            await update.message.reply_text(
                "🔐 <b>ПОТРІБЕН OTP КОД</b>\n\n"
                "Використання: /panic_close_all &lt;OTP_CODE&gt;\n\n"
                "Приклад: <code>/panic_close_all 123456</code>\n\n"
                "Отримайте код з вашого Authenticator (Google Authenticator, Authy тощо).",
                parse_mode='HTML'
            )
            return
        
        otp_code = args[0]
        
        # Verify OTP
        if not self.otp_verifier:
            await update.message.reply_text(
                "❌ <b>OTP не налаштовано</b>\n\n"
                "Зверніться до адміністратора для налаштування 2FA.",
                parse_mode='HTML'
            )
            return
        
        if not self.otp_verifier.verify(otp_code):
            await update.message.reply_text(
                "❌ <b>НЕВІРНИЙ OTP КОД</b>\n\n"
                "Перевірте код у вашому Authenticator і спробуйте знову.\n\n"
                "<i>Переконайтеся, що час на вашому пристрої синхронізовано.</i>",
                parse_mode='HTML'
            )
            logger.warning(f"❌ [TG] Invalid OTP from user {user_id}")
            # Record failure
            self.otp_failure_limiter.check(user_id)
            return
        
        # OTP verified - execute panic close
        logger.critical(f"🚨🚨🚨 [TG] PANIC CLOSE AUTHORIZED by {user.username} (ID: {user_id})")
        
        await update.message.reply_text(
            "🚨 <b>PANIC CLOSE ПІДТВЕРДЖЕНО</b>\n\n"
            "⏳ Закриття всіх позицій...",
            parse_mode='HTML'
        )
        
        # Execute panic callback
        results = None
        try:
            if self.panic_callback:
                results = self.panic_callback()
                
                result_msg = f"""
🚨🚨🚨 <b>ГЛОБАЛЬНЕ АВАРІЙНЕ ЗАКРИТТЯ ВИКОНАНО</b> 🚨🚨🚨

📊 <b>Master:</b> {results.get('master_closed', 0)} позицій закрито
👥 <b>Slaves:</b> {results.get('slaves_closed', 0)} акаунтів оброблено

👤 <b>Виконано:</b> @{user.username}
⏰ <b>Час:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                if results.get('errors'):
                    result_msg += f"\n⚠️ <b>Помилки:</b>\n" + "\n".join(results['errors'][:5])
                
                await update.message.reply_text(result_msg.strip(), parse_mode='HTML')
                
                # Notify admin chat
                if self.admin_chat_id:
                    await self._notify_admin(result_msg)
            else:
                await update.message.reply_text(
                    "⚠️ <b>Panic callback не налаштовано</b>\n\n"
                    "Зверніться до адміністратора.",
                    parse_mode='HTML'
                )
                
        except Exception as e:
            error_msg = f"""
❌ <b>ПОМИЛКА ПРИ PANIC CLOSE</b>

{str(e)[:200]}

👤 <b>Ініціатор:</b> @{user.username}
⏰ <b>Час:</b> {datetime.now().strftime('%H:%M:%S')}
"""
            await update.message.reply_text(error_msg.strip(), parse_mode='HTML')
            logger.error(f"Panic close error: {e}")
            
            if self.admin_chat_id:
                await self._notify_admin(error_msg)
    
    async def _cmd_otp_setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /otp_setup command - Show OTP setup info"""
        user = update.effective_user
        
        if not self._is_authorized(user.id):
            await update.message.reply_text(
                "⛔ Ця команда доступна лише авторизованим користувачам.",
                parse_mode='HTML'
            )
            return
        
        if not self.otp_verifier or not self.otp_verifier.totp:
            await update.message.reply_text(
                "❌ OTP не налаштовано в системі.\n\n"
                "Зверніться до адміністратора.",
                parse_mode='HTML'
            )
            return
        
        uri = self.otp_verifier.get_provisioning_uri()
        
        setup_msg = f"""
🔐 <b>OTP Налаштування</b>

Щоб налаштувати OTP у вашому Authenticator:

1. Відкрийте Google Authenticator / Authy
2. Натисніть "+" → "Ввести ключ вручну"
3. Ім'я: <code>MIMIC/BrainCapital</code>
4. Ключ: <i>(зверніться до адміністратора)</i>

Або скануйте QR-код з URI:
<code>{uri}</code>

⚠️ <b>УВАГА:</b> Ніколи не діліться цим URI з іншими!
"""
        await update.message.reply_text(setup_msg.strip(), parse_mode='HTML')
    
    async def _cmd_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands"""
        await update.message.reply_text(
            "❓ Невідома команда.\n\nВведіть /help для списку команд.",
            parse_mode='HTML'
        )
    
    async def _notify_admin(self, message: str):
        """Send notification to admin chat"""
        if self.admin_chat_id and self.bot:
            try:
                await self.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=message,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")
    
    def start(self):
        """Start the bot in a background thread"""
        if not TELEGRAM_BOT_AVAILABLE:
            logger.warning("Cannot start bot - telegram dependencies not available")
            return
        
        if not self.bot_token:
            logger.warning("Cannot start bot - no bot token provided")
            return
        
        if self._running:
            logger.warning("Bot is already running")
            return
        
        # Get startup delay from config (default 30 seconds to prevent 409 conflicts on restart)
        # Increased from 15s to 30s for more reliable conflict avoidance
        try:
            from config import Config
            startup_delay = getattr(Config, 'TG_POLLING_STARTUP_DELAY', 30)
        except:
            startup_delay = 30
        
        def run_bot_multiprocess():
            """
            Run the bot in a separate process to completely isolate from eventlet.
            This is necessary because eventlet monkey-patches asyncio globally.
            Uses multiprocessing.Process with spawn context for clean isolation.
            """
            import multiprocessing
            import signal
            import atexit
            
            # Use 'spawn' context to get a completely fresh Python interpreter
            # This ensures eventlet's patches are NOT inherited
            ctx = multiprocessing.get_context('spawn')
            
            logger.info("🤖 Starting Telegram bot in separate process (spawn)...")
            
            try:
                # Start the bot in a completely separate process
                # Uses module-level function _telegram_bot_process_main which is picklable
                process = ctx.Process(
                    target=_telegram_bot_process_main,
                    args=(
                        self.bot_token,
                        self.admin_chat_id or '',
                        list(self.authorized_users) if self.authorized_users else [],
                        self.otp_verifier.secret if self.otp_verifier else '',
                        startup_delay  # Pass startup delay to subprocess
                    ),
                    daemon=False,  # Don't use daemon - we'll manage cleanup ourselves
                    name="TelegramBotProcess"
                )
                process.start()
                self._bot_process = process
                
                logger.info(f"🤖 Telegram bot process started (PID: {process.pid})")
                
                # Register cleanup function to terminate subprocess on exit
                def cleanup_subprocess():
                    if process.is_alive():
                        logger.info(f"🤖 Terminating Telegram bot subprocess (PID: {process.pid})...")
                        process.terminate()
                        process.join(timeout=5)
                        if process.is_alive():
                            logger.warning("🤖 Subprocess didn't terminate, killing...")
                            process.kill()
                            process.join(timeout=2)
                
                atexit.register(cleanup_subprocess)
                
                # Wait for the process (it runs until stopped)
                process.join()
                
            except Exception as e:
                logger.error(f"Bot process error: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
        
        def run_bot_async():
            """
            Run the bot using asyncio directly.
            Works when NOT running under eventlet.
            """
            import asyncio
            
            # Create a brand new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def _start_bot():
                """Initialize and start the bot"""
                logger.info("🤖 Creating Telegram bot application...")
                
                # Create the Application in this thread
                self.application = Application.builder().token(self.bot_token).build()
                self.bot = self.application.bot
                
                # Add command handlers
                self.application.add_handler(CommandHandler("start", self._cmd_start))
                self.application.add_handler(CommandHandler("help", self._cmd_help))
                self.application.add_handler(CommandHandler("status", self._cmd_status))
                self.application.add_handler(CommandHandler("support", self._cmd_support))
                self.application.add_handler(CommandHandler("ask", self._cmd_support))
                self.application.add_handler(CommandHandler("panic_close_all", self._cmd_panic_close_all))
                self.application.add_handler(CommandHandler("panic", self._cmd_panic_close_all))
                self.application.add_handler(CommandHandler("otp_setup", self._cmd_otp_setup))
                self.application.add_handler(MessageHandler(filters.COMMAND, self._cmd_unknown))
                
                logger.info("🤖 Starting Telegram bot polling...")
                
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=['message', 'callback_query']
                )
                
                logger.info("🤖 Telegram bot is now running")
            
            async def _stop_bot():
                """Stop the bot gracefully"""
                try:
                    if self.application:
                        if self.application.updater and self.application.updater.running:
                            await self.application.updater.stop()
                        if self.application.running:
                            await self.application.stop()
                        await self.application.shutdown()
                except Exception as e:
                    logger.debug(f"Bot cleanup error: {e}")
            
            try:
                loop.run_until_complete(_start_bot())
                loop.run_forever()
            except Exception as e:
                logger.error(f"Bot error: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
            finally:
                try:
                    loop.run_until_complete(_stop_bot())
                except:
                    pass
                try:
                    loop.close()
                except:
                    pass
        
        # Check if eventlet is monkey-patching (causes asyncio issues)
        self._running = True
        self._bot_process = None
        
        try:
            import eventlet
            eventlet_active = eventlet.patcher.is_monkey_patched('socket')
        except ImportError:
            eventlet_active = False
        
        if eventlet_active:
            # Eventlet is active - use multiprocessing with 'spawn' for complete isolation
            logger.info("🤖 Eventlet detected - starting Telegram bot in isolated process")
            bot_thread = threading.Thread(target=run_bot_multiprocess, daemon=True, name="TelegramBotLauncher")
        else:
            # No eventlet - use regular asyncio thread
            logger.info("🤖 Starting Telegram bot in async thread")
            bot_thread = threading.Thread(target=run_bot_async, daemon=True, name="TelegramBot")
        
        bot_thread.start()
        logger.info("🤖 Telegram bot started")
    
    def stop(self):
        """Stop the bot gracefully"""
        if not self._running:
            return
        
        self._running = False
        logger.info("🤖 Stopping Telegram bot...")
        
        # If running as subprocess, terminate it with proper signal handling
        if hasattr(self, '_bot_process') and self._bot_process:
            try:
                if self._bot_process.is_alive():
                    # Send SIGTERM first for graceful shutdown
                    self._bot_process.terminate()
                    
                    # Wait for graceful shutdown (up to 10 seconds)
                    self._bot_process.join(timeout=10)
                    
                    if self._bot_process.is_alive():
                        # Force kill if graceful shutdown failed
                        logger.warning("🤖 Subprocess didn't terminate gracefully, killing...")
                        self._bot_process.kill()
                        self._bot_process.join(timeout=3)
                    
                    logger.info("🤖 Telegram bot subprocess stopped")
                else:
                    logger.info("🤖 Telegram bot subprocess already stopped")
            except Exception as e:
                logger.debug(f"Subprocess stop error: {e}")
                try:
                    self._bot_process.kill()
                except:
                    pass
            return
        
        # If running as async application, try to stop it
        if self.application:
            try:
                import asyncio
                
                async def shutdown():
                    try:
                        if self.application.updater and self.application.updater.running:
                            await self.application.updater.stop()
                        if self.application.running:
                            await self.application.stop()
                        await self.application.shutdown()
                    except Exception as e:
                        logger.debug(f"Shutdown error: {e}")
                
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(shutdown())
                except RuntimeError:
                    try:
                        asyncio.run(shutdown())
                    except:
                        pass
                
                logger.info("🤖 Telegram bot stopped")
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")


# Global instance
_bot_handler: Optional[TelegramBotHandler] = None


def init_telegram_bot(
    bot_token: str,
    otp_secret: str,
    authorized_users: list,
    panic_callback: Callable = None,
    admin_chat_id: str = None
) -> Optional[TelegramBotHandler]:
    """
    Initialize and start the Telegram bot handler.
    
    Args:
        bot_token: Telegram bot token
        otp_secret: TOTP secret for 2FA (optional - panic commands disabled without it)
        authorized_users: List of authorized Telegram user IDs
        panic_callback: Function to call for panic close
        admin_chat_id: Chat ID for admin notifications
        
    Returns:
        TelegramBotHandler instance or None if initialization fails
    """
    global _bot_handler
    
    # Debug logging for troubleshooting
    logger.info("🔍 Telegram Bot Initialization Debug:")
    logger.info(f"   - python-telegram-bot available: {TELEGRAM_BOT_AVAILABLE}")
    logger.info(f"   - pyotp available: {PYOTP_AVAILABLE}")
    logger.info(f"   - bot_token provided: {bool(bot_token)}")
    if bot_token:
        # Show first 10 chars of token for debug (safe to show)
        logger.info(f"   - bot_token prefix: {bot_token[:10]}...")
    logger.info(f"   - otp_secret provided: {bool(otp_secret)}")
    logger.info(f"   - authorized_users: {authorized_users}")
    logger.info(f"   - admin_chat_id: {admin_chat_id}")
    
    if not TELEGRAM_BOT_AVAILABLE:
        logger.error("❌ Telegram bot dependencies not available!")
        logger.error("   Install with: pip install python-telegram-bot[ext]")
        return None
    
    if not bot_token:
        logger.warning("⚠️ No bot token provided - Telegram bot disabled")
        logger.warning("   Set TELEGRAM_BOT_TOKEN in .env or bot_token in config.ini")
        return None
    
    # Validate token format (should be like 123456789:ABCdefGHI...)
    if ':' not in bot_token or len(bot_token) < 30:
        logger.error(f"❌ Invalid bot token format!")
        logger.error("   Token should look like: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ...")
        logger.error("   Get your token from @BotFather on Telegram")
        return None
    
    try:
        _bot_handler = TelegramBotHandler(
            bot_token=bot_token,
            otp_secret=otp_secret or '',
            authorized_users=authorized_users or [],
            panic_callback=panic_callback,
            admin_chat_id=admin_chat_id or ''
        )
        
        # Check if polling should be disabled (e.g., when another instance is running)
        from config import Config
        disable_polling = getattr(Config, 'TG_DISABLE_POLLING', False)
        
        if disable_polling:
            logger.info("ℹ️ Telegram Bot polling DISABLED (disable_polling=True in config)")
            logger.info("   Notifications will still be sent, but commands won't work")
        else:
            _bot_handler.start()
            
            if otp_secret and authorized_users:
                logger.info("✅ Telegram Bot started with panic commands enabled")
            else:
                logger.info("✅ Telegram Bot started (basic commands only)")
                if not otp_secret:
                    logger.info("   ℹ️ Set PANIC_OTP_SECRET to enable panic commands")
        
        return _bot_handler
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Telegram bot: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return None


def get_telegram_bot() -> Optional[TelegramBotHandler]:
    """Get the global Telegram bot handler instance"""
    return _bot_handler


def generate_otp_secret() -> str:
    """
    Generate a new TOTP secret for OTP setup.
    
    Returns:
        Base32-encoded secret string (32 characters)
    """
    if not PYOTP_AVAILABLE:
        raise ImportError("pyotp is required. Install with: pip install pyotp")
    
    return pyotp.random_base32()


def diagnose_telegram_conflict(bot_token: str) -> dict:
    """
    Diagnose 409 Conflict issues by testing Telegram API directly.
    
    This function makes a series of getUpdates calls to determine if
    another bot instance is actively polling.
    
    Args:
        bot_token: Telegram bot token to test
        
    Returns:
        dict with diagnosis results:
        - has_conflict: bool - True if another instance is polling
        - bot_info: dict - Bot username, ID if available
        - recommendation: str - What to do next
        - details: str - Technical details
    """
    import requests
    import time
    
    result = {
        'has_conflict': False,
        'bot_info': {},
        'recommendation': '',
        'details': '',
        'checks': []
    }
    
    base_url = f"https://api.telegram.org/bot{bot_token}"
    
    # 1. Get bot info
    try:
        resp = requests.get(f"{base_url}/getMe", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                result['bot_info'] = {
                    'username': data['result'].get('username'),
                    'id': data['result'].get('id'),
                    'first_name': data['result'].get('first_name')
                }
                result['checks'].append(f"✅ Bot valid: @{data['result'].get('username')}")
        else:
            result['checks'].append(f"❌ Bot token invalid: {resp.status_code}")
            result['recommendation'] = "Check your bot token with @BotFather"
            return result
    except Exception as e:
        result['checks'].append(f"❌ Could not connect: {e}")
        result['recommendation'] = "Check network connectivity"
        return result
    
    # 2. Delete webhook first (in case it's set)
    try:
        resp = requests.post(f"{base_url}/deleteWebhook", timeout=10)
        if resp.status_code == 200:
            result['checks'].append("✅ Webhook deleted/not set")
    except Exception as e:
        result['checks'].append(f"⚠️ Webhook check failed: {e}")
    
    # 3. Make multiple rapid getUpdates calls to detect conflicts
    conflict_count = 0
    success_count = 0
    
    for i in range(5):
        try:
            resp = requests.post(
                f"{base_url}/getUpdates",
                json={"limit": 1, "timeout": 0},
                timeout=10
            )
            
            if resp.status_code == 200:
                success_count += 1
                result['checks'].append(f"✅ Poll #{i+1}: OK")
            elif resp.status_code == 409:
                conflict_count += 1
                result['checks'].append(f"❌ Poll #{i+1}: 409 CONFLICT!")
            else:
                result['checks'].append(f"⚠️ Poll #{i+1}: {resp.status_code}")
            
            time.sleep(0.5)  # Small delay between checks
            
        except Exception as e:
            result['checks'].append(f"❌ Poll #{i+1} error: {e}")
    
    # 4. Analyze results
    if conflict_count > 0:
        result['has_conflict'] = True
        result['details'] = f"Detected {conflict_count} conflicts out of 5 polling attempts"
        result['recommendation'] = """
ANOTHER BOT INSTANCE IS ACTIVELY POLLING!

To fix this:
1. Find and stop the other instance:
   - Check other servers/VPS using same token
   - Check developer machines running the bot
   - Check Docker containers: docker ps | grep mimic
   - Check screen/tmux sessions: screen -ls
   
2. On this server, run:
   pkill -f "telegram_bot"
   pkill -f "python.*mimic"
   rm -f /tmp/mimic_telegram_bot.lock
   
3. If you can't find the other instance:
   - Go to @BotFather on Telegram
   - Send /mybots
   - Select your bot
   - Choose "API Token" → "Revoke token"
   - Update your .env with the new token
   
4. Then restart:
   sudo systemctl restart mimic
"""
    else:
        result['has_conflict'] = False
        result['details'] = f"No conflicts detected ({success_count}/5 successful polls)"
        result['recommendation'] = "Bot token is clear. You can start the bot now."
    
    return result


def print_conflict_diagnosis(bot_token: str = None):
    """
    Print a formatted conflict diagnosis to console.
    
    Usage from command line:
        python -c "from telegram_bot import print_conflict_diagnosis; print_conflict_diagnosis()"
    
    Or with specific token:
        python -c "from telegram_bot import print_conflict_diagnosis; print_conflict_diagnosis('your-token')"
    """
    if not bot_token:
        try:
            from config import Config
            bot_token = getattr(Config, 'TG_TOKEN', None)
        except ImportError:
            print("❌ Could not load config. Please provide bot token as argument.")
            return
    
    if not bot_token:
        print("❌ No bot token configured. Check TG_TOKEN in .env")
        return
    
    print("\n" + "=" * 60)
    print("🔍 TELEGRAM BOT CONFLICT DIAGNOSIS")
    print("=" * 60 + "\n")
    
    result = diagnose_telegram_conflict(bot_token)
    
    # Print bot info
    if result['bot_info']:
        print(f"🤖 Bot: @{result['bot_info'].get('username', 'unknown')}")
        print(f"   ID: {result['bot_info'].get('id', 'unknown')}\n")
    
    # Print checks
    print("Checks:")
    for check in result['checks']:
        print(f"  {check}")
    print()
    
    # Print result
    if result['has_conflict']:
        print("❌ CONFLICT DETECTED!")
        print(f"   {result['details']}")
    else:
        print("✅ NO CONFLICT DETECTED")
        print(f"   {result['details']}")
    
    # Print recommendation
    print("\n" + "-" * 60)
    print("RECOMMENDATION:")
    print("-" * 60)
    print(result['recommendation'])
    print("=" * 60 + "\n")

