#!/bin/bash
#
# Force fix config.ini mount
# ===========================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Force fixing config.ini mount..."
echo ""

cd "$INSTALL_PATH"

# Check if config.ini exists
if [[ ! -f config.ini ]]; then
    echo "❌ config.ini not found at $INSTALL_PATH/config.ini"
    exit 1
fi

echo "✅ config.ini exists at: $(pwd)/config.ini"
echo "   Size: $(wc -c < config.ini) bytes"
echo ""

# Check docker-compose.yml
echo "Checking docker-compose.yml volume mount..."
if grep -A 1 "worker:" docker-compose.yml | grep -q "config.ini"; then
    echo "✅ Volume mount found in docker-compose.yml"
else
    echo "⚠️  Volume mount might be missing"
fi
echo ""

# Stop and remove worker
echo "Stopping worker..."
docker compose stop worker 2>/dev/null || true

echo "Removing worker container..."
docker compose rm -f worker 2>/dev/null || true

# Check absolute path
ABSOLUTE_PATH=$(realpath config.ini)
echo "Absolute path to config.ini: $ABSOLUTE_PATH"
echo ""

# Verify docker-compose.yml has the mount
echo "Verifying docker-compose.yml..."
if ! grep -q "./config.ini:/app/config.ini" docker-compose.yml; then
    echo "❌ Volume mount not found in docker-compose.yml!"
    echo "   Please check docker-compose.yml worker section"
    exit 1
fi

# Recreate worker
echo "Recreating worker container..."
docker compose up -d worker

# Wait for container
echo "Waiting for container to start..."
sleep 5

# Check if file exists now
echo ""
echo "Checking if config.ini is accessible in container..."
if docker compose exec -T worker test -f /app/config.ini 2>/dev/null; then
    echo "✅ config.ini file exists in container"
    
    # Check content
    echo ""
    echo "Checking file content..."
    CONTAINER_SIZE=$(docker compose exec -T worker wc -c < /app/config.ini 2>/dev/null || echo "0")
    echo "Container file size: $CONTAINER_SIZE bytes"
    
    if [[ "$CONTAINER_SIZE" -gt 0 ]]; then
        echo "✅ File has content"
        
        # Check for [Settings]
        echo ""
        echo "Checking for [Settings] section..."
        if docker compose exec -T worker grep -q "^\[Settings\]" /app/config.ini 2>/dev/null; then
            echo "✅ [Settings] section found!"
            echo ""
            echo "Content:"
            docker compose exec -T worker sed -n '/^\[Settings\]/,/^\[/p' /app/config.ini 2>/dev/null | head -5
        else
            echo "❌ [Settings] section still not found"
            echo ""
            echo "First 20 lines of container file:"
            docker compose exec -T worker head -20 /app/config.ini 2>/dev/null
        fi
    else
        echo "❌ File is empty in container"
    fi
else
    echo "❌ config.ini still not accessible in container"
    echo ""
    echo "Checking /app directory:"
    docker compose exec -T worker ls -la /app/ 2>/dev/null | head -10 || echo "Cannot list /app"
    echo ""
    echo "Checking mounts:"
    docker inspect brain_capital_worker 2>/dev/null | grep -A 20 "Mounts" || echo "Cannot inspect container"
fi

echo ""
echo "Checking worker logs..."
docker compose logs --tail=15 worker

echo ""
echo "✅ Fix complete!"
echo ""
