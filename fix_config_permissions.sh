#!/bin/bash
#
# Fix config.ini permissions
# ===========================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing config.ini permissions..."
echo ""

cd "$INSTALL_PATH"

# Check current permissions
echo "Current permissions:"
ls -la config.ini
echo ""

# Fix permissions - make it readable by all
echo "Setting permissions to 644 (readable by all)..."
chmod 644 config.ini

echo "New permissions:"
ls -la config.ini
echo ""

# Verify in container
echo "Verifying in container..."
sleep 2

if docker compose exec -T worker test -r /app/config.ini 2>/dev/null; then
    echo "✅ File is readable in container"
    
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
        fi
    else
        echo "❌ File is still empty in container"
    fi
else
    echo "❌ File is still not readable in container"
    echo ""
    echo "Checking file in container:"
    docker compose exec -T worker ls -la /app/config.ini 2>/dev/null || echo "Cannot check"
fi

# Restart worker to apply changes
echo ""
echo "Restarting worker..."
docker compose restart worker
sleep 3

echo ""
echo "Checking worker logs..."
docker compose logs --tail=10 worker | grep -E "(Settings|KeyError|config.ini)" || echo "No relevant errors found"

echo ""
echo "✅ Permissions fix complete!"
echo ""
