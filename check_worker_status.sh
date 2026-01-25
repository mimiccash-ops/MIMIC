#!/bin/bash
#
# Check worker status
# ===================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔍 Checking worker status..."
echo ""

cd "$INSTALL_PATH"

# Check container status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Container Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose ps worker
echo ""

# Check if worker is running
if docker compose ps worker | grep -q "Up"; then
    echo "✅ Worker container is running"
    
    # Check recent logs
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "2. Recent Logs (last 20 lines)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    docker compose logs --tail=20 worker
    
    # Check for errors
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "3. Error Check"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if docker compose logs worker 2>&1 | grep -iE "(error|exception|traceback|keyerror)" | tail -5; then
        echo "⚠️  Found errors in logs"
    else
        echo "✅ No errors found"
    fi
    
    # Check if config.ini is readable
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "4. Config.ini Check"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if docker compose exec -T worker test -r /app/config.ini 2>/dev/null; then
        echo "✅ config.ini is readable"
        if docker compose exec -T worker grep -q "^\[Settings\]" /app/config.ini 2>/dev/null; then
            echo "✅ [Settings] section found"
        else
            echo "❌ [Settings] section not found"
        fi
    else
        echo "❌ config.ini is not readable"
    fi
else
    echo "❌ Worker container is NOT running"
    echo ""
    echo "Checking logs..."
    docker compose logs --tail=30 worker
fi

echo ""
echo "✅ Status check complete!"
echo ""
