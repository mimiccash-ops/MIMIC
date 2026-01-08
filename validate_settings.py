#!/usr/bin/env python3
"""
Brain Capital - Admin Settings Validator
=========================================

This script validates your admin_settings.ini configuration file
and generates the .env file for Docker deployment.

Usage:
    python validate_settings.py              # Validate and show status
    python validate_settings.py --generate   # Generate .env file
    python validate_settings.py --help       # Show help
"""

import configparser
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def color(text: str, color_code: str) -> str:
    """Wrap text in color codes (Windows compatible)."""
    if os.name == 'nt':
        # Enable ANSI colors on Windows
        os.system('')
    return f"{color_code}{text}{Colors.ENDC}"

# Base directory
BASE_DIR = Path(__file__).parent
SETTINGS_FILE = BASE_DIR / "admin_settings.ini"
ENV_FILE = BASE_DIR / ".env"
CONFIG_INI_FILE = BASE_DIR / "config.ini"

# Required fields configuration
REQUIRED_FIELDS = {
    'Security': {
        'flask_secret_key': {'min_length': 32, 'description': 'Flask session key'},
        'master_encryption_key': {'min_length': 32, 'description': 'User API encryption key'},
        'webhook_passphrase': {'min_length': 16, 'description': 'TradingView webhook secret'},
    },
    'Binance': {
        'api_key': {'min_length': 10, 'description': 'Binance API key'},
        'api_secret': {'min_length': 10, 'description': 'Binance API secret'},
    },
    'Database': {
        'password': {'min_length': 8, 'description': 'PostgreSQL password'},
    },
}

OPTIONAL_FIELDS = {
    'Telegram': {
        'bot_token': {'pattern': r'^\d+:[A-Za-z0-9_-]+$', 'description': 'Telegram bot token'},
        'chat_id': {'pattern': r'^-?\d+$', 'description': 'Telegram chat ID'},
    },
    'Payments': {
        'plisio_api_key': {'min_length': 10, 'description': 'Plisio API key'},
        'plisio_webhook_secret': {'min_length': 10, 'description': 'Plisio webhook secret'},
    },
    'Email': {
        'email_address': {'pattern': r'^[^@]+@[^@]+\.[^@]+$', 'description': 'SMTP email'},
        'email_password': {'min_length': 1, 'description': 'SMTP password'},
    },
}


def load_settings() -> configparser.ConfigParser:
    """Load admin_settings.ini file with automatic encoding detection."""
    if not SETTINGS_FILE.exists():
        print(color(f"❌ Settings file not found: {SETTINGS_FILE}", Colors.RED))
        print(color("   Creating from template...", Colors.YELLOW))
        create_settings_from_template()
        sys.exit(1)
    
    # First, check if file is a binary file (SQLite, etc.)
    try:
        with open(SETTINGS_FILE, 'rb') as f:
            header = f.read(16)
        
        # Check for SQLite database header
        if header.startswith(b'SQLite format 3'):
            print(color(f"❌ ERROR: {SETTINGS_FILE.name} is a SQLite database, not a config file!", Colors.RED))
            print(color("", Colors.RED))
            print(color("   This file was accidentally overwritten with a database.", Colors.YELLOW))
            print(color("   Fixing automatically...", Colors.CYAN))
            print()
            
            # Backup the corrupted file
            backup_path = SETTINGS_FILE.with_suffix('.ini.corrupted')
            SETTINGS_FILE.rename(backup_path)
            print(color(f"   ✓ Corrupted file backed up to: {backup_path.name}", Colors.GREEN))
            
            # Create fresh settings file
            create_settings_from_template()
            print(color(f"   ✓ Fresh {SETTINGS_FILE.name} created from template", Colors.GREEN))
            print()
            print(color("   ⚠️  Please edit admin_settings.ini with your settings!", Colors.YELLOW))
            print(color("   Run: notepad admin_settings.ini", Colors.CYAN))
            sys.exit(1)
        
        # Check for other binary file signatures
        if b'\x00' in header[:100]:
            print(color(f"❌ ERROR: {SETTINGS_FILE.name} appears to be a binary file!", Colors.RED))
            print(color("   Creating fresh config from template...", Colors.YELLOW))
            
            backup_path = SETTINGS_FILE.with_suffix('.ini.corrupted')
            SETTINGS_FILE.rename(backup_path)
            create_settings_from_template()
            print(color(f"   ✓ Fresh {SETTINGS_FILE.name} created", Colors.GREEN))
            sys.exit(1)
            
    except Exception as e:
        print(color(f"⚠️  Warning checking file: {e}", Colors.YELLOW))
    
    config = configparser.ConfigParser()
    
    # Try multiple encodings (common Windows encodings)
    encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            config.read(SETTINGS_FILE, encoding=encoding)
            if config.sections():  # Successfully parsed with sections
                return config
        except UnicodeDecodeError:
            continue
        except Exception:
            continue
    
    # If all encodings fail, try to read and fix the file
    print(color(f"⚠️  Encoding issue detected in {SETTINGS_FILE.name}", Colors.YELLOW))
    print(color("   Attempting to fix encoding...", Colors.CYAN))
    
    try:
        # Read with errors='replace' to handle bad bytes
        with open(SETTINGS_FILE, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Check if content looks like a valid INI file
        if '[' not in content or ']' not in content:
            print(color(f"❌ File doesn't appear to be a valid INI file", Colors.RED))
            print(color("   Creating fresh config from template...", Colors.YELLOW))
            
            backup_path = SETTINGS_FILE.with_suffix('.ini.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            create_settings_from_template()
            print(color(f"   ✓ Fresh {SETTINGS_FILE.name} created", Colors.GREEN))
            print(color(f"   ⚠️  Please edit with your settings!", Colors.YELLOW))
            sys.exit(1)
        
        # Write back with proper UTF-8 encoding
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(color("   ✓ File encoding fixed", Colors.GREEN))
        
        # Try reading again
        config = configparser.ConfigParser()
        config.read(SETTINGS_FILE, encoding='utf-8')
        return config
        
    except Exception as e:
        print(color(f"❌ Cannot read settings file: {e}", Colors.RED))
        print(color("   Creating fresh config from template...", Colors.YELLOW))
        create_settings_from_template()
        sys.exit(1)
    
    return config


def create_settings_from_template():
    """Create admin_settings.ini from the embedded template."""
    template = '''# =============================================================================
#                    🧠 BRAIN CAPITAL - ADMIN SETTINGS
# =============================================================================
# Fill in your settings below. Lines starting with # are comments.
# After editing, run: python validate_settings.py --generate
# =============================================================================

[Security]
# Flask secret key (REQUIRED) - Generate: python -c "import secrets; print(secrets.token_hex(32))"
flask_secret_key = 

# Master encryption key (REQUIRED) - Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
master_encryption_key = 

# Webhook passphrase (REQUIRED) - Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
webhook_passphrase = 

[Binance]
# Your Binance Futures API credentials
api_key = 
api_secret = 
use_testnet = False
max_open_positions = 10

[Database]
host = db
port = 5432
name = brain_capital
username = brain_capital
# Database password (REQUIRED)
password = 

[Telegram]
# Telegram bot settings (optional but recommended)
bot_token = 
chat_id = 
enabled = False
panic_otp_secret = 
panic_authorized_users = 

[Payments]
enabled = False
plisio_api_key = 
plisio_webhook_secret = 

[Email]
enabled = False
smtp_server = smtp.gmail.com
smtp_port = 587
email_address = 
email_password = 
from_name = Brain Capital

[Domain]
production_url = 
https_enabled = False

[Redis]
host = redis
port = 6379
database = 0

[Proxy]
enabled = False
proxies = 

[Monitoring]
enabled = True
grafana_user = admin
grafana_password = braincapital2024
'''
    
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        f.write(template)
    
    print(color(f"   Created: {SETTINGS_FILE.name}", Colors.GREEN))


def validate_field(value: str, rules: dict) -> Tuple[bool, str]:
    """Validate a single field against its rules."""
    if not value or value.strip() == '':
        return False, "Empty or not set"
    
    value = value.strip()
    
    # Check minimum length
    if 'min_length' in rules and len(value) < rules['min_length']:
        return False, f"Too short (min {rules['min_length']} chars)"
    
    # Check pattern
    if 'pattern' in rules and not re.match(rules['pattern'], value):
        return False, "Invalid format"
    
    return True, "OK"


def validate_all(config: configparser.ConfigParser) -> Tuple[Dict, Dict, Dict]:
    """Validate all settings and return results."""
    errors = {}
    warnings = {}
    success = {}
    
    # Check required fields
    for section, fields in REQUIRED_FIELDS.items():
        if not config.has_section(section):
            errors[f"{section}"] = "Section missing"
            continue
            
        for field, rules in fields.items():
            key = f"{section}.{field}"
            value = config.get(section, field, fallback='')
            is_valid, message = validate_field(value, rules)
            
            if is_valid:
                success[key] = rules.get('description', field)
            else:
                errors[key] = f"{rules.get('description', field)}: {message}"
    
    # Check optional fields (if their section is enabled)
    for section, fields in OPTIONAL_FIELDS.items():
        if not config.has_section(section):
            continue
        
        # Check if section is enabled
        enabled = config.getboolean(section, 'enabled', fallback=True)
        
        for field, rules in fields.items():
            key = f"{section}.{field}"
            value = config.get(section, field, fallback='')
            is_valid, message = validate_field(value, rules)
            
            if enabled and not is_valid:
                warnings[key] = f"{rules.get('description', field)}: {message}"
            elif is_valid:
                success[key] = rules.get('description', field)
    
    return errors, warnings, success


def print_validation_report(errors: Dict, warnings: Dict, success: Dict):
    """Print a formatted validation report."""
    print()
    print(color("=" * 60, Colors.CYAN))
    print(color("   🧠 BRAIN CAPITAL - Settings Validation Report", Colors.BOLD))
    print(color("=" * 60, Colors.CYAN))
    print()
    
    # Success items
    if success:
        print(color("✅ CONFIGURED:", Colors.GREEN))
        for key, desc in success.items():
            print(color(f"   ✓ {desc}", Colors.GREEN))
        print()
    
    # Warnings
    if warnings:
        print(color("⚠️  WARNINGS (optional but recommended):", Colors.YELLOW))
        for key, message in warnings.items():
            print(color(f"   ⚠ {message}", Colors.YELLOW))
        print()
    
    # Errors
    if errors:
        print(color("❌ ERRORS (must fix):", Colors.RED))
        for key, message in errors.items():
            print(color(f"   ✗ {message}", Colors.RED))
        print()
    
    # Summary
    print(color("-" * 60, Colors.CYAN))
    total = len(errors) + len(warnings) + len(success)
    print(f"   Total: {len(success)}/{total} configured")
    
    if errors:
        print(color(f"   Status: ❌ {len(errors)} error(s) - CANNOT START", Colors.RED))
        return False
    elif warnings:
        print(color(f"   Status: ⚠️  {len(warnings)} warning(s) - CAN START", Colors.YELLOW))
        return True
    else:
        print(color("   Status: ✅ All required settings configured!", Colors.GREEN))
        return True
    
    print()


def generate_env_file(config: configparser.ConfigParser) -> bool:
    """Generate .env file from admin_settings.ini."""
    print()
    print(color("📝 Generating .env file...", Colors.CYAN))
    
    env_lines = [
        "# =============================================================================",
        "# BRAIN CAPITAL - Environment Variables (Auto-generated)",
        "# =============================================================================",
        f"# Generated from admin_settings.ini",
        f"# DO NOT EDIT DIRECTLY - Edit admin_settings.ini instead!",
        "# =============================================================================",
        "",
    ]
    
    # Security
    env_lines.append("# ==================== SECURITY ====================")
    env_lines.append(f"FLASK_ENV=production")
    env_lines.append(f"FLASK_SECRET_KEY={config.get('Security', 'flask_secret_key', fallback='')}")
    env_lines.append(f"BRAIN_CAPITAL_MASTER_KEY={config.get('Security', 'master_encryption_key', fallback='')}")
    env_lines.append(f"WEBHOOK_PASSPHRASE={config.get('Security', 'webhook_passphrase', fallback='')}")
    env_lines.append("")
    
    # Binance
    env_lines.append("# ==================== BINANCE ====================")
    env_lines.append(f"BINANCE_MASTER_API_KEY={config.get('Binance', 'api_key', fallback='')}")
    env_lines.append(f"BINANCE_MASTER_API_SECRET={config.get('Binance', 'api_secret', fallback='')}")
    env_lines.append("")
    
    # Database
    env_lines.append("# ==================== DATABASE ====================")
    db_host = config.get('Database', 'host', fallback='db')
    db_port = config.get('Database', 'port', fallback='5432')
    db_name = config.get('Database', 'name', fallback='brain_capital')
    db_user = config.get('Database', 'username', fallback='brain_capital')
    db_pass = config.get('Database', 'password', fallback='')
    env_lines.append(f"DATABASE_URL=postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")
    env_lines.append(f"POSTGRES_PASSWORD={db_pass}")
    env_lines.append("")
    
    # Redis
    env_lines.append("# ==================== REDIS ====================")
    redis_host = config.get('Redis', 'host', fallback='redis')
    redis_port = config.get('Redis', 'port', fallback='6379')
    redis_db = config.get('Redis', 'database', fallback='0')
    env_lines.append(f"REDIS_URL=redis://{redis_host}:{redis_port}/{redis_db}")
    env_lines.append("")
    
    # Telegram
    env_lines.append("# ==================== TELEGRAM ====================")
    env_lines.append(f"TELEGRAM_BOT_TOKEN={config.get('Telegram', 'bot_token', fallback='')}")
    env_lines.append(f"TELEGRAM_CHAT_ID={config.get('Telegram', 'chat_id', fallback='')}")
    env_lines.append(f"PANIC_OTP_SECRET={config.get('Telegram', 'panic_otp_secret', fallback='')}")
    env_lines.append(f"PANIC_AUTHORIZED_USERS={config.get('Telegram', 'panic_authorized_users', fallback='')}")
    env_lines.append("")
    
    # Payments
    env_lines.append("# ==================== PAYMENTS ====================")
    env_lines.append(f"PLISIO_API_KEY={config.get('Payments', 'plisio_api_key', fallback='')}")
    env_lines.append(f"PLISIO_WEBHOOK_SECRET={config.get('Payments', 'plisio_webhook_secret', fallback='')}")
    env_lines.append("")
    
    # Email
    env_lines.append("# ==================== EMAIL ====================")
    env_lines.append(f"SMTP_USERNAME={config.get('Email', 'email_address', fallback='')}")
    env_lines.append(f"SMTP_PASSWORD={config.get('Email', 'email_password', fallback='')}")
    env_lines.append(f"SMTP_FROM_EMAIL={config.get('Email', 'email_address', fallback='')}")
    env_lines.append("")
    
    # Domain
    env_lines.append("# ==================== DOMAIN ====================")
    env_lines.append(f"PRODUCTION_DOMAIN={config.get('Domain', 'production_url', fallback='https://localhost')}")
    env_lines.append(f"HTTPS_ENABLED={config.get('Domain', 'https_enabled', fallback='false')}")
    env_lines.append("")
    
    # Monitoring
    env_lines.append("# ==================== MONITORING ====================")
    env_lines.append(f"GRAFANA_ADMIN_USER={config.get('Monitoring', 'grafana_user', fallback='admin')}")
    env_lines.append(f"GRAFANA_ADMIN_PASSWORD={config.get('Monitoring', 'grafana_password', fallback='braincapital2024')}")
    env_lines.append(f"GRAFANA_ROOT_URL={config.get('Monitoring', 'grafana_url', fallback='http://localhost:3000')}")
    env_lines.append("")
    
    # Write to file
    try:
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(env_lines))
        print(color(f"✅ Generated: {ENV_FILE}", Colors.GREEN))
        return True
    except Exception as e:
        print(color(f"❌ Failed to write .env: {e}", Colors.RED))
        return False


def generate_config_ini(config: configparser.ConfigParser) -> bool:
    """Generate config.ini file from admin_settings.ini."""
    print(color("📝 Generating config.ini...", Colors.CYAN))
    
    ini_lines = [
        "# =============================================================================",
        "# BRAIN CAPITAL - Configuration (Auto-generated)",
        "# =============================================================================",
        "# Generated from admin_settings.ini",
        "# DO NOT EDIT DIRECTLY - Edit admin_settings.ini instead!",
        "# =============================================================================",
        "",
        "[MasterAccount]",
        f"api_key = ${{BINANCE_MASTER_API_KEY}}",
        f"api_secret = ${{BINANCE_MASTER_API_SECRET}}",
        "",
        "[Webhook]",
        f"passphrase = ${{WEBHOOK_PASSPHRASE}}",
        "",
        "[Settings]",
        f"testnet = {config.get('Binance', 'use_testnet', fallback='False')}",
        f"max_open_positions = {config.get('Binance', 'max_open_positions', fallback='10')}",
        "",
        "[Telegram]",
        f"bot_token = ${{TELEGRAM_BOT_TOKEN}}",
        f"chat_id = ${{TELEGRAM_CHAT_ID}}",
        f"enabled = {config.get('Telegram', 'enabled', fallback='True')}",
        "",
        "[Email]",
        f"smtp_server = {config.get('Email', 'smtp_server', fallback='smtp.gmail.com')}",
        f"smtp_port = {config.get('Email', 'smtp_port', fallback='587')}",
        f"smtp_username = ${{SMTP_USERNAME}}",
        f"smtp_password = ${{SMTP_PASSWORD}}",
        f"from_email = ${{SMTP_FROM_EMAIL}}",
        f"from_name = {config.get('Email', 'from_name', fallback='Brain Capital')}",
        f"enabled = {config.get('Email', 'enabled', fallback='False')}",
        "",
        "[Payment]",
        f"api_key = ${{PLISIO_API_KEY}}",
        f"webhook_secret = ${{PLISIO_WEBHOOK_SECRET}}",
        f"enabled = {config.get('Payments', 'enabled', fallback='False')}",
        "",
        "[Production]",
        f"domain = {config.get('Domain', 'production_url', fallback='https://localhost')}",
        "ssl_cert = ",
        "ssl_key = ",
        "",
        "[Proxy]",
        f"enabled = {config.get('Proxy', 'enabled', fallback='False')}",
        f"proxies = {config.get('Proxy', 'proxies', fallback='')}",
        f"users_per_proxy = {config.get('Proxy', 'users_per_proxy', fallback='50')}",
        f"proxy_cooldown_seconds = {config.get('Proxy', 'cooldown_seconds', fallback='60')}",
        f"max_proxy_retries = {config.get('Proxy', 'max_retries', fallback='3')}",
        "",
        "[PanicOTP]",
        f"secret = ${{PANIC_OTP_SECRET}}",
        f"authorized_users = ${{PANIC_AUTHORIZED_USERS}}",
    ]
    
    try:
        with open(CONFIG_INI_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(ini_lines))
        print(color(f"✅ Generated: {CONFIG_INI_FILE}", Colors.GREEN))
        return True
    except Exception as e:
        print(color(f"❌ Failed to write config.ini: {e}", Colors.RED))
        return False


def show_checklist(config: configparser.ConfigParser):
    """Show a checklist of what's configured."""
    print()
    print(color("=" * 60, Colors.CYAN))
    print(color("   📋 CONFIGURATION CHECKLIST", Colors.BOLD))
    print(color("=" * 60, Colors.CYAN))
    print()
    
    sections = [
        ('Security', 'flask_secret_key', '🔐 Flask & Security Keys'),
        ('Binance', 'api_key', '📈 Binance API'),
        ('Database', 'password', '🗄️ Database (PostgreSQL)'),
        ('Telegram', 'bot_token', '🤖 Telegram Bot'),
        ('Payments', 'plisio_api_key', '💳 Payments (Plisio)'),
        ('Email', 'email_address', '📧 Email (SMTP)'),
        ('Domain', 'production_url', '🌐 Domain & SSL'),
        ('VPS', 'host', '🖥️ VPS & Deployment'),
        ('Monitoring', 'grafana_password', '📊 Monitoring (Grafana)'),
    ]
    
    for section, key, label in sections:
        if config.has_section(section):
            value = config.get(section, key, fallback='')
            enabled = config.getboolean(section, 'enabled', fallback=True)
            
            if value and value.strip():
                print(color(f"   [✓] {label}", Colors.GREEN))
            elif not enabled:
                print(color(f"   [—] {label} (disabled)", Colors.BLUE))
            else:
                print(color(f"   [✗] {label}", Colors.RED))
        else:
            print(color(f"   [?] {label} (section missing)", Colors.YELLOW))
    
    print()


def main():
    """Main entry point."""
    print(color("""
    ██████╗ ██████╗  █████╗ ██╗███╗   ██╗     ██████╗ █████╗ ██████╗ ██╗████████╗ █████╗ ██╗     
    ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║    ██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝██╔══██╗██║     
    ██████╔╝██████╔╝███████║██║██╔██╗ ██║    ██║     ███████║██████╔╝██║   ██║   ███████║██║     
    ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║    ██║     ██╔══██║██╔═══╝ ██║   ██║   ██╔══██║██║     
    ██████╔╝██║  ██║██║  ██║██║██║ ╚████║    ╚██████╗██║  ██║██║     ██║   ██║   ██║  ██║███████╗
    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝     ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝
    """, Colors.CYAN))
    print(color("                    Settings Validator v1.0", Colors.BOLD))
    print()
    
    # Check for --help
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        sys.exit(0)
    
    # Load settings
    config = load_settings()
    
    # Show checklist
    show_checklist(config)
    
    # Validate
    errors, warnings, success = validate_all(config)
    is_valid = print_validation_report(errors, warnings, success)
    
    # Generate files if requested or if valid
    if '--generate' in sys.argv or (is_valid and '--no-generate' not in sys.argv):
        print()
        generate_env_file(config)
        generate_config_ini(config)
        print()
        
        if is_valid:
            print(color("=" * 60, Colors.GREEN))
            print(color("   ✅ READY TO START!", Colors.GREEN))
            print(color("=" * 60, Colors.GREEN))
            print()
            print(color("   Run: docker-compose up -d --build", Colors.CYAN))
            print()
    else:
        print()
        print(color("   Fix the errors above, then run:", Colors.YELLOW))
        print(color("   python validate_settings.py --generate", Colors.CYAN))
        print()
    
    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()

