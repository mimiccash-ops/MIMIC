#!/bin/bash
#
# Fix worker permissions for logs directory
# ========================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing worker permissions..."
echo ""

cd "$INSTALL_PATH"

# Create logs directory if it doesn't exist
echo "Creating logs directory on host..."
mkdir -p logs
chmod 777 logs

# Create logs subdirectories if needed
mkdir -p logs/avatars logs/music 2>/dev/null || true
chmod -R 777 logs

echo "✅ Host logs directory permissions set"
echo ""

# Stop worker to fix permissions
echo "Stopping worker..."
docker compose stop worker 2>/dev/null || true

# Fix permissions in Docker container by running as root
echo "Fixing permissions in Docker container (as root)..."
docker compose run --rm --user root --entrypoint="sh" worker -c "
    mkdir -p /app/logs
    chown -R brainapp:brainapp /app/logs
    chmod -R 777 /app/logs
    ls -la /app/ | grep logs
" 2>&1 || true

# Alternative: Use docker exec if container is running
if docker compose ps worker | grep -q "Up\|Restarting"; then
    echo "Fixing permissions in running container..."
    docker compose exec --user root worker sh -c "
        mkdir -p /app/logs
        chown -R brainapp:brainapp /app/logs
        chmod -R 777 /app/logs
    " 2>/dev/null || true
fi

# Restart worker
echo ""
echo "Starting worker..."
docker compose up -d worker

# Wait a bit and check status
sleep 5

echo ""
echo "Checking worker status..."
if docker compose ps worker | grep -q "Up"; then
    echo "✅ Worker is running"
    echo ""
    echo "Checking worker logs (last 10 lines)..."
    docker compose logs --tail=10 worker
else
    echo "❌ Worker is still having issues"
    echo ""
    echo "Checking logs..."
    docker compose logs --tail=30 worker
    echo ""
    echo "⚠️  If permission errors persist, try:"
    echo "  1. Check logs directory: ls -la logs/"
    echo "  2. Manually fix: sudo chmod -R 777 logs/"
    echo "  3. Rebuild worker: docker compose up -d --build worker"
fi

echo ""
echo "✅ Permissions fix complete!"
echo ""
