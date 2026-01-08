"""
Brain Capital - Production Server Launcher
https://mimic.cash

This script starts the application in production mode with all
security settings enabled.
"""

import os
import sys

# ==================== FORCE PRODUCTION MODE ====================
os.environ['FLASK_ENV'] = 'production'
os.environ['PRODUCTION_DOMAIN'] = 'https://mimic.cash,https://www.mimic.cash'

# Load .env file if exists
env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_file):
    with open(env_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Force production regardless of .env
os.environ['FLASK_ENV'] = 'production'
os.environ['PRODUCTION_DOMAIN'] = 'https://mimic.cash,https://www.mimic.cash'

def main():
    print("=" * 60)
    print("  BRAIN CAPITAL - PRODUCTION SERVER")
    print("  https://mimic.cash")
    print("=" * 60)
    print()
    print(f"  FLASK_ENV: {os.environ.get('FLASK_ENV')}")
    print(f"  DOMAIN: {os.environ.get('PRODUCTION_DOMAIN')}")
    print(f"  PORT: 80")
    print()
    print("  Press Ctrl+C to stop the server")
    print("=" * 60)
    print()

    try:
        # Import app with threading mode (already configured in app.py)
        from app import app, socketio
        
        print("[OK] Starting production server with WebSocket support...")
        print("[OK] Server running on http://0.0.0.0:80")
        print()
        
        # Use socketio.run with threading mode (configured in app.py)
        # This supports WebSockets without eventlet/gevent issues
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=80, 
            debug=False,
            use_reloader=False,
            log_output=True
        )
                
    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e}")
        print("[INFO] Run: pip install -r requirements.txt")
        sys.exit(1)
    except PermissionError:
        print("[ERROR] Permission denied for port 80!")
        print("[INFO] Run as Administrator: Right-click -> Run as administrator")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
