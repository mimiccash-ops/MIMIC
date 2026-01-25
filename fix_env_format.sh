#!/bin/bash
#
# Fix .env file format - ensure proper line breaks
#

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing .env file format..."

if [[ -f "$INSTALL_PATH/.env" ]]; then
    # Fix the stuck line (START_MODE=dockerDATABASE_URL=...)
    sed -i 's/START_MODE=dockerDATABASE_URL=/START_MODE=docker\nDATABASE_URL=/g' "$INSTALL_PATH/.env"
    
    # Ensure DATABASE_URL is correct
    sed -i '/^DATABASE_URL=/d' "$INSTALL_PATH/.env"
    echo "" >> "$INSTALL_PATH/.env"
    echo "DATABASE_URL=postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:5432/mimic_db" >> "$INSTALL_PATH/.env"
    
    # Ensure REDIS_URL is correct
    if ! grep -q "^REDIS_URL=" "$INSTALL_PATH/.env"; then
        echo "REDIS_URL=redis://localhost:6379/0" >> "$INSTALL_PATH/.env"
    fi
    
    echo "✅ .env file fixed"
    echo ""
    echo "Current DATABASE_URL:"
    grep "^DATABASE_URL=" "$INSTALL_PATH/.env"
    echo ""
    echo "Current REDIS_URL:"
    grep "^REDIS_URL=" "$INSTALL_PATH/.env"
else
    echo "❌ .env file not found"
    exit 1
fi
