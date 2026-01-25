#!/bin/bash
#
# Fix config.ini - add missing sections
# ======================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing config.ini..."
echo ""

cd "$INSTALL_PATH"

# Add [Settings] section if missing
if ! grep -q "^\[Settings\]" config.ini; then
    echo "Adding [Settings] section to config.ini..."
    cat >> config.ini << 'EOF'

[Settings]
testnet = False
max_open_positions = 10
EOF
    echo "✅ Added [Settings] section"
else
    echo "✅ [Settings] section already exists"
fi

# Ensure [Telegram] section exists
if ! grep -q "^\[Telegram\]" config.ini; then
    echo "Adding [Telegram] section to config.ini..."
    cat >> config.ini << 'EOF'

[Telegram]
bot_token = 
chat_id = 
enabled = False
disable_polling = False
polling_startup_delay = 30
EOF
    echo "✅ Added [Telegram] section"
else
    echo "✅ [Telegram] section already exists"
fi

echo ""
echo "✅ config.ini fixed!"
echo ""
echo "Restarting worker to apply changes..."
docker compose restart worker
sleep 3

echo ""
echo "Checking worker status..."
if docker compose ps worker | grep -q "Up"; then
    echo "✅ Worker is running"
    echo ""
    echo "Checking logs (last 5 lines)..."
    docker compose logs --tail=5 worker
else
    echo "❌ Worker failed to start"
    docker compose logs --tail=20 worker
fi

echo ""
