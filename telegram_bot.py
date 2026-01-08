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
        
        try:
            self._setup_bot()
            logger.info("✅ Telegram Bot Handler initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram bot: {e}")
    
    def _setup_bot(self):
        """Set up the bot application with command handlers"""
        self.application = Application.builder().token(self.bot_token).build()
        self.bot = self.application.bot
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(CommandHandler("panic_close_all", self._cmd_panic_close_all))
        self.application.add_handler(CommandHandler("panic", self._cmd_panic_close_all))  # Alias
        self.application.add_handler(CommandHandler("otp_setup", self._cmd_otp_setup))
        
        # Handle unknown commands
        self.application.add_handler(MessageHandler(filters.COMMAND, self._cmd_unknown))
    
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
        if not self.application:
            logger.warning("Cannot start bot - not initialized")
            return
        
        if self._running:
            logger.warning("Bot is already running")
            return
        
        def run_bot():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                self._running = True
                logger.info("🤖 Starting Telegram bot polling...")
                loop.run_until_complete(self.application.initialize())
                loop.run_until_complete(self.application.start())
                loop.run_until_complete(self.application.updater.start_polling())
                loop.run_forever()
            except Exception as e:
                logger.error(f"Bot error: {e}")
            finally:
                self._running = False
        
        bot_thread = threading.Thread(target=run_bot, daemon=True, name="TelegramBot")
        bot_thread.start()
        logger.info("🤖 Telegram bot started in background thread")
    
    def stop(self):
        """Stop the bot"""
        if self.application and self._running:
            import asyncio
            
            async def shutdown():
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(shutdown())
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")
            
            self._running = False
            logger.info("🤖 Telegram bot stopped")


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
        otp_secret: TOTP secret for 2FA
        authorized_users: List of authorized Telegram user IDs
        panic_callback: Function to call for panic close
        admin_chat_id: Chat ID for admin notifications
        
    Returns:
        TelegramBotHandler instance or None if initialization fails
    """
    global _bot_handler
    
    if not TELEGRAM_BOT_AVAILABLE:
        logger.error("Telegram bot dependencies not available")
        return None
    
    if not bot_token:
        logger.warning("No bot token provided - Telegram bot disabled")
        return None
    
    try:
        _bot_handler = TelegramBotHandler(
            bot_token=bot_token,
            otp_secret=otp_secret,
            authorized_users=authorized_users,
            panic_callback=panic_callback,
            admin_chat_id=admin_chat_id
        )
        
        _bot_handler.start()
        return _bot_handler
        
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
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

