#!/bin/bash
# =============================================================================
# BRAIN CAPITAL - PRODUCTION STARTUP SCRIPT (Linux/Mac)
# =============================================================================
# This script starts the application in production mode
# Make sure to configure your .env file before running!
# =============================================================================

echo "============================================"
echo "  BRAIN CAPITAL - Production Deployment"
echo "============================================"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "[ERROR] .env file not found!"
    echo "Please copy production.env.example to .env and configure it."
    echo ""
    echo "  cp production.env.example .env"
    echo ""
    exit 1
fi

# Load environment variables from .env
set -a
source .env
set +a

# Verify required environment variables
if [ -z "$FLASK_ENV" ]; then
    echo "[ERROR] FLASK_ENV is not set in .env file"
    exit 1
fi

if [ "$FLASK_ENV" != "production" ]; then
    echo "[WARNING] FLASK_ENV is set to '$FLASK_ENV', not 'production'"
    echo "For production deployment, set FLASK_ENV=production in .env"
    echo ""
fi

if [ -z "$FLASK_SECRET_KEY" ]; then
    echo "[ERROR] FLASK_SECRET_KEY is not set in .env file"
    exit 1
fi

if [ -z "$BRAIN_CAPITAL_MASTER_KEY" ]; then
    echo "[ERROR] BRAIN_CAPITAL_MASTER_KEY is not set in .env file"
    exit 1
fi

if [ -z "$PRODUCTION_DOMAIN" ]; then
    echo "[WARNING] PRODUCTION_DOMAIN is not set. CORS may not work correctly."
    echo ""
fi

echo "[INFO] Environment: $FLASK_ENV"
echo "[INFO] Domain: $PRODUCTION_DOMAIN"
echo ""

# Check if gunicorn is installed
if ! python -c "import gunicorn" 2>/dev/null; then
    echo "[INFO] Installing gunicorn (production WSGI server)..."
    pip install gunicorn gevent
fi

echo "[INFO] Starting Brain Capital in PRODUCTION mode..."
echo "[INFO] Press Ctrl+C to stop the server"
echo ""

# Start with gunicorn (production-ready WSGI server)
# Using gevent for WebSocket support
gunicorn --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
         --workers 4 \
         --bind 0.0.0.0:5000 \
         --timeout 120 \
         --keep-alive 5 \
         --access-logfile - \
         --error-logfile - \
         --capture-output \
         "app:app"

