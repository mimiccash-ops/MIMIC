#!/bin/bash
# =============================================================================
# BRAIN CAPITAL - ARQ WORKER LAUNCHER (Linux/Mac)
# =============================================================================
# Runs the background task processor for trading signals
# This must run alongside the Flask app to process webhook signals
# =============================================================================

echo "===================================================="
echo "    MIMIC ARQ Worker - Brain Capital v9.0"
echo "===================================================="
echo ""

# Check if .env file exists and load it
if [ -f ".env" ]; then
    echo "[*] Loading environment from .env file..."
    set -a
    source .env
    set +a
else
    echo "[!] WARNING: .env file not found. Using default settings."
fi

# Check if Redis is accessible
echo "[*] Checking Redis connection..."
python3 -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379, db=0); r.ping(); print('    Redis: OK')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[!] WARNING: Redis not accessible at 127.0.0.1:6379"
    echo "[!] Make sure Redis is running before starting the worker"
    echo "[!] Try: sudo systemctl start redis"
    echo ""
    exit 1
fi

# Set Redis URL if not already set
if [ -z "$REDIS_URL" ]; then
    export REDIS_URL="redis://127.0.0.1:6379/0"
fi

echo "[*] Redis URL: $REDIS_URL"
echo "[*] Press Ctrl+C to stop"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the worker
python3 worker.py
