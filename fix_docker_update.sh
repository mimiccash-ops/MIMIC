#!/bin/bash
#
# Fix Docker Update Issues
# ========================
#

set -e

cd /var/www/mimic

echo "🔧 Fixing Docker update issues..."

# 1. Fix git local changes
echo "1. Fixing git local changes..."
git stash || true
git pull origin main || git pull

# 2. Check if PostgreSQL is running on host
echo "2. Checking PostgreSQL on host..."
if systemctl is-active --quiet postgresql; then
    echo "⚠️  PostgreSQL is running on host. Stopping it for Docker..."
    systemctl stop postgresql
    systemctl disable postgresql
fi

# 3. Check and stop services using ports
echo "3. Checking ports..."

# Check PostgreSQL
if systemctl is-active --quiet postgresql; then
    echo "⚠️  PostgreSQL is running on host. Stopping it for Docker..."
    systemctl stop postgresql
    systemctl disable postgresql
fi

# Check Redis
if systemctl is-active --quiet redis-server || systemctl is-active --quiet redis; then
    echo "⚠️  Redis is running on host. Stopping it for Docker..."
    systemctl stop redis-server 2>/dev/null || systemctl stop redis 2>/dev/null
    systemctl disable redis-server 2>/dev/null || systemctl disable redis 2>/dev/null
fi

# Check if ports are still in use
if lsof -i :5432 > /dev/null 2>&1; then
    echo "⚠️  Port 5432 is still in use. Finding process..."
    lsof -i :5432
fi

if lsof -i :6379 > /dev/null 2>&1; then
    echo "⚠️  Port 6379 is still in use. Finding process..."
    lsof -i :6379
fi

# 4. Fix config.ini - add missing [Telegram] section if needed
echo "3. Checking config.ini..."
if ! grep -q "^\[Telegram\]" config.ini; then
    echo "Adding [Telegram] section to config.ini..."
    cat >> config.ini << 'EOF'

[Telegram]
bot_token = 
chat_id = 
enabled = False
EOF
    echo "✅ Added [Telegram] section"
fi

# 5. Remove orphan containers
echo "4. Removing orphan containers..."
docker compose down --remove-orphans 2>/dev/null || true

echo ""
echo "✅ Fixes applied!"
echo ""
echo "Now try:"
echo "  docker compose up -d"
echo ""
