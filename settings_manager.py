"""
Settings Manager Module

Provides dynamic access to system settings stored in the database,
with fallback to config.py/environment variables for backward compatibility.

Usage:
    from settings_manager import get_setting, is_service_enabled
    
    # Get a specific setting
    telegram_token = get_setting('telegram', 'bot_token')
    
    # Check if a service is enabled
    if is_service_enabled('telegram'):
        send_telegram_notification(...)
"""

import logging
from functools import lru_cache
from config import Config

logger = logging.getLogger("SettingsManager")

# Cache for database connection availability
_db_available = None


def _check_db_available():
    """Check if database and SystemSetting model are available"""
    global _db_available
    if _db_available is not None:
        return _db_available
    
    try:
        from models import db, SystemSetting
        # Try a simple query
        with db.session.begin_nested():
            SystemSetting.query.first()
        _db_available = True
    except Exception:
        _db_available = False
    
    return _db_available


def get_setting(category: str, key: str, default: str = '') -> str:
    """
    Get a setting value with database priority and config.py fallback.
    
    Priority:
    1. Database (SystemSetting table)
    2. Config class attribute (env vars / config.ini)
    3. Default value
    
    Args:
        category: Setting category (e.g., 'telegram', 'payment')
        key: Setting key (e.g., 'bot_token', 'api_key')
        default: Default value if not found anywhere
        
    Returns:
        The setting value
    """
    # Try database first
    try:
        if _check_db_available():
            from models import SystemSetting
            value = SystemSetting.get_setting(category, key, '')
            if value:
                return value
    except Exception as e:
        logger.debug(f"Could not read {category}.{key} from database: {e}")
    
    # Fallback to Config class
    config_mapping = {
        ('telegram', 'bot_token'): 'TG_TOKEN',
        ('telegram', 'chat_id'): 'TG_CHAT_ID',
        ('telegram', 'enabled'): 'TG_ENABLED',
        ('email', 'smtp_server'): 'SMTP_SERVER',
        ('email', 'smtp_port'): 'SMTP_PORT',
        ('email', 'smtp_username'): 'SMTP_USERNAME',
        ('email', 'smtp_password'): 'SMTP_PASSWORD',
        ('email', 'from_email'): 'SMTP_FROM_EMAIL',
        ('email', 'from_name'): 'SMTP_FROM_NAME',
        ('email', 'enabled'): 'EMAIL_ENABLED',
        ('payment', 'api_key'): 'PLISIO_API_KEY',
        ('payment', 'webhook_secret'): 'PLISIO_WEBHOOK_SECRET',
        ('payment', 'enabled'): 'PAYMENT_ENABLED',
        ('twitter', 'api_key'): 'TWITTER_API_KEY',
        ('twitter', 'api_secret'): 'TWITTER_API_SECRET',
        ('twitter', 'access_token'): 'TWITTER_ACCESS_TOKEN',
        ('twitter', 'access_secret'): 'TWITTER_ACCESS_SECRET',
        ('twitter', 'min_roi_threshold'): 'TWITTER_MIN_ROI_THRESHOLD',
        ('twitter', 'site_url'): 'SITE_URL',
        ('twitter', 'enabled'): 'TWITTER_ENABLED',
        ('openai', 'api_key'): 'OPENAI_API_KEY',
        ('openai', 'embedding_model'): 'OPENAI_EMBEDDING_MODEL',
        ('openai', 'chat_model'): 'OPENAI_CHAT_MODEL',
        ('openai', 'confidence_threshold'): 'RAG_CONFIDENCE_THRESHOLD',
        ('openai', 'enabled'): 'SUPPORT_BOT_ENABLED',
        ('webpush', 'vapid_public_key'): 'VAPID_PUBLIC_KEY',
        ('webpush', 'vapid_private_key'): 'VAPID_PRIVATE_KEY',
        ('webpush', 'vapid_claim_email'): 'VAPID_CLAIM_EMAIL',
        ('webpush', 'enabled'): 'WEBPUSH_ENABLED',
        ('binance', 'api_key'): 'BINANCE_MASTER_KEY',
        ('binance', 'api_secret'): 'BINANCE_MASTER_SECRET',
        ('binance', 'testnet'): 'IS_TESTNET',
        ('webhook', 'passphrase'): 'WEBHOOK_PASSPHRASE',
        ('compliance', 'tos_version'): 'TOS_VERSION',
        ('compliance', 'blocked_countries'): 'BLOCKED_COUNTRIES',
        ('compliance', 'tos_consent_enabled'): 'TOS_CONSENT_ENABLED',
        ('compliance', 'geo_blocking_enabled'): 'GEO_BLOCKING_ENABLED',
        ('general', 'max_open_positions'): 'GLOBAL_MAX_POSITIONS',
        ('proxy', 'enabled'): 'PROXY_ENABLED',
        ('proxy', 'proxies'): 'PROXY_LIST',
        ('panic', 'otp_secret'): 'PANIC_OTP_SECRET',
        ('panic', 'authorized_users'): 'PANIC_AUTHORIZED_USERS',
    }
    
    config_attr = config_mapping.get((category, key))
    if config_attr:
        try:
            value = getattr(Config, config_attr, None)
            if value is not None:
                # Convert non-string values
                if isinstance(value, bool):
                    return str(value).lower()
                if isinstance(value, (list, tuple)):
                    return ','.join(str(v) for v in value)
                return str(value)
        except Exception as e:
            logger.debug(f"Could not read Config.{config_attr}: {e}")
    
    return default


def is_service_enabled(category: str) -> bool:
    """
    Check if a service category is enabled.
    
    First checks database, then falls back to Config class.
    
    Args:
        category: Service category name
        
    Returns:
        True if service is enabled and configured
    """
    # Try database first
    try:
        if _check_db_available():
            from models import SystemSetting
            return SystemSetting.is_service_enabled(category)
    except Exception:
        pass
    
    # Fallback to Config class
    config_enabled_attrs = {
        'telegram': 'TG_ENABLED',
        'email': 'EMAIL_ENABLED',
        'payment': 'PAYMENT_ENABLED',
        'twitter': 'TWITTER_ENABLED',
        'openai': 'SUPPORT_BOT_ENABLED',
        'webpush': 'WEBPUSH_ENABLED',
    }
    
    attr = config_enabled_attrs.get(category)
    if attr:
        try:
            return bool(getattr(Config, attr, False))
        except Exception:
            pass
    
    return False


def get_category_settings(category: str) -> dict:
    """
    Get all settings for a category as a dictionary.
    
    Args:
        category: Setting category
        
    Returns:
        Dict of key -> value for the category
    """
    # Try database first
    try:
        if _check_db_available():
            from models import SystemSetting
            return SystemSetting.get_category_settings(category)
    except Exception:
        pass
    
    # Fallback - return empty dict as we can't easily enumerate Config attributes
    return {}


def clear_cache():
    """Clear any cached values (call after updating settings)"""
    global _db_available
    _db_available = None


# Service configuration metadata
SERVICE_INFO = {
    'telegram': {
        'name': 'Telegram Bot',
        'icon': 'fab fa-telegram',
        'description': 'Telegram notifications and panic kill switch',
    },
    'email': {
        'name': 'Email/SMTP',
        'icon': 'fas fa-envelope',
        'description': 'Email notifications for password recovery and alerts',
    },
    'payment': {
        'name': 'Plisio Payments',
        'icon': 'fas fa-credit-card',
        'description': 'Crypto payment gateway for subscriptions',
    },
    'twitter': {
        'name': 'Twitter/X',
        'icon': 'fab fa-twitter',
        'description': 'Auto-post successful trades to Twitter',
    },
    'openai': {
        'name': 'OpenAI (Support Bot)',
        'icon': 'fas fa-robot',
        'description': 'AI-powered support chatbot with RAG',
    },
    'webpush': {
        'name': 'Web Push',
        'icon': 'fas fa-bell',
        'description': 'Browser push notifications (PWA)',
    },
    'binance': {
        'name': 'Binance Master',
        'icon': 'fas fa-coins',
        'description': 'Master trading account for copy trading',
    },
    'webhook': {
        'name': 'TradingView Webhook',
        'icon': 'fas fa-bolt',
        'description': 'Receive trading signals from TradingView',
    },
}
