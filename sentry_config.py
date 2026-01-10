"""
MIMIC - Sentry Error Tracking Configuration
============================================
Optional Sentry integration for error tracking and performance monitoring.

Setup:
1. Create a Sentry account at https://sentry.io
2. Create a new Python project
3. Set SENTRY_DSN environment variable with your DSN

Usage:
    from sentry_config import init_sentry
    init_sentry(flask_app)  # For Flask
    init_sentry(fastapi_app, framework='fastapi')  # For FastAPI
"""

import os
import logging

logger = logging.getLogger("Sentry")

# Check if Sentry is available
SENTRY_AVAILABLE = False
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    logger.info("Sentry SDK not installed. Error tracking disabled.")
    sentry_sdk = None


def init_sentry(app=None, framework='flask'):
    """
    Initialize Sentry error tracking.
    
    Args:
        app: Flask or FastAPI application instance
        framework: 'flask' or 'fastapi'
    
    Returns:
        bool: True if Sentry was initialized, False otherwise
    """
    dsn = os.environ.get('SENTRY_DSN', '')
    
    if not dsn:
        logger.info("SENTRY_DSN not set. Error tracking disabled.")
        return False
    
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not installed. Run: pip install sentry-sdk[flask]")
        return False
    
    # Determine environment
    environment = os.environ.get('FLASK_ENV', 'development')
    release = os.environ.get('APP_VERSION', '1.0.0')
    
    # Configure integrations
    integrations = [
        SqlalchemyIntegration(),
        RedisIntegration(),
        LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR
        ),
    ]
    
    if framework == 'flask':
        integrations.append(FlaskIntegration())
    elif framework == 'fastapi':
        try:
            from sentry_sdk.integrations.starlette import StarletteIntegration
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            integrations.extend([
                StarletteIntegration(),
                FastApiIntegration(),
            ])
        except ImportError:
            logger.warning("FastAPI Sentry integration not available")
    
    # Initialize Sentry
    sentry_sdk.init(
        dsn=dsn,
        integrations=integrations,
        
        # Environment and release
        environment=environment,
        release=f"mimic@{release}",
        
        # Performance monitoring (adjust sample rate for production)
        traces_sample_rate=0.1 if environment == 'production' else 1.0,
        
        # Profiling (for performance analysis)
        profiles_sample_rate=0.1 if environment == 'production' else 0.5,
        
        # Send PII data (disable in production if needed)
        send_default_pii=environment != 'production',
        
        # Server name (useful for multi-server setups)
        server_name=os.environ.get('SERVER_NAME', 'mimic-server'),
        
        # Max breadcrumbs (for debugging context)
        max_breadcrumbs=50,
        
        # Attach stack trace to messages
        attach_stacktrace=True,
        
        # Before send hook (filter sensitive data)
        before_send=filter_sensitive_data,
        
        # Ignore certain exceptions
        ignore_errors=[
            KeyboardInterrupt,
            SystemExit,
        ],
    )
    
    logger.info(f"✅ Sentry initialized for {environment} environment")
    return True


def filter_sensitive_data(event, hint):
    """
    Filter sensitive data before sending to Sentry.
    
    This hook removes or masks sensitive information from error reports.
    """
    # List of sensitive keys to filter
    sensitive_keys = [
        'password', 'api_key', 'api_secret', 'secret', 'token',
        'authorization', 'cookie', 'session', 'credit_card',
        'ssn', 'master_key', 'private_key'
    ]
    
    def scrub_data(data, parent_key=''):
        """Recursively scrub sensitive data from a dictionary."""
        if isinstance(data, dict):
            for key, value in list(data.items()):
                lower_key = key.lower()
                if any(sensitive in lower_key for sensitive in sensitive_keys):
                    data[key] = '[FILTERED]'
                elif isinstance(value, (dict, list)):
                    scrub_data(value, key)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    scrub_data(item, parent_key)
        return data
    
    # Scrub request data
    if 'request' in event:
        scrub_data(event['request'])
    
    # Scrub extra context
    if 'extra' in event:
        scrub_data(event['extra'])
    
    # Scrub user data
    if 'user' in event:
        if 'ip_address' in event['user']:
            # Mask last octet of IP for privacy
            ip = event['user']['ip_address']
            if ip and '.' in ip:
                parts = ip.split('.')
                if len(parts) == 4:
                    parts[-1] = 'xxx'
                    event['user']['ip_address'] = '.'.join(parts)
    
    return event


def capture_exception(error, **kwargs):
    """
    Capture an exception and send to Sentry.
    
    Args:
        error: The exception to capture
        **kwargs: Additional context to include
    """
    if not SENTRY_AVAILABLE or not sentry_sdk:
        logger.error(f"Error (Sentry disabled): {error}")
        return
    
    with sentry_sdk.push_scope() as scope:
        for key, value in kwargs.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_exception(error)


def capture_message(message, level='info', **kwargs):
    """
    Capture a message and send to Sentry.
    
    Args:
        message: The message to capture
        level: Log level ('debug', 'info', 'warning', 'error', 'fatal')
        **kwargs: Additional context to include
    """
    if not SENTRY_AVAILABLE or not sentry_sdk:
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
        return
    
    with sentry_sdk.push_scope() as scope:
        for key, value in kwargs.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_message(message, level=level)


def set_user_context(user_id, username=None, email=None):
    """
    Set user context for error reports.
    
    Args:
        user_id: User's ID
        username: User's username (optional)
        email: User's email (optional)
    """
    if not SENTRY_AVAILABLE or not sentry_sdk:
        return
    
    sentry_sdk.set_user({
        'id': str(user_id),
        'username': username,
        'email': email,
    })


def clear_user_context():
    """Clear user context (e.g., on logout)."""
    if SENTRY_AVAILABLE and sentry_sdk:
        sentry_sdk.set_user(None)


# Performance monitoring helpers
def start_transaction(name, op='http.server'):
    """Start a new performance transaction."""
    if not SENTRY_AVAILABLE or not sentry_sdk:
        return None
    return sentry_sdk.start_transaction(name=name, op=op)


def add_breadcrumb(message, category='custom', level='info', data=None):
    """Add a breadcrumb for debugging context."""
    if not SENTRY_AVAILABLE or not sentry_sdk:
        return
    sentry_sdk.add_breadcrumb(
        category=category,
        message=message,
        level=level,
        data=data or {}
    )
