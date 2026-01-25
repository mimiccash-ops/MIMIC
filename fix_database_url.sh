#!/bin/bash
#
# Fix Database URL in .env file
# ==============================
# Changes Docker hostnames (db, redis) to localhost for VPS deployment
#

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing DATABASE_URL and REDIS_URL in .env..."

if [[ -f "$INSTALL_PATH/.env" ]]; then
    # Fix DATABASE_URL - change 'db' to 'localhost' and use correct credentials
    sed -i 's|@db:|@localhost:|g' "$INSTALL_PATH/.env"
    sed -i 's|postgresql://.*@localhost:.*/brain_capital|postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:5432/mimic_db|g' "$INSTALL_PATH/.env"
    sed -i 's|postgresql://brain_capital:.*@localhost|postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost|g' "$INSTALL_PATH/.env"
    
    # If DATABASE_URL doesn't exist or is still wrong, set it correctly
    if ! grep -q "^DATABASE_URL=postgresql://mimic_user:" "$INSTALL_PATH/.env"; then
        # Remove old DATABASE_URL line if exists
        sed -i '/^DATABASE_URL=/d' "$INSTALL_PATH/.env"
        # Add correct one
        echo "DATABASE_URL=postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:5432/mimic_db" >> "$INSTALL_PATH/.env"
    fi
    
    # Fix REDIS_URL - change 'redis' to 'localhost'
    sed -i 's|redis://redis:|redis://localhost:|g' "$INSTALL_PATH/.env"
    
    # If REDIS_URL doesn't exist, add it
    if ! grep -q "^REDIS_URL=" "$INSTALL_PATH/.env"; then
        echo "REDIS_URL=redis://localhost:6379/0" >> "$INSTALL_PATH/.env"
    fi
    
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
