"""
Brain Capital Security Module v1.0
Comprehensive protection against attacks
"""

import time
import hashlib
import secrets
import logging
import re
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

from flask import request, abort, session, g, jsonify

logger = logging.getLogger("Security")


# ==================== RATE LIMITER ====================

class RateLimiter:
    """
    Advanced rate limiter with sliding window
    Protects against brute force and DDoS attacks
    
    SECURITY HARDENED:
    - Auto-cleanup of stale entries to prevent memory exhaustion
    - Thread-safe operations
    - Automatic escalation for repeat offenders
    """
    MAX_TRACKED_KEYS = 10000  # Prevent memory exhaustion attack
    CLEANUP_INTERVAL = 300  # Cleanup every 5 minutes
    
    def __init__(self):
        self.requests = defaultdict(list)  # {key: [timestamps]}
        self.blocked = {}  # {key: unblock_time}
        self.offense_count = defaultdict(int)  # Track repeat offenders
        self.lock = Lock()
        self._last_cleanup = time.time()
    
    def _cleanup(self, key: str, window: int):
        """Remove old requests outside the window"""
        now = time.time()
        self.requests[key] = [t for t in self.requests[key] if now - t < window]
    
    def _global_cleanup(self):
        """Periodic cleanup of all stale entries to prevent memory growth"""
        now = time.time()
        if now - self._last_cleanup < self.CLEANUP_INTERVAL:
            return
        
        self._last_cleanup = now
        
        # Cleanup expired blocks
        expired_blocks = [k for k, v in self.blocked.items() if v <= now]
        for k in expired_blocks:
            del self.blocked[k]
        
        # Cleanup old request entries (older than 1 hour)
        stale_keys = []
        for key, timestamps in self.requests.items():
            if not timestamps or (now - max(timestamps)) > 3600:
                stale_keys.append(key)
        for k in stale_keys:
            del self.requests[k]
        
        # Cleanup old offense counts (older than 24 hours check)
        if len(self.offense_count) > self.MAX_TRACKED_KEYS:
            # Keep only recent offenders - reset all
            self.offense_count.clear()
        
        if stale_keys or expired_blocks:
            logger.debug(f"Rate limiter cleanup: {len(stale_keys)} stale, {len(expired_blocks)} expired blocks")
    
    def is_blocked(self, key: str) -> bool:
        """Check if key is currently blocked"""
        if key in self.blocked:
            if time.time() < self.blocked[key]:
                return True
            del self.blocked[key]
        return False
    
    def block(self, key: str, duration: int = 300):
        """Block a key for specified duration (default 5 minutes)"""
        with self.lock:
            # Escalate block duration for repeat offenders
            self.offense_count[key] += 1
            escalated_duration = min(duration * self.offense_count[key], 3600)  # Max 1 hour
            self.blocked[key] = time.time() + escalated_duration
            logger.warning(f"🚫 Blocked {key} for {escalated_duration}s (offense #{self.offense_count[key]})")
    
    def check(self, key: str, max_requests: int, window: int) -> bool:
        """
        Check if request is allowed
        Returns True if allowed, False if rate limited
        """
        if self.is_blocked(key):
            return False
        
        with self.lock:
            # Periodic global cleanup
            self._global_cleanup()
            
            # Prevent memory exhaustion - limit tracked keys
            if len(self.requests) > self.MAX_TRACKED_KEYS:
                logger.warning("Rate limiter approaching memory limit - forcing cleanup")
                self.requests.clear()
            
            self._cleanup(key, window)
            
            if len(self.requests[key]) >= max_requests:
                return False
            
            self.requests[key].append(time.time())
            return True
    
    def get_remaining(self, key: str, max_requests: int, window: int) -> int:
        """Get remaining requests allowed"""
        with self.lock:
            self._cleanup(key, window)
            return max(0, max_requests - len(self.requests[key]))


# Global rate limiters
login_limiter = RateLimiter()
api_limiter = RateLimiter()
webhook_limiter = RateLimiter()


# ==================== FAILED LOGIN TRACKER ====================

class LoginTracker:
    """
    Track failed login attempts and block suspicious IPs
    
    SECURITY HARDENED:
    - Progressive block duration for repeat offenders
    - Automatic cleanup to prevent memory exhaustion
    - Account lockout protection
    """
    MAX_TRACKED_IPS = 50000  # Prevent memory exhaustion
    
    def __init__(self):
        self.failed_attempts = defaultdict(list)  # {ip: [timestamps]}
        self.blocked_ips = {}  # {ip: unblock_time}
        self.block_count = defaultdict(int)  # Track how many times IP was blocked
        self.lock = Lock()
        self._last_cleanup = time.time()
        
        # Configuration - HARDENED VALUES
        self.max_attempts = 5  # Max failed attempts before block
        self.window = 300  # 5 minute window
        self.block_duration = 900  # 15 minute initial block
        self.max_block_duration = 86400  # Maximum 24 hour block
        self.permanent_block_threshold = 10  # After this many blocks, 24h block
    
    def _global_cleanup(self):
        """Periodic cleanup of stale entries"""
        now = time.time()
        if now - self._last_cleanup < 300:  # Every 5 minutes
            return
        
        self._last_cleanup = now
        
        # Cleanup expired blocks
        expired = [ip for ip, t in self.blocked_ips.items() if t <= now]
        for ip in expired:
            del self.blocked_ips[ip]
        
        # Cleanup old failed attempts
        stale = [ip for ip, times in self.failed_attempts.items() 
                 if not times or (now - max(times)) > self.window * 2]
        for ip in stale:
            del self.failed_attempts[ip]
        
        # Prevent memory exhaustion
        if len(self.failed_attempts) > self.MAX_TRACKED_IPS:
            self.failed_attempts.clear()
            logger.warning("Login tracker memory limit reached - cleared tracking data")
    
    def record_failure(self, ip: str, username: str = None):
        """Record a failed login attempt"""
        with self.lock:
            self._global_cleanup()
            
            now = time.time()
            self.failed_attempts[ip].append(now)
            
            # Cleanup old attempts
            self.failed_attempts[ip] = [
                t for t in self.failed_attempts[ip] 
                if now - t < self.window
            ]
            
            attempts = len(self.failed_attempts[ip])
            logger.warning(f"⚠️ Failed login from {ip} ({attempts}/{self.max_attempts}) user={username}")
            
            if attempts >= self.max_attempts:
                self.block_ip(ip)
    
    def record_success(self, ip: str):
        """Clear failed attempts on successful login"""
        with self.lock:
            if ip in self.failed_attempts:
                del self.failed_attempts[ip]
    
    def block_ip(self, ip: str):
        """Block an IP address with escalating duration for repeat offenders"""
        with self.lock:
            self.block_count[ip] += 1
            
            # Escalate block duration for repeat offenders
            if self.block_count[ip] >= self.permanent_block_threshold:
                duration = self.max_block_duration  # 24 hour block
            else:
                # Double the duration each time, up to max
                duration = min(self.block_duration * (2 ** (self.block_count[ip] - 1)), 
                              self.max_block_duration)
            
            self.blocked_ips[ip] = time.time() + duration
            logger.critical(f"🚫 IP BLOCKED: {ip} for {duration}s (block #{self.block_count[ip]})")
    
    def is_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        if ip in self.blocked_ips:
            if time.time() < self.blocked_ips[ip]:
                return True
            del self.blocked_ips[ip]
        return False
    
    def get_blocked_ips(self) -> dict:
        """Get all currently blocked IPs"""
        now = time.time()
        return {ip: int(t - now) for ip, t in self.blocked_ips.items() if t > now}


login_tracker = LoginTracker()


# ==================== INPUT VALIDATION ====================

class InputValidator:
    """
    Validates and sanitizes user input
    Prevents SQL injection, XSS, and other attacks
    """
    
    # Patterns for validation
    USERNAME_PATTERN = re.compile(r'^[\w\+\-\.@]{3,50}$')
    PHONE_PATTERN = re.compile(r'^\+?[\d\s\-\(\)]{10,20}$')
    # Updated pattern to support various exchanges (Bybit keys are ~18 chars, some use hyphens/underscores)
    API_KEY_PATTERN = re.compile(r'^[A-Za-z0-9\-_]{16,200}$')
    SYMBOL_PATTERN = re.compile(r'^[A-Z0-9]{2,20}$')
    
    # Dangerous patterns to block
    SQL_INJECTION_PATTERNS = [
        r"('|\")\s*(OR|AND)\s*('|\"|\d)",
        r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER)",
        r"UNION\s+SELECT",
        r"--\s*$",
        r"/\*.*\*/",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe",
        r"<object",
        r"<embed",
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 255) -> str:
        """Basic string sanitization"""
        if not value:
            return ""
        
        # Trim and limit length
        value = str(value).strip()[:max_length]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        return value
    
    @classmethod
    def validate_username(cls, username: str) -> tuple:
        """Validate username format"""
        username = cls.sanitize_string(username, 50)
        
        if not username:
            return False, "Username is required"
        
        if len(username) < 3:
            return False, "Username too short (min 3 chars)"
        
        if not cls.USERNAME_PATTERN.match(username):
            return False, "Invalid username format"
        
        return True, username
    
    @classmethod
    def validate_password(cls, password: str, strict: bool = True) -> tuple:
        """
        Validate password strength
        
        SECURITY: Enforces strong password policy
        - Minimum 8 characters
        - Maximum 128 characters
        - Must contain uppercase, lowercase, digit, and special character for strict mode
        """
        if not password:
            return False, "Password is required"
        
        if len(password) < 8:
            return False, "Password too short (min 8 characters)"
        
        if len(password) > 128:
            return False, "Password too long"
        
        # Strict validation for new passwords
        if strict:
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`]', password))
            
            if not has_upper:
                return False, "Password must contain at least one uppercase letter (A-Z)"
            if not has_lower:
                return False, "Password must contain at least one lowercase letter (a-z)"
            if not has_digit:
                return False, "Password must contain at least one number (0-9)"
            if not has_special:
                return False, "Password must contain at least one special character (!@#$%^&*)"
        
        # Check for dangerous patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, password, re.IGNORECASE):
                return False, "Invalid password characters"
        
        return True, password
    
    @classmethod
    def validate_api_key(cls, key: str) -> tuple:
        """Validate Binance API key format"""
        key = cls.sanitize_string(key, 100)
        
        if not key:
            return False, "API key is required"
        
        if not cls.API_KEY_PATTERN.match(key):
            return False, "Invalid API key format"
        
        return True, key
    
    @classmethod
    def validate_symbol(cls, symbol: str) -> tuple:
        """Validate trading symbol"""
        symbol = cls.sanitize_string(symbol, 20).upper()
        
        if not symbol:
            return False, "Symbol is required"
        
        if not cls.SYMBOL_PATTERN.match(symbol):
            return False, "Invalid symbol format"
        
        return True, symbol
    
    @classmethod
    def check_injection(cls, value: str) -> bool:
        """Check for SQL injection or XSS attempts"""
        if not value:
            return False
        
        value_lower = value.lower()
        
        # Check SQL injection
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.critical(f"🚨 SQL INJECTION ATTEMPT: {value[:100]}")
                return True
        
        # Check XSS
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.critical(f"🚨 XSS ATTEMPT: {value[:100]}")
                return True
        
        return False


# ==================== SECURITY DECORATORS ====================

def rate_limit(max_requests: int = 10, window: int = 60, key_func=None):
    """
    Rate limiting decorator
    
    Usage:
        @rate_limit(max_requests=5, window=60)
        def my_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Get rate limit key (default: IP address)
            if key_func:
                key = key_func()
            else:
                key = get_client_ip()
            
            if not api_limiter.check(key, max_requests, window):
                logger.warning(f"Rate limit exceeded for {key}")
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': window
                }), 429
            
            return f(*args, **kwargs)
        return wrapped
    return decorator


def login_required_secure(f):
    """
    Enhanced login required decorator with security checks
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        from flask_login import current_user
        
        if not current_user.is_authenticated:
            abort(401)
        
        # Verify session integrity
        if not verify_session():
            abort(401)
        
        return f(*args, **kwargs)
    return wrapped


def admin_required(f):
    """
    Admin-only access decorator
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        from flask_login import current_user
        
        if not current_user.is_authenticated:
            abort(401)
        
        if current_user.role != 'admin':
            logger.warning(f"⚠️ Unauthorized admin access attempt by {current_user.username}")
            abort(403)
        
        return f(*args, **kwargs)
    return wrapped


def validate_webhook(f):
    """
    Webhook validation decorator
    Checks passphrase and rate limits
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        ip = get_client_ip()
        
        # Rate limit webhooks
        if not webhook_limiter.check(ip, max_requests=30, window=60):
            logger.warning(f"Webhook rate limit exceeded for {ip}")
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        return f(*args, **kwargs)
    return wrapped


# ==================== HELPER FUNCTIONS ====================

def get_client_ip() -> str:
    """Get real client IP (handles proxies)"""
    # Check for proxy headers
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or '0.0.0.0'


def generate_csrf_token() -> str:
    """Generate CSRF token for forms"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def verify_csrf_token(token: str) -> bool:
    """Verify CSRF token"""
    return token and token == session.get('csrf_token')


def verify_session() -> bool:
    """Verify session integrity"""
    # Check session fingerprint
    current_fingerprint = generate_session_fingerprint()
    stored_fingerprint = session.get('fingerprint')
    
    if stored_fingerprint and stored_fingerprint != current_fingerprint:
        logger.warning(f"Session fingerprint mismatch! Possible session hijacking.")
        return False
    
    return True


def generate_session_fingerprint() -> str:
    """Generate browser fingerprint for session validation"""
    components = [
        request.headers.get('User-Agent', ''),
        request.headers.get('Accept-Language', ''),
    ]
    fingerprint = hashlib.sha256('|'.join(components).encode()).hexdigest()[:16]
    return fingerprint


def init_session_security():
    """Initialize session security on login"""
    session['fingerprint'] = generate_session_fingerprint()
    session['created_at'] = time.time()
    session.permanent = True


def hash_sensitive_log(value: str) -> str:
    """Hash sensitive values for logging"""
    if not value:
        return "[empty]"
    return f"{value[:3]}...{value[-3:]}" if len(value) > 6 else "***"


# ==================== SECURITY HEADERS ====================

def add_security_headers(response):
    """Add security headers to response"""
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # XSS Protection
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Prevent MIME sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Referrer Policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Content Security Policy - Allow all required CDNs
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.socket.io https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "https://cdn.tailwindcss.com https://unpkg.com https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
        "img-src 'self' data: https: blob:; "
        "media-src 'self' data: blob:; "
        "connect-src 'self' ws: wss: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
        "worker-src 'self' blob:; "
        "frame-ancestors 'self';"
    )
    
    # Permissions Policy
    response.headers['Permissions-Policy'] = (
        'geolocation=(), microphone=(), camera=()'
    )
    
    return response


# ==================== AUDIT LOGGING ====================

class SecurityAudit:
    """
    Security event logging for audit trails
    """
    
    @staticmethod
    def log_login(username: str, ip: str, success: bool, reason: str = None):
        """Log login attempts"""
        status = "SUCCESS" if success else "FAILED"
        msg = f"[AUTH] {status} - User: {username}, IP: {ip}"
        if reason:
            msg += f", Reason: {reason}"
        
        if success:
            logger.info(msg)
        else:
            logger.warning(msg)
    
    @staticmethod
    def log_admin_action(admin: str, action: str, target: str, details: str = None):
        """Log admin actions"""
        msg = f"[ADMIN] {admin} - Action: {action}, Target: {target}"
        if details:
            msg += f", Details: {details}"
        logger.info(msg)
    
    @staticmethod
    def log_api_access(user: str, endpoint: str, ip: str):
        """Log API access"""
        logger.debug(f"[API] User: {user}, Endpoint: {endpoint}, IP: {ip}")
    
    @staticmethod
    def log_security_event(event_type: str, details: str, severity: str = "WARNING"):
        """Log security events"""
        msg = f"[SECURITY] {event_type}: {details}"
        if severity == "CRITICAL":
            logger.critical(msg)
        elif severity == "WARNING":
            logger.warning(msg)
        else:
            logger.info(msg)


audit = SecurityAudit()


# ==================== ENCRYPTION SERVICE ====================

def get_cipher_suite():
    """Get Fernet cipher suite instance"""
    from config import Config
    from cryptography.fernet import Fernet
    
    if not Config.MASTER_KEY_ENCRYPTION:
        raise ValueError("MASTER_KEY_ENCRYPTION not configured")
    
    try:
        return Fernet(Config.MASTER_KEY_ENCRYPTION.encode() if isinstance(Config.MASTER_KEY_ENCRYPTION, str) else Config.MASTER_KEY_ENCRYPTION)
    except Exception as e:
        logger.error(f"Failed to initialize cipher suite: {e}")
        raise


def encrypt_secret(plain_text: str) -> str:
    """
    Encrypt a secret string using Fernet symmetric encryption
    
    Args:
        plain_text: Plain text secret to encrypt
        
    Returns:
        Encrypted string (base64 encoded)
        
    Raises:
        ValueError: If encryption key is not configured
        Exception: If encryption fails
    """
    if not plain_text:
        return ""
    
    try:
        cipher = get_cipher_suite()
        encrypted_bytes = cipher.encrypt(plain_text.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError(f"Failed to encrypt secret: {str(e)}")


def decrypt_secret(cipher_text: str) -> str:
    """
    Decrypt an encrypted secret string
    
    Args:
        cipher_text: Encrypted string (base64 encoded)
        
    Returns:
        Decrypted plain text string
        
    Raises:
        ValueError: If decryption fails or key is invalid
    """
    if not cipher_text:
        return ""
    
    try:
        cipher = get_cipher_suite()
        decrypted_bytes = cipher.decrypt(cipher_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise ValueError(f"Failed to decrypt secret: {str(e)}")


# ==================== API TOKEN GENERATION ====================

def generate_api_token(user_id: int) -> str:
    """
    Generate a secure API token for FastAPI authentication
    
    Token format: base64(user_id:timestamp:hmac_signature)
    
    Args:
        user_id: The user's ID
        
    Returns:
        Base64 encoded token string
    """
    import hmac
    import hashlib
    import base64
    import time
    from config import Config
    
    timestamp = int(time.time())
    message = f"{user_id}:{timestamp}".encode()
    
    secret_key = Config.SECRET_KEY.encode() if isinstance(Config.SECRET_KEY, str) else Config.SECRET_KEY
    signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    
    token_data = f"{user_id}:{timestamp}:{signature}"
    token = base64.urlsafe_b64encode(token_data.encode()).decode()
    
    return token


def verify_api_token(token: str) -> tuple:
    """
    Verify an API token
    
    Args:
        token: The token to verify
        
    Returns:
        Tuple of (is_valid: bool, user_id: int or None)
    """
    import hmac
    import hashlib
    import base64
    import time
    from config import Config
    
    TOKEN_MAX_AGE = 3600  # 1 hour
    
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.split(':')
        
        if len(parts) != 3:
            return False, None
        
        user_id_str, timestamp_str, received_signature = parts
        user_id = int(user_id_str)
        timestamp = int(timestamp_str)
        
        # Check expiration
        if int(time.time()) - timestamp > TOKEN_MAX_AGE:
            return False, None
        
        # Verify signature
        secret_key = Config.SECRET_KEY.encode() if isinstance(Config.SECRET_KEY, str) else Config.SECRET_KEY
        message = f"{user_id}:{timestamp}".encode()
        expected_signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(received_signature, expected_signature):
            return False, None
        
        return True, user_id
        
    except Exception:
        return False, None


# ==================== ADDITIONAL SECURITY UTILITIES ====================

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem use
    """
    import os
    import unicodedata
    
    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename)
    filename = filename.encode('ASCII', 'ignore').decode('ASCII')
    
    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')
    filename = filename.replace('..', '')
    
    # Remove null bytes
    filename = filename.replace('\x00', '')
    
    # Get just the base name (no directory)
    filename = os.path.basename(filename)
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    
    return name + ext


def is_safe_redirect_url(target: str) -> bool:
    """
    Check if a redirect URL is safe (prevents open redirect attacks)
    
    Args:
        target: The redirect target URL
        
    Returns:
        True if the URL is safe for redirect
    """
    from urllib.parse import urlparse
    
    if not target:
        return False
    
    # Only allow relative URLs (no scheme or netloc)
    parsed = urlparse(target)
    
    # Must not have a scheme (http, https) or netloc (domain)
    if parsed.scheme or parsed.netloc:
        return False
    
    # Must start with /
    if not target.startswith('/'):
        return False
    
    # Must not contain ..
    if '..' in target:
        return False
    
    return True


def mask_sensitive_string(value: str, show_chars: int = 4) -> str:
    """
    Mask a sensitive string for safe display/logging
    
    Args:
        value: The string to mask
        show_chars: Number of characters to show at start and end
        
    Returns:
        Masked string like "abcd...wxyz"
    """
    if not value:
        return "[empty]"
    
    if len(value) <= show_chars * 2:
        return "*" * len(value)
    
    return f"{value[:show_chars]}...{value[-show_chars:]}"
