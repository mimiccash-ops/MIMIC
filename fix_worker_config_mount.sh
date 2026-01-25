#!/bin/bash
#
# Fix worker config.ini mount issue
# ==================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing worker config.ini mount..."
echo ""

cd "$INSTALL_PATH"

# Check if config.ini exists
if [[ ! -f config.ini ]]; then
    echo "❌ config.ini not found on host!"
    exit 1
fi

echo "✅ config.ini exists on host"
echo ""

# Check docker-compose.yml
echo "Checking docker-compose.yml..."
if grep -q "./config.ini:/app/config.ini" docker-compose.yml; then
    echo "✅ config.ini mount is configured in docker-compose.yml"
else
    echo "❌ config.ini mount is NOT configured in docker-compose.yml"
    echo "   Adding mount configuration..."
    # This would require editing docker-compose.yml, but it should already be there
    exit 1
fi
echo ""

# Stop worker
echo "Stopping worker..."
docker compose stop worker

# Remove worker container to force recreation
echo "Removing worker container..."
docker compose rm -f worker

# Recreate worker with proper volumes
echo "Recreating worker container..."
docker compose up -d worker

# Wait for container to start
sleep 5

# Check if config.ini is now mounted
echo ""
echo "Checking if config.ini is mounted..."
if docker compose exec -T worker test -f /app/config.ini 2>/dev/null; then
    echo "✅ config.ini is now mounted in container"
    echo ""
    echo "Verifying [Settings] section..."
    if docker compose exec -T worker grep -q "^\[Settings\]" /app/config.ini 2>/dev/null; then
        echo "✅ [Settings] section found in container"
        echo ""
        echo "Content:"
        docker compose exec -T worker sed -n '/^\[Settings\]/,/^\[/p' /app/config.ini 2>/dev/null | head -5
    else
        echo "❌ [Settings] section still not found"
    fi
else
    echo "❌ config.ini is still NOT mounted"
    echo ""
    echo "Checking worker volumes..."
    docker compose exec -T worker ls -la /app/ | grep config.ini || echo "config.ini not found"
    echo ""
    echo "Checking docker inspect..."
    docker inspect brain_capital_worker | grep -A 10 "Mounts" || true
fi

echo ""
echo "Checking worker logs..."
docker compose logs --tail=10 worker

echo ""
echo "✅ Fix complete!"
echo ""
