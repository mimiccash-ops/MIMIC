"""
Telegram Notification System for Brain Capital
Sends trade alerts and system notifications to Telegram
Also includes Email sending functionality for password recovery
"""

import logging
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from queue import Queue
from datetime import datetime

logger = logging.getLogger("TelegramNotifier")

# Try to import telegram, handle gracefully if not installed
try:
    import telegram
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("⚠️ python-telegram-bot not installed. Telegram notifications disabled.")


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled and TELEGRAM_AVAILABLE and bot_token and chat_id
        self.bot = None
        self.message_queue = Queue()
        
        if self.enabled:
            try:
                self.bot = telegram.Bot(token=bot_token)
                # Start message sender thread
                self._sender_thread = threading.Thread(target=self._send_loop, daemon=True)
                self._sender_thread.start()
                logger.info("✅ Telegram Notifier initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Telegram bot: {e}")
                self.enabled = False
        else:
            logger.info("ℹ️ Telegram notifications disabled")

    def _send_loop(self):
        """Background thread for sending messages"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while True:
            try:
                item = self.message_queue.get()
                if item:
                    # Handle both old string format and new dict format
                    if isinstance(item, dict):
                        message = item.get('message', '')
                        chat_id = item.get('chat_id')
                    else:
                        message = item
                        chat_id = None
                    loop.run_until_complete(self._async_send(message, chat_id))
            except Exception as e:
                logger.error(f"Telegram send error: {e}")

    async def _async_send(self, message: str, chat_id: str = None):
        """Async message sender"""
        if self.bot:
            try:
                target_chat = chat_id or self.chat_id
                await self.bot.send_message(
                    chat_id=target_chat,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Telegram send failed to {chat_id}: {e}")

    def send(self, message: str, chat_id: str = None):
        """Queue a message for sending"""
        if self.enabled or chat_id:  # Allow sending to specific chat even if main notifications disabled
            self.message_queue.put({'message': message, 'chat_id': chat_id})

    def send_sync(self, message: str, chat_id: str) -> tuple[bool, str]:
        """
        Send a message synchronously using direct HTTP request.
        Returns (success: bool, error_message: str)
        Used for testing connections and sending critical messages that need confirmation.
        """
        if not self.bot_token:
            return False, "Telegram bot not initialized"
        
        if not chat_id:
            return False, "No chat ID provided"
        
        import requests
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("ok"):
                return True, ""
            else:
                error_desc = result.get("description", "Unknown error")
                if "chat not found" in error_desc.lower():
                    return False, "chat_not_found"
                elif "bot was blocked" in error_desc.lower():
                    return False, "bot_blocked"
                elif "user is deactivated" in error_desc.lower():
                    return False, "user_deactivated"
                else:
                    return False, error_desc
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, str(e)

    def test_connection(self, chat_id: str, username: str = "") -> tuple[bool, str]:
        """
        Test connection to a user's Telegram chat by sending a welcome message.
        Returns (success: bool, error_code: str)
        """
        welcome_msg = f"""
✅ <b>TELEGRAM ПІДКЛЮЧЕНО!</b>

👋 Вітаємо{', <b>' + username + '</b>' if username else ''}!

Ваш Telegram успішно підключено до <b>Brain Capital</b>.

Тепер ви будете отримувати:
• 🔔 Сповіщення про торгівлю
• 🔐 Коди відновлення паролю
• 📊 Важливі системні повідомлення

<i>Якщо ви не підключали Telegram — проігноруйте це повідомлення.</i>
"""
        return self.send_sync(welcome_msg.strip(), chat_id)

    def get_bot_username(self) -> str:
        """Get the bot's username using direct HTTP request"""
        if not self.bot_token:
            return ""
        
        # Cache the username to avoid repeated API calls
        if hasattr(self, '_cached_bot_username'):
            return self._cached_bot_username
        
        import requests
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)
            result = response.json()
            
            if result.get("ok"):
                username = result.get("result", {}).get("username", "")
                self._cached_bot_username = username
                return username
            return ""
        except Exception as e:
            logger.error(f"Failed to get bot username: {e}")
            return ""

    # ==================== FORMATTED MESSAGES ====================

    def notify_signal_received(self, symbol: str, action: str, risk: float, leverage: int):
        """Notify about incoming trading signal"""
        emoji = "🟢" if action == "long" else "🔴" if action == "short" else "⚪"
        msg = f"""
{emoji} <b>НОВИЙ СИГНАЛ</b>

📊 <b>Пара:</b> <code>{symbol}</code>
📈 <b>Дія:</b> <code>{action.upper()}</code>
⚠️ <b>Ризик:</b> <code>{risk}%</code>
🔧 <b>Плече:</b> <code>x{leverage}</code>
⏰ <b>Час:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>
"""
        self.send(msg.strip())

    def notify_trade_opened(self, node_name: str, symbol: str, side: str, qty: float, price: float):
        """Notify about opened trade"""
        emoji = "🟢" if side == "LONG" else "🔴"
        msg = f"""
{emoji} <b>УГОДУ ВІДКРИТО</b>

👤 <b>Вузол:</b> <code>{node_name}</code>
📊 <b>Пара:</b> <code>{symbol}</code>
📈 <b>Сторона:</b> <code>{side}</code>
📦 <b>Кількість:</b> <code>{qty:.4f}</code>
💰 <b>Ціна входу:</b> <code>${price:.4f}</code>
"""
        self.send(msg.strip())

    def notify_trade_closed(self, node_name: str, symbol: str, side: str, pnl: float, roi: float):
        """Notify about closed trade"""
        emoji = "💰" if pnl >= 0 else "💸"
        pnl_emoji = "+" if pnl >= 0 else ""
        msg = f"""
{emoji} <b>УГОДУ ЗАКРИТО</b>

👤 <b>Вузол:</b> <code>{node_name}</code>
📊 <b>Пара:</b> <code>{symbol}</code>
📈 <b>Сторона:</b> <code>{side}</code>
💵 <b>PnL:</b> <code>{pnl_emoji}{pnl:.2f} USDT</code>
📊 <b>ROI:</b> <code>{pnl_emoji}{roi:.2f}%</code>
"""
        self.send(msg.strip())

    def notify_error(self, node_name: str, symbol: str, error: str):
        """Notify about trade error"""
        msg = f"""
⚠️ <b>ПОМИЛКА ТОРГІВЛІ</b>

👤 <b>Вузол:</b> <code>{node_name}</code>
📊 <b>Пара:</b> <code>{symbol}</code>
❌ <b>Помилка:</b> <code>{error}</code>
⏰ <b>Час:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>
"""
        self.send(msg.strip())

    def notify_system_event(self, event: str, details: str = ""):
        """Notify about system events"""
        msg = f"""
🔔 <b>СИСТЕМНА ПОДІЯ</b>

📋 <b>Подія:</b> <code>{event}</code>
{"📝 <b>Деталі:</b> <code>" + details + "</code>" if details else ""}
⏰ <b>Час:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>
"""
        self.send(msg.strip())

    def notify_panic_close(self, node_name: str, positions_closed: int):
        """Notify about panic close"""
        msg = f"""
🚨 <b>АВАРІЙНЕ ЗАКРИТТЯ</b>

👤 <b>Вузол:</b> <code>{node_name}</code>
📊 <b>Закрито позицій:</b> <code>{positions_closed}</code>
⏰ <b>Час:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>
"""
        self.send(msg.strip())

    def notify_global_panic(self, master_closed: int, slaves_count: int):
        """Notify about global panic close (all accounts)"""
        msg = f"""
🚨🚨🚨 <b>ГЛОБАЛЬНЕ АВАРІЙНЕ ЗАКРИТТЯ</b> 🚨🚨🚨

📊 <b>Master закрито:</b> <code>{master_closed}</code> позицій
👥 <b>Slaves оброблено:</b> <code>{slaves_count}</code> акаунтів
⏰ <b>Час:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>

⚠️ Всі позиції та ордери закрито!
"""
        self.send(msg.strip())

    # ==================== USER-SPECIFIC NOTIFICATIONS ====================

    def notify_user_trade_opened(self, user_chat_id: str, symbol: str, side: str, qty: float, price: float):
        """Notify specific user about their opened trade"""
        if not user_chat_id:
            return
        emoji = "🟢" if side == "LONG" else "🔴"
        msg = f"""
{emoji} <b>ВАШУ УГОДУ ВІДКРИТО</b>

📊 <b>Пара:</b> <code>{symbol}</code>
📈 <b>Сторона:</b> <code>{side}</code>
📦 <b>Кількість:</b> <code>{qty:.4f}</code>
💰 <b>Ціна входу:</b> <code>${price:.4f}</code>
⏰ <b>Час:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>
"""
        self.send(msg.strip(), chat_id=user_chat_id)

    def notify_user_trade_closed(self, user_chat_id: str, symbol: str, side: str, pnl: float, roi: float):
        """Notify specific user about their closed trade"""
        if not user_chat_id:
            return
        emoji = "💰" if pnl >= 0 else "💸"
        pnl_emoji = "+" if pnl >= 0 else ""
        msg = f"""
{emoji} <b>ВАШУ УГОДУ ЗАКРИТО</b>

📊 <b>Пара:</b> <code>{symbol}</code>
📈 <b>Сторона:</b> <code>{side}</code>
💵 <b>PnL:</b> <code>{pnl_emoji}{pnl:.2f} USDT</code>
📊 <b>ROI:</b> <code>{pnl_emoji}{roi:.2f}%</code>
⏰ <b>Час:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>
"""
        self.send(msg.strip(), chat_id=user_chat_id)

    def notify_user_error(self, user_chat_id: str, symbol: str, error: str):
        """Notify specific user about error"""
        if not user_chat_id:
            return
        msg = f"""
⚠️ <b>ПОМИЛКА ТОРГІВЛІ</b>

📊 <b>Пара:</b> <code>{symbol}</code>
❌ <b>Помилка:</b> <code>{error}</code>
⏰ <b>Час:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>
"""
        self.send(msg.strip(), chat_id=user_chat_id)


    # ==================== PASSWORD RESET NOTIFICATIONS ====================

    def send_password_reset_code(self, user_chat_id: str, code: str, username: str):
        """Надіслати код відновлення паролю користувачу через Telegram"""
        if not user_chat_id:
            return False
        msg = f"""
🔐 <b>ВІДНОВЛЕННЯ ПАРОЛЮ</b>

Ви запросили відновлення паролю для акаунту <b>{username}</b>.

Ваш код підтвердження:
<code>{code}</code>

⏰ Код дійсний протягом 15 хвилин.

⚠️ Якщо ви не запитували відновлення паролю, проігноруйте це повідомлення.
"""
        self.send(msg.strip(), chat_id=user_chat_id)
        return True

    # ==================== SUBSCRIPTION NOTIFICATIONS ====================

    def notify_subscription_expiring(self, user_chat_id: str, username: str, days_remaining: int, plan: str):
        """Notify user that their subscription is about to expire"""
        if not user_chat_id:
            return False
        
        emoji = "⏰" if days_remaining > 1 else "🚨"
        urgency = "скоро закінчується" if days_remaining > 1 else "закінчується сьогодні"
        
        msg = f"""
{emoji} <b>ПІДПИСКА {urgency.upper()}!</b>

👤 <b>Користувач:</b> <code>{username}</code>
📦 <b>План:</b> <code>{plan.upper()}</code>
⏳ <b>Залишилось днів:</b> <code>{days_remaining}</code>

💡 Продовжіть підписку, щоб продовжити торгівлю.

🔗 Перейдіть до налаштувань для оплати.
"""
        self.send(msg.strip(), chat_id=user_chat_id)
        return True

    def notify_subscription_expired(self, user_chat_id: str, username: str, plan: str):
        """Notify user that their subscription has expired"""
        if not user_chat_id:
            return False
        
        msg = f"""
🔴 <b>ПІДПИСКУ ЗАКІНЧЕНО!</b>

👤 <b>Користувач:</b> <code>{username}</code>
📦 <b>План:</b> <code>{plan.upper()}</code>

⚠️ Ваша підписка закінчилася.
Торгівля призупинена до поновлення підписки.

💳 Поновіть підписку, щоб продовжити торгівлю:
🔗 Перейдіть до налаштувань -> Підписка

Дякуємо, що користуєтесь Brain Capital!
"""
        self.send(msg.strip(), chat_id=user_chat_id)
        return True

    def notify_subscription_activated(self, user_chat_id: str, username: str, plan: str, days: int, expires_at: str):
        """Notify user that their subscription has been activated"""
        if not user_chat_id:
            return False
        
        msg = f"""
💎 <b>ПІДПИСКУ АКТИВОВАНО!</b>

👤 <b>Користувач:</b> <code>{username}</code>
✅ <b>План:</b> <code>{plan.upper()}</code>
📅 <b>Днів:</b> <code>{days}</code>
🗓 <b>Активна до:</b> <code>{expires_at}</code>

🚀 Торгівля увімкнена! Бажаємо успішних трейдів!

💡 Підказка: Налаштуйте свої параметри ризику в налаштуваннях.
"""
        self.send(msg.strip(), chat_id=user_chat_id)
        return True


class EmailSender:
    """Клас для відправки Email повідомлень"""
    
    def __init__(self, smtp_server: str, smtp_port: int, username: str, 
                 password: str, from_email: str, from_name: str = "Brain Capital", enabled: bool = True):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.enabled = enabled and all([smtp_server, username, password, from_email])
        
        if self.enabled:
            logger.info("✅ Email Sender initialized")
        else:
            logger.info("ℹ️ Email sending disabled or not configured")
    
    def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """Надіслати Email"""
        if not self.enabled:
            logger.warning("Email sending is disabled")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Додаємо текстову версію
            if text_content:
                msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            
            # Додаємо HTML версію
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # Відправляємо через SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_email, to_email, msg.as_string())
            
            logger.info(f"✅ Email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            return False
    
    def send_password_reset_code(self, to_email: str, code: str, username: str) -> bool:
        """Надіслати код відновлення паролю на Email"""
        subject = "🔐 Brain Capital - Відновлення паролю"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0a0a12;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 500px;
            margin: 0 auto;
            background: linear-gradient(165deg, rgba(12, 12, 24, 0.98), rgba(20, 20, 40, 0.95));
            border-radius: 16px;
            border: 1px solid rgba(0, 245, 255, 0.3);
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(0, 245, 255, 0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            font-size: 28px;
            font-weight: bold;
            background: linear-gradient(135deg, #00f5ff, #ff00ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        .title {{
            font-size: 18px;
            color: #e8e8f0;
            margin-bottom: 5px;
        }}
        .subtitle {{
            font-size: 14px;
            color: #7a7a98;
        }}
        .code-box {{
            background: rgba(0, 245, 255, 0.1);
            border: 2px solid #00f5ff;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            margin: 30px 0;
        }}
        .code {{
            font-size: 36px;
            font-weight: bold;
            letter-spacing: 8px;
            color: #00f5ff;
            font-family: 'Courier New', monospace;
        }}
        .info {{
            color: #7a7a98;
            font-size: 14px;
            line-height: 1.6;
            margin-top: 20px;
        }}
        .warning {{
            background: rgba(255, 200, 0, 0.1);
            border-left: 3px solid #ffc800;
            padding: 12px 16px;
            margin-top: 20px;
            border-radius: 0 8px 8px 0;
            font-size: 13px;
            color: #ffc800;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            color: #4a4a68;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🧠 BRAIN CAPITAL</div>
            <div class="title">Відновлення паролю</div>
            <div class="subtitle">для акаунту {username}</div>
        </div>
        
        <div class="code-box">
            <p style="color: #7a7a98; margin-bottom: 15px; font-size: 14px;">Ваш код підтвердження:</p>
            <div class="code">{code}</div>
        </div>
        
        <div class="info">
            ⏰ Код дійсний протягом <strong style="color: #00f5ff;">15 хвилин</strong>.<br><br>
            Введіть цей код на сторінці відновлення паролю для встановлення нового паролю.
        </div>
        
        <div class="warning">
            ⚠️ Якщо ви не запитували відновлення паролю, проігноруйте цей лист. Ваш акаунт залишиться в безпеці.
        </div>
        
        <div class="footer">
            © {datetime.now().year} Brain Capital. Всі права захищено.
        </div>
    </div>
</body>
</html>
"""
        
        text_content = f"""
BRAIN CAPITAL - Відновлення паролю

Ви запросили відновлення паролю для акаунту {username}.

Ваш код підтвердження: {code}

Код дійсний протягом 15 хвилин.

Якщо ви не запитували відновлення паролю, проігноруйте цей лист.

© {datetime.now().year} Brain Capital
"""
        
        return self.send_email(to_email, subject, html_content, text_content)


# Global instances (initialized in app.py)
notifier = None
email_sender = None


def init_notifier(bot_token: str, chat_id: str, enabled: bool = True):
    """Initialize global notifier instance"""
    global notifier
    notifier = TelegramNotifier(bot_token, chat_id, enabled)
    return notifier


def init_email_sender(smtp_server: str, smtp_port: int, username: str, 
                      password: str, from_email: str, from_name: str = "Brain Capital", enabled: bool = True):
    """Initialize global email sender instance"""
    global email_sender
    email_sender = EmailSender(smtp_server, smtp_port, username, password, from_email, from_name, enabled)
    return email_sender


def get_notifier() -> TelegramNotifier:
    """Get global notifier instance"""
    return notifier


def get_email_sender() -> EmailSender:
    """Get global email sender instance"""
    return email_sender


# ==================== TELEGRAM LOGGING HANDLER ====================

class TelegramLoggingHandler(logging.Handler):
    """
    Custom logging handler that sends log messages to Telegram.
    
    Features:
    - Batches messages to avoid Telegram rate limits
    - Filters duplicate messages within a time window
    - Categorizes by severity (ERROR, WARNING, CRITICAL)
    - Includes traceback for exceptions
    - Logs to file as backup
    
    Usage:
        handler = TelegramLoggingHandler(notifier, min_level=logging.WARNING)
        logging.getLogger().addHandler(handler)
    """
    
    def __init__(self, telegram_notifier: TelegramNotifier, min_level: int = logging.WARNING,
                 error_log_file: str = None, rate_limit_seconds: int = 5):
        """
        Initialize the Telegram logging handler.
        
        Args:
            telegram_notifier: TelegramNotifier instance for sending messages
            min_level: Minimum logging level to send (default: WARNING)
            error_log_file: Path to error log file (optional, for backup)
            rate_limit_seconds: Minimum seconds between duplicate messages
        """
        super().__init__(level=min_level)
        self.telegram_notifier = telegram_notifier
        self.error_log_file = error_log_file
        self.rate_limit_seconds = rate_limit_seconds
        
        # Rate limiting - track recent messages
        self._recent_messages = {}  # message_hash -> timestamp
        self._lock = threading.Lock()
        
        # Setup file handler if path provided
        self._file_handler = None
        if error_log_file:
            import os
            os.makedirs(os.path.dirname(error_log_file) if os.path.dirname(error_log_file) else '.', exist_ok=True)
            self._file_handler = logging.FileHandler(error_log_file, encoding='utf-8')
            self._file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            ))
    
    def _get_message_hash(self, record: logging.LogRecord) -> str:
        """Create a hash for deduplication"""
        import hashlib
        key = f"{record.name}:{record.levelno}:{record.getMessage()[:100]}"
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    def _should_send(self, record: logging.LogRecord) -> bool:
        """Check if message should be sent (rate limiting)"""
        msg_hash = self._get_message_hash(record)
        now = datetime.now().timestamp()
        
        with self._lock:
            if msg_hash in self._recent_messages:
                last_sent = self._recent_messages[msg_hash]
                if now - last_sent < self.rate_limit_seconds:
                    return False
            
            # Cleanup old entries (older than 60 seconds)
            self._recent_messages = {
                k: v for k, v in self._recent_messages.items()
                if now - v < 60
            }
            
            self._recent_messages[msg_hash] = now
            return True
    
    def _get_level_emoji(self, level: int) -> str:
        """Get emoji for log level"""
        if level >= logging.CRITICAL:
            return "🚨🚨🚨"
        elif level >= logging.ERROR:
            return "❌"
        elif level >= logging.WARNING:
            return "⚠️"
        elif level >= logging.INFO:
            return "ℹ️"
        else:
            return "🔍"
    
    def _get_level_name(self, level: int) -> str:
        """Get display name for log level"""
        if level >= logging.CRITICAL:
            return "CRITICAL"
        elif level >= logging.ERROR:
            return "ERROR"
        elif level >= logging.WARNING:
            return "WARNING"
        elif level >= logging.INFO:
            return "INFO"
        else:
            return "DEBUG"
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record to Telegram and file"""
        try:
            # Always log to file if configured
            if self._file_handler:
                self._file_handler.emit(record)
            
            # Check rate limiting before sending to Telegram
            if not self._should_send(record):
                return
            
            # Don't send if notifier is not available
            if not self.telegram_notifier or not self.telegram_notifier.enabled:
                return
            
            # Format the message
            emoji = self._get_level_emoji(record.levelno)
            level_name = self._get_level_name(record.levelno)
            
            # Get message and truncate if too long
            message = record.getMessage()
            if len(message) > 500:
                message = message[:500] + "..."
            
            # Build Telegram message
            msg = f"""
{emoji} <b>SYSTEM {level_name}</b>

📁 <b>Source:</b> <code>{record.name}</code>
📍 <b>Location:</b> <code>{record.filename}:{record.lineno}</code>
⏰ <b>Time:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>

📝 <b>Message:</b>
<code>{self._escape_html(message)}</code>
"""
            
            # Add traceback if present
            if record.exc_info:
                import traceback
                tb = ''.join(traceback.format_exception(*record.exc_info))
                # Truncate traceback if too long
                if len(tb) > 1000:
                    tb = tb[:1000] + "\n... (truncated)"
                msg += f"\n🔍 <b>Traceback:</b>\n<code>{self._escape_html(tb)}</code>"
            
            # Send to Telegram
            self.telegram_notifier.send(msg.strip())
            
        except Exception as e:
            # Don't raise exceptions in logging handler
            print(f"TelegramLoggingHandler error: {e}")
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))
    
    def close(self):
        """Close the handler"""
        if self._file_handler:
            self._file_handler.close()
        super().close()


def init_telegram_error_logging(
    telegram_notifier: TelegramNotifier,
    min_level: int = logging.WARNING,
    error_log_file: str = "logs/errors.log",
    loggers: list = None
) -> TelegramLoggingHandler:
    """
    Initialize Telegram error logging for the application.
    
    Adds a TelegramLoggingHandler to specified loggers that will:
    - Send all WARNING, ERROR, and CRITICAL messages to Telegram
    - Log all errors to a file for backup
    - Rate-limit duplicate messages
    
    Args:
        telegram_notifier: TelegramNotifier instance
        min_level: Minimum level to log (default: WARNING)
        error_log_file: Path to error log file
        loggers: List of logger names to add handler to (default: root logger + common loggers)
    
    Returns:
        TelegramLoggingHandler instance
    
    Usage:
        from telegram_notifier import init_telegram_error_logging, get_notifier
        handler = init_telegram_error_logging(get_notifier())
    """
    import os
    
    # Create logs directory if needed
    if error_log_file:
        log_dir = os.path.dirname(error_log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    # Create the handler
    handler = TelegramLoggingHandler(
        telegram_notifier=telegram_notifier,
        min_level=min_level,
        error_log_file=error_log_file,
        rate_limit_seconds=10  # Don't send same error more than once per 10 seconds
    )
    
    # Default loggers to add handler to
    if loggers is None:
        loggers = [
            '',  # Root logger
            'BrainCapital',
            'TradingEngine',
            'TelegramNotifier',
            'ARQ.Worker',
            'ARQ.Tasks',
            'werkzeug',
            'flask',
            'sqlalchemy',
        ]
    
    # Add handler to each logger
    for logger_name in loggers:
        log = logging.getLogger(logger_name)
        log.addHandler(handler)
    
    logger.info(f"✅ Telegram error logging initialized (min_level={logging.getLevelName(min_level)}, file={error_log_file})")
    
    return handler


def setup_comprehensive_error_logging(
    telegram_notifier: TelegramNotifier,
    log_dir: str = "logs",
    include_warnings: bool = True
):
    """
    Set up comprehensive error logging with file backup and Telegram notifications.
    
    Creates:
    - logs/errors.log - All errors and warnings (rotated)
    - logs/critical.log - Only critical errors
    - Telegram notifications for all errors
    
    Args:
        telegram_notifier: TelegramNotifier instance
        log_dir: Directory for log files
        include_warnings: Whether to include WARNING level (default: True)
    """
    import os
    from logging.handlers import RotatingFileHandler
    
    os.makedirs(log_dir, exist_ok=True)
    
    # 1. Error log file (rotating, max 10MB, keep 5 backups)
    error_file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.WARNING if include_warnings else logging.ERROR)
    error_file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s'
    ))
    
    # 2. Critical log file (for severe errors only)
    critical_file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'critical.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    critical_file_handler.setLevel(logging.ERROR)
    critical_file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s\n%(exc_info)s'
    ))
    
    # 3. Telegram handler
    telegram_handler = TelegramLoggingHandler(
        telegram_notifier=telegram_notifier,
        min_level=logging.WARNING if include_warnings else logging.ERROR,
        error_log_file=None,  # Already logging to files above
        rate_limit_seconds=10
    )
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(error_file_handler)
    root_logger.addHandler(critical_file_handler)
    root_logger.addHandler(telegram_handler)
    
    # Also add to specific loggers that might not propagate
    for logger_name in ['BrainCapital', 'TradingEngine', 'ARQ.Worker', 'ARQ.Tasks']:
        log = logging.getLogger(logger_name)
        if not any(isinstance(h, TelegramLoggingHandler) for h in log.handlers):
            log.addHandler(telegram_handler)
    
    logger.info(f"✅ Comprehensive error logging configured:")
    logger.info(f"   📁 Error log: {os.path.join(log_dir, 'errors.log')}")
    logger.info(f"   📁 Critical log: {os.path.join(log_dir, 'critical.log')}")
    logger.info(f"   📱 Telegram notifications: {'enabled' if telegram_notifier and telegram_notifier.enabled else 'disabled'}")
    
    return telegram_handler

