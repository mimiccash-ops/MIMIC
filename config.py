"""
Brain Capital Configuration Module

SECURITY HARDENED:
- Master encryption key loaded from Docker Secret or secure file (never simple env vars)
- All sensitive values should be in environment variables
- config.ini should only contain non-sensitive defaults
- Validates critical security parameters on startup
"""

import os
import configparser
from dotenv import load_dotenv
import logging
import secrets
from pathlib import Path

# Налаштування логування для конфігурації
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Config")

# Завантажуємо .env якщо є (для локальної розробки)
load_dotenv()

base_dir = os.path.dirname(os.path.abspath(__file__))
config_ini_path = os.path.join(base_dir, 'config.ini')

if not os.path.exists(config_ini_path):
    logger.critical(f"❌ Файл конфігурації не знайдено: {config_ini_path}")
    raise FileNotFoundError(f"Config file not found: {config_ini_path}")

config = configparser.ConfigParser()
config.read(config_ini_path, encoding='utf-8')


# ==================== SECURE KEY LOADING ====================

def load_secret_from_file(file_path: str) -> str:
    """
    Load a secret from a file path.
    Used for Docker Secrets and secure file-based secret storage.
    
    Args:
        file_path: Path to the secret file
        
    Returns:
        Secret value stripped of whitespace, or empty string if not found
    """
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            secret = path.read_text().strip()
            if secret:
                return secret
    except Exception as e:
        logger.debug(f"Could not read secret from {file_path}: {e}")
    return ""


def load_master_key() -> str:
    """
    Load the master encryption key from secure sources.
    
    SECURITY HIERARCHY (checked in order):
    1. Docker Secret: /run/secrets/brain_capital_master_key
    2. Secure file path: /etc/brain_capital/master.key (outside web root)
    3. Alternative Docker path: /run/secrets/master_key
    4. Local secrets directory: ./secrets/master.key (for development only)
    5. Environment variable: BRAIN_CAPITAL_MASTER_KEY (legacy fallback, logs warning)
    
    Returns:
        The master encryption key
        
    Raises:
        ValueError: If no master key is found
    """
    # Priority 1: Docker Secret (standard location)
    docker_secret_path = "/run/secrets/brain_capital_master_key"
    key = load_secret_from_file(docker_secret_path)
    if key:
        logger.info("🔐 Master key loaded from Docker Secret")
        return key
    
    # Priority 2: Secure system path (outside web root)
    system_secret_path = "/etc/brain_capital/master.key"
    key = load_secret_from_file(system_secret_path)
    if key:
        logger.info("🔐 Master key loaded from secure system path")
        return key
    
    # Priority 3: Alternative Docker secret name
    alt_docker_path = "/run/secrets/master_key"
    key = load_secret_from_file(alt_docker_path)
    if key:
        logger.info("🔐 Master key loaded from Docker Secret (alt)")
        return key
    
    # Priority 4: Local secrets directory (development)
    local_secret_path = os.path.join(base_dir, "secrets", "master.key")
    key = load_secret_from_file(local_secret_path)
    if key:
        logger.warning("⚠️ Master key loaded from local secrets directory (development only!)")
        return key
    
    # Windows development path
    windows_secret_path = os.path.join(base_dir, "secrets", "master.key")
    if os.name == 'nt':  # Windows
        key = load_secret_from_file(windows_secret_path)
        if key:
            logger.warning("⚠️ Master key loaded from local secrets directory (Windows dev)")
            return key
    
    # Priority 5: Environment variable (legacy fallback - logs security warning)
    env_key = os.environ.get('BRAIN_CAPITAL_MASTER_KEY')
    if env_key:
        # Check if this looks like a placeholder
        if env_key.startswith('${') or env_key == 'YOUR_MASTER_KEY_HERE':
            logger.critical("❌ BRAIN_CAPITAL_MASTER_KEY contains a placeholder value!")
            raise ValueError("BRAIN_CAPITAL_MASTER_KEY contains a placeholder - please set actual key")
        
        is_production = os.environ.get('FLASK_ENV', 'development') == 'production'
        if is_production:
            logger.warning("⚠️ SECURITY WARNING: Master key loaded from environment variable!")
            logger.warning("⚠️ For production, use Docker Secrets or secure file storage!")
        else:
            logger.info("🔐 Master key loaded from environment variable (development mode)")
        return env_key
    
    # No key found
    error_msg = """
CRITICAL: Master encryption key not found!

Please configure the key using one of these methods (in order of preference):

1. Docker Secret (recommended for production):
   - Create secret: echo "your-fernet-key" | docker secret create brain_capital_master_key -
   - Mount in docker-compose.yml under 'secrets' section

2. Secure file (for non-Docker deployments):
   - Create: /etc/brain_capital/master.key
   - Set permissions: chmod 600 /etc/brain_capital/master.key

3. Local development:
   - Create: ./secrets/master.key
   - Generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

4. Environment variable (not recommended for production):
   - Set BRAIN_CAPITAL_MASTER_KEY in your .env file
"""
    logger.critical(error_msg)
    raise ValueError("BRAIN_CAPITAL_MASTER_KEY not configured - see logs for setup instructions")


def get_config_value(section: str, key: str, env_var: str = None, default: str = "") -> str:
    """
    Get a config value with environment variable override.
    
    Priority:
    1. Environment variable (if env_var specified)
    2. config.ini value (if not a ${PLACEHOLDER})
    3. default value
    
    Args:
        section: config.ini section name
        key: config.ini key name
        env_var: Optional environment variable name to check first
        default: Default value if nothing found
        
    Returns:
        The configuration value
    """
    # Check environment variable first
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value and not env_value.startswith('${'):
            return env_value
    
    # Check config.ini
    try:
        ini_value = config[section].get(key, '')
        # Skip placeholder values
        if ini_value and not ini_value.startswith('${'):
            return ini_value
    except (KeyError, TypeError):
        pass
    
    return default


class Config:
    # --- FLASK SECURITY ---
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    if not SECRET_KEY:
        error_msg = "CRITICAL: Змінна 'FLASK_SECRET_KEY' відсутня! Встановіть її в файлі .env"
        logger.critical(error_msg)
        raise ValueError(error_msg)
    
    # --- DATABASE (PostgreSQL / SQLite) ---
    # OPTIMIZED: Connection pooling settings
    # Priority: DATABASE_URL env var > fallback to SQLite
    _db_url = os.environ.get('DATABASE_URL')
    
    # Handle Heroku/Railway-style postgres:// URLs (they need postgresql://)
    if _db_url and _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    
    # Fallback to SQLite for local development without DATABASE_URL
    if not _db_url:
        _db_url = 'sqlite:///' + os.path.join(base_dir, 'brain_capital.db')
        logger.info("📦 Using SQLite database (set DATABASE_URL for PostgreSQL)")
    else:
        # Mask password in log output
        masked_url = _db_url.split('@')[-1] if '@' in _db_url else _db_url
        logger.info(f"🐘 Using PostgreSQL database: ...@{masked_url}")
    
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # OPTIMIZED: Database connection pool settings for better performance
    # Note: SQLite uses different settings than PostgreSQL
    if 'sqlite' in _db_url:
        # SQLite-specific settings
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,  # Enable connection health checks
            'connect_args': {'check_same_thread': False},  # Allow multi-threading
        }
    else:
        # PostgreSQL/MySQL connection pooling
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 10,  # Maximum number of persistent connections
            'pool_recycle': 3600,  # Recycle connections after 1 hour
            'pool_pre_ping': True,  # Enable connection health checks
            'max_overflow': 20,  # Maximum overflow connections
            'pool_timeout': 30,  # Timeout for getting connection from pool
        }

    # --- REDIS (Task Queue) ---
    # URL для підключення до Redis.
    # Приклад: redis://localhost:6379/0
    # Якщо змінна відсутня, додаток буде використовувати локальну чергу в пам'яті (in-memory fallback).
    REDIS_URL = os.environ.get('REDIS_URL')

    # --- ENCRYPTION KEYS (SECURITY HARDENED) ---
    # Master key is loaded from Docker Secret, secure file, or env var (in that order)
    MASTER_KEY_ENCRYPTION = load_master_key()

    # --- EXTERNAL CONFIGS (from .ini with env var override) ---
    try:
        # Binance API credentials - prefer env vars
        BINANCE_MASTER_KEY = get_config_value(
            'MasterAccount', 'api_key', 
            'BINANCE_MASTER_API_KEY'
        )
        BINANCE_MASTER_SECRET = get_config_value(
            'MasterAccount', 'api_secret',
            'BINANCE_MASTER_API_SECRET'
        )
        
        # Webhook passphrase - prefer env var
        WEBHOOK_PASSPHRASE = get_config_value(
            'Webhook', 'passphrase',
            'WEBHOOK_PASSPHRASE'
        )
        
        # Telegram settings - prefer env vars
        TG_TOKEN = get_config_value(
            'Telegram', 'bot_token',
            'TELEGRAM_BOT_TOKEN'
        )
        TG_CHAT_ID = get_config_value(
            'Telegram', 'chat_id',
            'TELEGRAM_CHAT_ID'
        )
        TG_ENABLED = config['Telegram'].getboolean('enabled', False)
        TG_DISABLE_POLLING = config['Telegram'].getboolean('disable_polling', False)
        
        IS_TESTNET = config['Settings'].getboolean('testnet', False)
        GLOBAL_MAX_POSITIONS = int(config['Settings'].get('max_open_positions', 10))
        
        # --- EMAIL SETTINGS (SMTP) ---
        SMTP_SERVER = get_config_value('Email', 'smtp_server', default='') if config.has_section('Email') else ''
        SMTP_PORT = int(config['Email'].get('smtp_port', 587)) if config.has_section('Email') else 587
        SMTP_USERNAME = get_config_value('Email', 'smtp_username', 'SMTP_USERNAME', '') if config.has_section('Email') else ''
        SMTP_PASSWORD = get_config_value('Email', 'smtp_password', 'SMTP_PASSWORD', '') if config.has_section('Email') else ''
        SMTP_FROM_EMAIL = get_config_value('Email', 'from_email', 'SMTP_FROM_EMAIL', '') if config.has_section('Email') else ''
        SMTP_FROM_NAME = config['Email'].get('from_name', 'Brain Capital') if config.has_section('Email') else 'Brain Capital'
        EMAIL_ENABLED = config['Email'].getboolean('enabled', False) if config.has_section('Email') else False
        
        # --- PAYMENT SETTINGS (Plisio Crypto Gateway) ---
        PLISIO_API_KEY = get_config_value('Payment', 'api_key', 'PLISIO_API_KEY', '') if config.has_section('Payment') else os.environ.get('PLISIO_API_KEY', '')
        PLISIO_WEBHOOK_SECRET = get_config_value('Payment', 'webhook_secret', 'PLISIO_WEBHOOK_SECRET', '') if config.has_section('Payment') else os.environ.get('PLISIO_WEBHOOK_SECRET', '')
        PAYMENT_ENABLED = config['Payment'].getboolean('enabled', False) if config.has_section('Payment') else bool(os.environ.get('PLISIO_API_KEY', ''))
        
        # Subscription pricing (in USD)
        SUBSCRIPTION_PLANS = {
            'basic': {'price': 29.99, 'days': 30, 'name': 'Basic Monthly'},
            'pro': {'price': 79.99, 'days': 30, 'name': 'Pro Monthly'},
            'enterprise': {'price': 199.99, 'days': 30, 'name': 'Enterprise Monthly'},
            'basic_annual': {'price': 299.99, 'days': 365, 'name': 'Basic Annual'},
            'pro_annual': {'price': 799.99, 'days': 365, 'name': 'Pro Annual'},
        }
        
        # --- PROXY SETTINGS (for high-volume trading) ---
        PROXY_ENABLED = config['Proxy'].getboolean('enabled', False) if config.has_section('Proxy') else False
        _proxy_list_str = config['Proxy'].get('proxies', '') if config.has_section('Proxy') else ''
        PROXY_LIST = [p.strip() for p in _proxy_list_str.split(',') if p.strip()] if _proxy_list_str else []
        PROXY_USERS_PER_PROXY = int(config['Proxy'].get('users_per_proxy', 50)) if config.has_section('Proxy') else 50
        PROXY_COOLDOWN_SECONDS = int(config['Proxy'].get('proxy_cooldown_seconds', 60)) if config.has_section('Proxy') else 60
        PROXY_MAX_RETRIES = int(config['Proxy'].get('max_proxy_retries', 3)) if config.has_section('Proxy') else 3
        
        # --- PANIC OTP SETTINGS (for Telegram kill switch) ---
        PANIC_OTP_SECRET = get_config_value(
            'PanicOTP', 'secret',
            'PANIC_OTP_SECRET',
            ''
        ) if config.has_section('PanicOTP') else os.environ.get('PANIC_OTP_SECRET', '')
        
        _authorized_users_str = get_config_value(
            'PanicOTP', 'authorized_users',
            'PANIC_AUTHORIZED_USERS',
            ''
        ) if config.has_section('PanicOTP') else os.environ.get('PANIC_AUTHORIZED_USERS', '')
        
        PANIC_AUTHORIZED_USERS = [
            int(uid.strip()) for uid in _authorized_users_str.split(',') 
            if uid.strip().isdigit()
        ] if _authorized_users_str else []
        
        # --- WEB PUSH NOTIFICATION SETTINGS (VAPID) ---
        # Generate VAPID keys using: python -c "from pywebpush import webpush; from cryptography.hazmat.primitives.asymmetric import ec; from cryptography.hazmat.backends import default_backend; from cryptography.hazmat.primitives import serialization; import base64; private_key = ec.generate_private_key(ec.SECP256R1(), default_backend()); print('Private:', base64.urlsafe_b64encode(private_key.private_numbers().private_value.to_bytes(32, 'big')).decode()); public_key = private_key.public_key(); public_numbers = public_key.public_numbers(); x = public_numbers.x.to_bytes(32, 'big'); y = public_numbers.y.to_bytes(32, 'big'); print('Public:', base64.urlsafe_b64encode(b'\\x04' + x + y).decode())"
        # Or simpler: openssl ecparam -name prime256v1 -genkey -noout -out vapid_private.pem
        VAPID_PUBLIC_KEY = get_config_value(
            'WebPush', 'vapid_public_key',
            'VAPID_PUBLIC_KEY',
            ''
        ) if config.has_section('WebPush') else os.environ.get('VAPID_PUBLIC_KEY', '')
        
        VAPID_PRIVATE_KEY = get_config_value(
            'WebPush', 'vapid_private_key',
            'VAPID_PRIVATE_KEY',
            ''
        ) if config.has_section('WebPush') else os.environ.get('VAPID_PRIVATE_KEY', '')
        
        VAPID_CLAIM_EMAIL = get_config_value(
            'WebPush', 'vapid_claim_email',
            'VAPID_CLAIM_EMAIL',
            'mailto:admin@mimic.cash'
        ) if config.has_section('WebPush') else os.environ.get('VAPID_CLAIM_EMAIL', 'mailto:admin@mimic.cash')
        
        WEBPUSH_ENABLED = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)
        
        # --- TWITTER/X API SETTINGS (for auto-posting successful trades) ---
        # Get Twitter API credentials from environment or config.ini
        # Create a developer account at https://developer.twitter.com
        TWITTER_API_KEY = get_config_value(
            'Twitter', 'api_key',
            'TWITTER_API_KEY',
            ''
        ) if config.has_section('Twitter') else os.environ.get('TWITTER_API_KEY', '')
        
        TWITTER_API_SECRET = get_config_value(
            'Twitter', 'api_secret',
            'TWITTER_API_SECRET',
            ''
        ) if config.has_section('Twitter') else os.environ.get('TWITTER_API_SECRET', '')
        
        TWITTER_ACCESS_TOKEN = get_config_value(
            'Twitter', 'access_token',
            'TWITTER_ACCESS_TOKEN',
            ''
        ) if config.has_section('Twitter') else os.environ.get('TWITTER_ACCESS_TOKEN', '')
        
        TWITTER_ACCESS_SECRET = get_config_value(
            'Twitter', 'access_secret',
            'TWITTER_ACCESS_SECRET',
            ''
        ) if config.has_section('Twitter') else os.environ.get('TWITTER_ACCESS_SECRET', '')
        
        # Minimum ROI threshold for auto-posting (default 50%)
        TWITTER_MIN_ROI_THRESHOLD = float(get_config_value(
            'Twitter', 'min_roi_threshold',
            'TWITTER_MIN_ROI_THRESHOLD',
            '50.0'
        ) if config.has_section('Twitter') else os.environ.get('TWITTER_MIN_ROI_THRESHOLD', '50.0'))
        
        # Site URL for tweet links
        SITE_URL = get_config_value(
            'Twitter', 'site_url',
            'SITE_URL',
            'https://mimic.cash'
        ) if config.has_section('Twitter') else os.environ.get('SITE_URL', 'https://mimic.cash')
        
        TWITTER_ENABLED = bool(TWITTER_API_KEY and TWITTER_API_SECRET and TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_SECRET)
        
        # --- RAG SUPPORT BOT SETTINGS (OpenAI + LangChain) ---
        # Get OpenAI API key from environment or config.ini
        # Sign up at https://platform.openai.com to get an API key
        OPENAI_API_KEY = get_config_value(
            'SupportBot', 'openai_api_key',
            'OPENAI_API_KEY',
            ''
        ) if config.has_section('SupportBot') else os.environ.get('OPENAI_API_KEY', '')
        
        # OpenAI model settings
        OPENAI_EMBEDDING_MODEL = get_config_value(
            'SupportBot', 'embedding_model',
            'OPENAI_EMBEDDING_MODEL',
            'text-embedding-3-small'
        ) if config.has_section('SupportBot') else os.environ.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
        
        OPENAI_CHAT_MODEL = get_config_value(
            'SupportBot', 'chat_model',
            'OPENAI_CHAT_MODEL',
            'gpt-4o-mini'
        ) if config.has_section('SupportBot') else os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini')
        
        # RAG configuration
        RAG_CONFIDENCE_THRESHOLD = float(get_config_value(
            'SupportBot', 'confidence_threshold',
            'RAG_CONFIDENCE_THRESHOLD',
            '0.7'
        ) if config.has_section('SupportBot') else os.environ.get('RAG_CONFIDENCE_THRESHOLD', '0.7'))
        
        RAG_CHUNK_SIZE = int(get_config_value(
            'SupportBot', 'chunk_size',
            'RAG_CHUNK_SIZE',
            '500'
        ) if config.has_section('SupportBot') else os.environ.get('RAG_CHUNK_SIZE', '500'))
        
        RAG_CHUNK_OVERLAP = int(get_config_value(
            'SupportBot', 'chunk_overlap',
            'RAG_CHUNK_OVERLAP',
            '50'
        ) if config.has_section('SupportBot') else os.environ.get('RAG_CHUNK_OVERLAP', '50'))
        
        # Enable/disable support bot
        SUPPORT_BOT_ENABLED = bool(OPENAI_API_KEY)
        
        # --- COMPLIANCE SETTINGS (Geo-blocking & TOS) ---
        # Current Terms of Service version - increment when TOS changes to force re-consent
        TOS_VERSION = get_config_value(
            'Compliance', 'tos_version',
            'TOS_VERSION',
            '1.0'
        ) if config.has_section('Compliance') else os.environ.get('TOS_VERSION', '1.0')
        
        # Blocked country codes (ISO 3166-1 alpha-2)
        # US = United States, KP = North Korea, IR = Iran
        _blocked_countries_str = get_config_value(
            'Compliance', 'blocked_countries',
            'BLOCKED_COUNTRIES',
            'US,KP,IR'
        ) if config.has_section('Compliance') else os.environ.get('BLOCKED_COUNTRIES', 'US,KP,IR')
        
        BLOCKED_COUNTRIES = [c.strip().upper() for c in _blocked_countries_str.split(',') if c.strip()]
        
        # GeoIP Database path (MaxMind GeoLite2-Country.mmdb)
        # Download from: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
        GEOIP_DB_PATH = get_config_value(
            'Compliance', 'geoip_db_path',
            'GEOIP_DB_PATH',
            ''
        ) if config.has_section('Compliance') else os.environ.get('GEOIP_DB_PATH', '')
        
        # If not explicitly set, check common locations
        if not GEOIP_DB_PATH:
            common_paths = [
                os.path.join(base_dir, 'GeoLite2-Country.mmdb'),
                os.path.join(base_dir, 'data', 'GeoLite2-Country.mmdb'),
                '/usr/share/GeoIP/GeoLite2-Country.mmdb',
                '/var/lib/GeoIP/GeoLite2-Country.mmdb',
            ]
            for path in common_paths:
                if os.path.exists(path):
                    GEOIP_DB_PATH = path
                    break
        
        # Enable/disable geo-blocking (disabled if no GeoIP database)
        GEO_BLOCKING_ENABLED = bool(GEOIP_DB_PATH and os.path.exists(GEOIP_DB_PATH))
        
        # Enable/disable TOS consent requirement
        TOS_CONSENT_ENABLED = config['Compliance'].getboolean('tos_consent_enabled', True) if config.has_section('Compliance') else os.environ.get('TOS_CONSENT_ENABLED', 'true').lower() == 'true'
        
    except KeyError as e:
        logger.critical(f"❌ Помилка в структурі config.ini: Відсутній ключ {e}")
        raise KeyError(f"Missing key in config.ini: {e}")
    
    # ==================== SECURITY VALIDATION ====================
    
    @classmethod
    def validate_security(cls):
        """
        Validate critical security parameters on startup
        
        SECURITY: This ensures the application won't run with insecure defaults
        """
        errors = []
        warnings = []
        
        # Check SECRET_KEY strength
        if len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY is too short (minimum 32 characters)")
        
        # Check MASTER_KEY_ENCRYPTION is valid Fernet key
        if cls.MASTER_KEY_ENCRYPTION:
            try:
                from cryptography.fernet import Fernet
                Fernet(cls.MASTER_KEY_ENCRYPTION)
            except Exception:
                errors.append("MASTER_KEY_ENCRYPTION is not a valid Fernet key")
        
        # Check webhook passphrase strength
        if hasattr(cls, 'WEBHOOK_PASSPHRASE'):
            passphrase = cls.WEBHOOK_PASSPHRASE or ''
            if len(passphrase) < 16:
                warnings.append("WEBHOOK_PASSPHRASE is weak (recommended: 32+ chars)")
            # Check for common weak passphrases
            weak_passphrases = ['password', '123456', 'admin', 'secret', 'passphrase']
            if passphrase.lower() in weak_passphrases:
                errors.append("WEBHOOK_PASSPHRASE is a common weak password!")
        
        # Check if running with testnet accidentally in production
        if not cls.IS_TESTNET:
            # Production checks
            if 'localhost' in cls.SQLALCHEMY_DATABASE_URI:
                warnings.append("Production mode but using localhost database")
        
        # Check panic OTP configuration
        if cls.PANIC_OTP_SECRET:
            if len(cls.PANIC_OTP_SECRET) < 16:
                warnings.append("PANIC_OTP_SECRET is too short (should be 32 chars base32)")
            if not cls.PANIC_AUTHORIZED_USERS:
                warnings.append("PANIC_OTP_SECRET is set but no authorized users configured")
        
        # Report findings
        for warning in warnings:
            logger.warning(f"⚠️ SECURITY WARNING: {warning}")
        
        if errors:
            for error in errors:
                logger.critical(f"🚨 SECURITY ERROR: {error}")
            raise ValueError(f"Security validation failed: {'; '.join(errors)}")
        
        logger.info("✅ Security validation passed")
        return True


# Run security validation on import (in production mode)
IS_PRODUCTION = os.environ.get('FLASK_ENV', 'development') == 'production'
if IS_PRODUCTION:
    try:
        Config.validate_security()
    except Exception as e:
        logger.critical(f"Security validation failed: {e}")
        # In production, we should fail hard on security issues
        raise
