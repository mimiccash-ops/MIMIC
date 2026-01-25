#!/bin/bash
#
# Fix config.ini and port configuration
# ====================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing config.ini and ports..."

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
fi

# Update systemd service to use port 8000
if [[ -f /etc/systemd/system/mimic.service ]]; then
    echo "Updating mimic.service to use port 8000..."
    sed -i 's/--bind 127.0.0.1:5000/--bind 127.0.0.1:8000/g' /etc/systemd/system/mimic.service
    systemctl daemon-reload
    echo "✅ Updated mimic.service"
fi

# Update Nginx if it exists
if [[ -f /etc/nginx/sites-enabled/mimic ]] || [[ -f /etc/nginx/nginx.conf ]]; then
    echo "Updating Nginx to use port 8000..."
    # Update nginx config to use port 8000
    sed -i 's/127.0.0.1:5000/127.0.0.1:8000/g' /etc/nginx/sites-enabled/* 2>/dev/null || true
    sed -i 's/127.0.0.1:5000/127.0.0.1:8000/g' /etc/nginx/nginx.conf 2>/dev/null || true
    echo "✅ Updated Nginx configuration"
    echo "⚠️  Run: sudo nginx -t && sudo systemctl reload nginx"
fi

echo ""
echo "✅ Configuration fixed!"
echo ""
echo "Next steps:"
echo "  1. Restart mimic service: sudo systemctl restart mimic"
echo "  2. Test: curl http://localhost:8000/health"
echo "  3. Reload Nginx: sudo nginx -t && sudo systemctl reload nginx"
echo ""
