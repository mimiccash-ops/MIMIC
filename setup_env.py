import secrets
from cryptography.fernet import Fernet
import os
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def create_env_file():
    print("[*] Generating security keys...")
    
    # 1. Генерація ключа для сесій Flask
    flask_secret = secrets.token_hex(32)
    print("[OK] FLASK_SECRET_KEY generated")

    # 2. Генерація ключа шифрування Fernet (для API ключів)
    master_key = Fernet.generate_key().decode()
    print("[OK] BRAIN_CAPITAL_MASTER_KEY generated")

    # 3. Формування змісту файлу
    env_content = f"""# --- SECURITY KEYS ---
# Ключ для підпису сесій (cookies). Нікому не показувати.
FLASK_SECRET_KEY={flask_secret}

# Ключ для шифрування API ключів Binance у базі даних.
# ЯКЩО ВИ ВТРАТИТЕ ЦЕЙ КЛЮЧ, ВСІ API КЛЮЧІ КОРИСТУВАЧІВ СТАНУТЬ НЕДОСТУПНИМИ.
BRAIN_CAPITAL_MASTER_KEY={master_key}

# --- DATABASE ---
# (Опціонально) Шлях до бази даних. За замовчуванням SQLite.
# DATABASE_URL=postgresql://user:password@localhost/dbname
"""

    # 4. Запис у файл
    force = '--force' in sys.argv or '-f' in sys.argv
    if os.path.exists('.env') and not force:
        print("[!] .env file already exists!")
        print("Use --force or -f to overwrite")
        return

    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("\n[SUCCESS] .env file created!")
    print("You can now run: python app.py")

if __name__ == "__main__":
    try:
        create_env_file()
    except ImportError:
        print("[ERROR] cryptography library not installed.")
        print("Run: pip install cryptography")