#!/bin/bash
#
# Check Docker services status and logs
# ====================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔍 Checking Docker services..."
echo ""

cd "$INSTALL_PATH"

# Check container status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Container Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose ps
echo ""

# Check worker logs
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Worker Logs (last 50 lines)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker compose ps | grep -q "brain_capital_worker"; then
    docker compose logs --tail=50 worker 2>&1 || true
else
    echo "⚠️  Worker container not found"
fi
echo ""

# Check web container (if exists)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Web Container Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker compose ps | grep -q "brain_capital_web"; then
    echo "✅ Web container exists"
    docker compose ps web
    echo ""
    echo "Web logs (last 20 lines):"
    docker compose logs --tail=20 web 2>&1 || true
else
    echo "ℹ️  Web container not running (using systemd mimic.service instead)"
fi
echo ""

# Check database connection
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Database Connection Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker compose ps | grep -q "brain_capital_db.*healthy"; then
    echo "✅ Database container is healthy"
    echo ""
    echo "Testing connection..."
    docker compose exec -T db psql -U brain_capital -d brain_capital -c "SELECT 1;" 2>&1 || echo "⚠️  Connection test failed"
else
    echo "❌ Database container is not healthy"
fi
echo ""

# Check Redis connection
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Redis Connection Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker compose ps | grep -q "brain_capital_redis.*healthy"; then
    echo "✅ Redis container is healthy"
    echo ""
    echo "Testing connection..."
    docker compose exec -T redis redis-cli ping 2>&1 || echo "⚠️  Connection test failed"
else
    echo "❌ Redis container is not healthy"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To fix worker issues:"
echo "  1. Check worker logs: docker compose logs -f worker"
echo "  2. Restart worker: docker compose restart worker"
echo "  3. Rebuild worker: docker compose up -d --build worker"
echo ""
