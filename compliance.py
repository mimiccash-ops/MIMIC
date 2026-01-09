"""
Brain Capital Compliance Module

REGULATORY COMPLIANCE:
1. Geo-blocking: Blocks access from restricted jurisdictions (US, North Korea, Iran)
2. TOS Consent: Forces users to accept Terms of Service and Risk Disclaimer

Usage:
    from compliance import init_compliance, check_geo_blocking, check_tos_consent
    
    # In app.py, after creating Flask app:
    init_compliance(app)
"""

import logging
from functools import wraps
from typing import Optional, Tuple

from flask import request, abort, redirect, url_for, g, render_template_string
from flask_login import current_user

logger = logging.getLogger("Compliance")

# GeoIP reader instance (initialized once)
_geoip_reader = None
_geoip_available = False


def init_geoip(db_path: str) -> bool:
    """
    Initialize the GeoIP2 database reader.
    
    Args:
        db_path: Path to the MaxMind GeoLite2-Country.mmdb file
        
    Returns:
        True if successfully initialized, False otherwise
    """
    global _geoip_reader, _geoip_available
    
    if not db_path:
        logger.warning("⚠️ GeoIP database path not configured - geo-blocking disabled")
        return False
    
    try:
        import geoip2.database
        _geoip_reader = geoip2.database.Reader(db_path)
        _geoip_available = True
        logger.info(f"✅ GeoIP database loaded from: {db_path}")
        return True
    except FileNotFoundError:
        logger.warning(f"⚠️ GeoIP database not found at: {db_path} - geo-blocking disabled")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to load GeoIP database: {e}")
        return False


def get_country_from_ip(ip_address: str) -> Optional[str]:
    """
    Get the ISO country code for an IP address.
    
    Args:
        ip_address: The client's IP address
        
    Returns:
        ISO 3166-1 alpha-2 country code (e.g., "US", "GB") or None if unknown
    """
    global _geoip_reader, _geoip_available
    
    if not _geoip_available or not _geoip_reader:
        return None
    
    # Skip private/local IPs
    if ip_address in ('127.0.0.1', 'localhost', '::1') or ip_address.startswith(('192.168.', '10.', '172.16.')):
        return None
    
    try:
        response = _geoip_reader.country(ip_address)
        return response.country.iso_code
    except Exception:
        # IP not found in database or other error
        return None


def is_country_blocked(country_code: str, blocked_countries: list) -> bool:
    """
    Check if a country is in the blocked list.
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code
        blocked_countries: List of blocked country codes
        
    Returns:
        True if country is blocked
    """
    if not country_code:
        return False
    return country_code.upper() in blocked_countries


def check_geo_blocking(blocked_countries: list) -> Tuple[bool, Optional[str]]:
    """
    Check if the current request should be blocked based on geo-location.
    
    Args:
        blocked_countries: List of blocked ISO country codes
        
    Returns:
        Tuple of (is_blocked, country_code)
    """
    from security import get_client_ip
    
    if not _geoip_available:
        return False, None
    
    ip = get_client_ip()
    country = get_country_from_ip(ip)
    
    if country and is_country_blocked(country, blocked_countries):
        logger.warning(f"🚫 Geo-blocked access attempt from {country} (IP: {ip})")
        return True, country
    
    return False, country


def check_tos_consent(user_id: int, required_version: str) -> bool:
    """
    Check if user has accepted the required TOS version.
    
    Args:
        user_id: The user's database ID
        required_version: The minimum required TOS version
        
    Returns:
        True if user has accepted the required version
    """
    from models import UserConsent
    return UserConsent.has_user_accepted_tos(user_id, required_version)


# ==================== BLOCKED PAGE TEMPLATE ====================

GEO_BLOCKED_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Service Unavailable - MIMIC</title>
    <style>
        :root {
            --bg-dark: #0a0a12;
            --text-primary: #ffffff;
            --text-secondary: #94a3b8;
            --neon-cyan: #00f0ff;
            --neon-red: #ff4757;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        
        .container {
            max-width: 600px;
            text-align: center;
            background: rgba(15, 15, 24, 0.95);
            border: 1px solid rgba(255, 71, 87, 0.3);
            border-radius: 16px;
            padding: 48px;
            box-shadow: 0 0 60px rgba(255, 71, 87, 0.1);
        }
        
        .icon {
            width: 80px;
            height: 80px;
            background: rgba(255, 71, 87, 0.1);
            border: 2px solid rgba(255, 71, 87, 0.3);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
            font-size: 36px;
        }
        
        h1 {
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 16px;
            color: var(--neon-red);
        }
        
        p {
            font-size: 1rem;
            color: var(--text-secondary);
            line-height: 1.6;
            margin-bottom: 24px;
        }
        
        .notice {
            background: rgba(255, 71, 87, 0.05);
            border: 1px solid rgba(255, 71, 87, 0.2);
            border-radius: 8px;
            padding: 16px;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }
        
        .code {
            font-family: monospace;
            background: rgba(0, 0, 0, 0.3);
            padding: 2px 8px;
            border-radius: 4px;
            color: var(--neon-cyan);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🚫</div>
        <h1>Service Unavailable in Your Region</h1>
        <p>
            We're sorry, but MIMIC services are not available in your jurisdiction 
            due to regulatory requirements.
        </p>
        <p>
            Our platform complies with international financial regulations and 
            cannot serve users from certain regions.
        </p>
        <div class="notice">
            <strong>Error Code:</strong> <span class="code">GEO_RESTRICTED_403</span><br>
            If you believe this is an error, please contact support.
        </div>
    </div>
</body>
</html>
"""


# ==================== COMPLIANCE MIDDLEWARE ====================

def init_compliance(app):
    """
    Initialize compliance middleware for the Flask application.
    
    This sets up:
    1. GeoIP database reader
    2. Before-request hooks for geo-blocking and TOS checking
    
    Args:
        app: Flask application instance
    """
    from config import Config
    
    # Initialize GeoIP if configured
    if hasattr(Config, 'GEOIP_DB_PATH') and Config.GEOIP_DB_PATH:
        init_geoip(Config.GEOIP_DB_PATH)
    
    # Get compliance settings
    blocked_countries = getattr(Config, 'BLOCKED_COUNTRIES', ['US', 'KP', 'IR'])
    tos_version = getattr(Config, 'TOS_VERSION', '1.0')
    geo_blocking_enabled = getattr(Config, 'GEO_BLOCKING_ENABLED', False)
    tos_consent_enabled = getattr(Config, 'TOS_CONSENT_ENABLED', True)
    
    # Routes that don't require compliance checks
    EXEMPT_ROUTES = {
        'static',
        'login',
        'register',
        'logout',
        'forgot_password',
        'reset_password',
        'legal_accept',  # TOS acceptance page
        'legal_tos',
        'legal_privacy',
        'legal_risk_disclaimer',
        'prometheus_metrics',
        'health_check',
        'api_health',
        'geo_blocked',
    }
    
    # API routes that should be geo-blocked but don't need TOS check
    API_ROUTES_PREFIX = '/api/'
    
    @app.before_request
    def compliance_check():
        """
        Run compliance checks before each request.
        
        1. Geo-blocking: Block requests from restricted countries
        2. TOS consent: Redirect authenticated users who haven't accepted TOS
        """
        # Skip compliance checks for exempt routes
        if request.endpoint in EXEMPT_ROUTES:
            return None
        
        # Skip static files
        if request.path.startswith('/static/'):
            return None
        
        # 1. GEO-BLOCKING CHECK
        if geo_blocking_enabled and _geoip_available:
            is_blocked, country = check_geo_blocking(blocked_countries)
            if is_blocked:
                # Store country in g for potential logging
                g.blocked_country = country
                
                # For API requests, return JSON
                if request.path.startswith(API_ROUTES_PREFIX):
                    from flask import jsonify
                    return jsonify({
                        'error': 'Service unavailable in your region',
                        'code': 'GEO_RESTRICTED',
                        'status': 403
                    }), 403
                
                # For web requests, show blocked page
                return render_template_string(GEO_BLOCKED_TEMPLATE), 403
        
        # 2. TOS CONSENT CHECK (only for authenticated users)
        if tos_consent_enabled and current_user.is_authenticated:
            # Skip TOS check for certain paths
            if request.path.startswith('/legal/'):
                return None
            
            # Check if user has accepted the current TOS version
            if not check_tos_consent(current_user.id, tos_version):
                # Store flag in g for template access
                g.needs_tos_consent = True
                g.tos_version = tos_version
                
                # For API requests, return error
                if request.path.startswith(API_ROUTES_PREFIX):
                    from flask import jsonify
                    return jsonify({
                        'error': 'You must accept the Terms of Service to continue',
                        'code': 'TOS_CONSENT_REQUIRED',
                        'redirect': url_for('legal_accept'),
                        'status': 403
                    }), 403
                
                # Redirect to TOS acceptance page
                return redirect(url_for('legal_accept'))
        
        return None
    
    logger.info(f"✅ Compliance middleware initialized")
    logger.info(f"   - Geo-blocking: {'ENABLED' if geo_blocking_enabled else 'DISABLED'} (Countries: {', '.join(blocked_countries)})")
    logger.info(f"   - TOS Consent: {'ENABLED' if tos_consent_enabled else 'DISABLED'} (Version: {tos_version})")


def compliance_required(f):
    """
    Decorator to explicitly require compliance checks on a route.
    
    Usage:
        @app.route('/protected')
        @compliance_required
        def protected_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from config import Config
        
        # Check geo-blocking
        if getattr(Config, 'GEO_BLOCKING_ENABLED', False):
            blocked_countries = getattr(Config, 'BLOCKED_COUNTRIES', ['US', 'KP', 'IR'])
            is_blocked, country = check_geo_blocking(blocked_countries)
            if is_blocked:
                abort(403)
        
        # Check TOS consent
        if getattr(Config, 'TOS_CONSENT_ENABLED', True) and current_user.is_authenticated:
            tos_version = getattr(Config, 'TOS_VERSION', '1.0')
            if not check_tos_consent(current_user.id, tos_version):
                return redirect(url_for('legal_accept'))
        
        return f(*args, **kwargs)
    return decorated_function
