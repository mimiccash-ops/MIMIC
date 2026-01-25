#!/bin/bash
#
# Check config.ini in host and container
# ======================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔍 Checking config.ini..."
echo ""

cd "$INSTALL_PATH"

# Check on host
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. config.ini on HOST"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if grep -q "^\[Settings\]" config.ini; then
    echo "✅ [Settings] section found on host"
    echo ""
    echo "Content:"
    sed -n '/^\[Settings\]/,/^\[/p' config.ini | head -5
else
    echo "❌ [Settings] section NOT found on host"
fi
echo ""

# Check in container
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. config.ini in CONTAINER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker compose exec -T worker grep -q "^\[Settings\]" /app/config.ini 2>/dev/null; then
    echo "✅ [Settings] section found in container"
    echo ""
    echo "Content:"
    docker compose exec -T worker sed -n '/^\[Settings\]/,/^\[/p' /app/config.ini 2>/dev/null | head -5
else
    echo "❌ [Settings] section NOT found in container"
    echo ""
    echo "Full config.ini in container:"
    docker compose exec -T worker cat /app/config.ini 2>/dev/null | tail -20
fi
echo ""

# Check if config.ini is mounted correctly
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Mount Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker compose exec -T worker test -f /app/config.ini 2>/dev/null; then
    echo "✅ config.ini is mounted in container"
    echo ""
    echo "File info:"
    docker compose exec -T worker ls -la /app/config.ini 2>/dev/null
else
    echo "❌ config.ini is NOT mounted in container"
fi
echo ""

# Fix if needed
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Fixing config.ini if needed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Ensure [Settings] section exists on host
if ! grep -q "^\[Settings\]" config.ini; then
    echo "Adding [Settings] section to host config.ini..."
    cat >> config.ini << 'EOF'

[Settings]
testnet = False
max_open_positions = 10
EOF
    echo "✅ Added [Settings] section"
else
    echo "✅ [Settings] section already exists on host"
fi

# Verify it's readable in container
echo ""
echo "Verifying in container..."
sleep 2
if docker compose exec -T worker grep -q "^\[Settings\]" /app/config.ini 2>/dev/null; then
    echo "✅ Container can read [Settings] section"
else
    echo "⚠️  Container still cannot read [Settings] section"
    echo "   Restarting worker to reload config..."
    docker compose restart worker
    sleep 3
    if docker compose exec -T worker grep -q "^\[Settings\]" /app/config.ini 2>/dev/null; then
        echo "✅ Container can now read [Settings] section"
    else
        echo "❌ Still cannot read [Settings] section"
        echo "   Check docker-compose.yml volume mount"
    fi
fi

echo ""
echo "✅ Check complete!"
echo ""
