#!/bin/bash
#
# Debug config.ini in container
# ==============================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔍 Debugging config.ini..."
echo ""

cd "$INSTALL_PATH"

# Check on host
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. config.ini on HOST (first 50 lines)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
head -50 config.ini
echo ""

# Check in container
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. config.ini in CONTAINER (first 50 lines)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose exec -T worker head -50 /app/config.ini 2>/dev/null || echo "Cannot read file"
echo ""

# Check file size
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. File sizes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Host: $(wc -l < config.ini) lines, $(wc -c < config.ini) bytes"
CONTAINER_LINES=$(docker compose exec -T worker wc -l < /app/config.ini 2>/dev/null || echo "0")
CONTAINER_BYTES=$(docker compose exec -T worker wc -c < /app/config.ini 2>/dev/null || echo "0")
echo "Container: $CONTAINER_LINES lines, $CONTAINER_BYTES bytes"
echo ""

# Search for [Settings]
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Searching for [Settings]"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "On host:"
grep -n "\[Settings\]" config.ini || echo "NOT FOUND"
echo ""
echo "In container:"
docker compose exec -T worker grep -n "\[Settings\]" /app/config.ini 2>/dev/null || echo "NOT FOUND"
echo ""

# Check all sections
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. All sections in container"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose exec -T worker grep "^\[" /app/config.ini 2>/dev/null || echo "No sections found"
echo ""

# Check file encoding
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. File encoding"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Host:"
file config.ini
echo ""
echo "Container:"
docker compose exec -T worker file /app/config.ini 2>/dev/null || echo "Cannot check"
echo ""

# Try to read with Python in container
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. Testing with Python ConfigParser"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose exec -T worker python3 -c "
import configparser
config = configparser.ConfigParser()
try:
    config.read('/app/config.ini')
    print('Sections found:', config.sections())
    if 'Settings' in config.sections():
        print('✅ [Settings] section exists')
        print('Keys:', list(config['Settings'].keys()))
    else:
        print('❌ [Settings] section NOT found')
        print('Available sections:', config.sections())
except Exception as e:
    print(f'Error: {e}')
" 2>/dev/null || echo "Python test failed"
echo ""

echo "✅ Debug complete!"
echo ""
