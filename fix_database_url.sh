#!/bin/bash
#
# Fix Database URL in .env file
# ==============================
# Changes Docker hostnames (db, redis) to localhost for VPS deployment
#

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing DATABASE_URL and REDIS_URL in .env..."

if [[ -f "$INSTALL_PATH/.env" ]]; then
    # Fix DATABASE_URL - change 'db' to 'localhost'
    sed -i 's|@db:|@localhost:|g' "$INSTALL_PATH/.env"
    sed -i 's|postgresql://.*@db:|postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:|g' "$INSTALL_PATH/.env"
    
    # Fix REDIS_URL - change 'redis' to 'localhost'
    sed -i 's|redis://redis:|redis://localhost:|g' "$INSTALL_PATH/.env"
    
    echo "✅ Fixed DATABASE_URL and REDIS_URL"
    echo ""
    echo "Current DATABASE_URL:"
    grep DATABASE_URL "$INSTALL_PATH/.env" || echo "  (not found)"
    echo ""
    echo "Current REDIS_URL:"
    grep REDIS_URL "$INSTALL_PATH/.env" || echo "  (not found)"
else
    echo "❌ .env file not found at $INSTALL_PATH/.env"
    exit 1
fi
