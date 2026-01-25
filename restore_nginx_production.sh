#!/bin/bash
#
# Restore full production Nginx configuration with SSL
# ====================================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Restoring full production Nginx configuration..."
echo ""

cd "$INSTALL_PATH"

# Check if SSL certificates exist
SSL_CERT="/etc/letsencrypt/live/mimiccash.com/fullchain.pem"
SSL_KEY="/etc/letsencrypt/live/mimiccash.com/privkey.pem"

if [[ ! -f "$SSL_CERT" ]] || [[ ! -f "$SSL_KEY" ]]; then
    echo "❌ SSL certificates not found!"
    echo "   Expected: $SSL_CERT"
    echo "   Expected: $SSL_KEY"
    echo ""
    echo "   Please install SSL certificates first:"
    echo "   sudo certbot --nginx -d mimiccash.com -d www.mimiccash.com"
    exit 1
fi

echo "✅ SSL certificates found"
echo ""

# Backup current config
if [[ -f /etc/nginx/nginx.conf ]]; then
    BACKUP_FILE="/etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)"
    sudo cp /etc/nginx/nginx.conf "$BACKUP_FILE"
    echo "✅ Backed up current config to: $BACKUP_FILE"
fi

# Copy production config
echo "Installing production configuration..."
sudo cp "$INSTALL_PATH/nginx.conf.production" /etc/nginx/nginx.conf

# Verify SSL paths are correct (they should already be in the config)
echo "Verifying SSL certificate paths..."
if grep -q "/etc/letsencrypt/live/mimiccash.com/fullchain.pem" /etc/nginx/nginx.conf; then
    echo "✅ SSL certificate paths are correct"
else
    echo "⚠️  Warning: SSL paths might need adjustment"
fi

# Test configuration
echo ""
echo "Testing Nginx configuration..."
if sudo nginx -t; then
    echo "✅ Nginx configuration is valid"
    echo ""
    echo "Reloading Nginx..."
    sudo systemctl reload nginx
    echo "✅ Nginx reloaded with production configuration"
else
    echo "❌ Nginx configuration has errors"
    sudo nginx -t
    echo ""
    echo "⚠️  Restoring backup..."
    if [[ -n "$BACKUP_FILE" ]] && [[ -f "$BACKUP_FILE" ]]; then
        sudo cp "$BACKUP_FILE" /etc/nginx/nginx.conf
        sudo systemctl reload nginx
        echo "✅ Backup restored"
    fi
    exit 1
fi

echo ""
echo "✅ Production configuration restored!"
echo ""
echo "Features enabled:"
echo "  ✓ HTTPS (SSL/TLS)"
echo "  ✓ HTTP → HTTPS redirect"
echo "  ✓ Rate limiting"
echo "  ✓ WebSocket support"
echo "  ✓ TradingView webhook (port 80/443)"
echo "  ✓ Security headers"
echo "  ✓ Static file serving"
echo ""
echo "Test your site:"
echo "  curl https://mimiccash.com/health"
echo "  curl https://www.mimiccash.com/health"
echo ""
