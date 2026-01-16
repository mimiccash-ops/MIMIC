import secrets
from cryptography.fernet import Fernet
import os
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def _load_env(path: str) -> dict:
    """Load key=value pairs from an env file."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    return values


def create_env_file():
    print("[*] Generating security keys...")
    
    force = '--force' in sys.argv or '-f' in sys.argv
    merge = '--merge' in sys.argv or '-m' in sys.argv
    
    existing = _load_env('.env')
    if os.path.exists('.env') and not force and not merge:
        print("[!] .env file already exists!")
        print("Use --merge (-m) to add missing keys or --force (-f) to overwrite")
        return
    
    # Generate required keys (only if missing or forcing)
    def get_or_generate(key: str, generator):
        if not force and key in existing and existing[key]:
            return existing[key]
        return generator()
    
    flask_secret = get_or_generate('FLASK_SECRET_KEY', lambda: secrets.token_hex(32))
    print("[OK] FLASK_SECRET_KEY ready")
    
    master_key = get_or_generate('BRAIN_CAPITAL_MASTER_KEY', lambda: Fernet.generate_key().decode())
    print("[OK] BRAIN_CAPITAL_MASTER_KEY ready")
    
    webhook_passphrase = get_or_generate('WEBHOOK_PASSPHRASE', lambda: secrets.token_urlsafe(32))
    print("[OK] WEBHOOK_PASSPHRASE ready")
    
    internal_health = get_or_generate('INTERNAL_HEALTH_TOKEN', lambda: secrets.token_hex(32))
    internal_metrics = get_or_generate('INTERNAL_METRICS_TOKEN', lambda: secrets.token_hex(32))
    print("[OK] Internal tokens ready")
    
    env_lines = [
        "# --- SECURITY KEYS ---",
        "# Ключ для підпису сесій (cookies). Нікому не показувати.",
        f"FLASK_SECRET_KEY={flask_secret}",
        "",
        "# Ключ для шифрування API ключів Binance у базі даних.",
        "# ЯКЩО ВИ ВТРАТИТЕ ЦЕЙ КЛЮЧ, ВСІ API КЛЮЧІ КОРИСТУВАЧІВ СТАНУТЬ НЕДОСТУПНИМИ.",
        f"BRAIN_CAPITAL_MASTER_KEY={master_key}",
        "",
        "# TradingView webhook passphrase (used if configured via env).",
        f"WEBHOOK_PASSPHRASE={webhook_passphrase}",
        "",
        "# Internal access tokens for sensitive endpoints.",
        f"INTERNAL_HEALTH_TOKEN={internal_health}",
        f"INTERNAL_METRICS_TOKEN={internal_metrics}",
        "",
        "# --- DATABASE ---",
        "# (Опціонально) Шлях до бази даних. За замовчуванням SQLite.",
        "# DATABASE_URL=postgresql://user:password@localhost/dbname",
        "",
    ]
    
    if merge and os.path.exists('.env') and not force:
        missing = []
        for line in env_lines:
            if line.startswith('#') or not line or '=' not in line:
                continue
            key = line.split('=', 1)[0]
            if key not in existing:
                missing.append(line)
        if missing:
            with open('.env', 'a', encoding='utf-8') as f:
                f.write("\n# --- AUTO-ADDED KEYS ---\n")
                for line in missing:
                    f.write(f"{line}\n")
            print("\n[SUCCESS] .env updated with missing keys!")
        else:
            print("\n[OK] .env already contains all required keys")
        return
    
    # Write new env file
    with open('.env', 'w', encoding='utf-8') as f:
        f.write("\n".join(env_lines))
    
    print("\n[SUCCESS] .env file created!")
    print("You can now run: python app.py")

if __name__ == "__main__":
    try:
        create_env_file()
    except ImportError:
        print("[ERROR] cryptography library not installed.")
        print("Run: pip install cryptography")