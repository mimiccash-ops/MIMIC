#!/bin/bash
#
# Test MIMIC services
# ==================
#

set -e

echo "🧪 Testing MIMIC services..."
echo ""

# Test Gunicorn
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Testing Gunicorn (port 8000)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Gunicorn is responding"
    curl -s http://localhost:8000/health
else
    echo "❌ Gunicorn is NOT responding"
fi
echo ""

# Test Nginx
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Testing Nginx (port 80)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if curl -s http://localhost/health > /dev/null; then
    echo "✅ Nginx is responding"
    curl -s http://localhost/health
else
    echo "❌ Nginx is NOT responding"
fi
echo ""

# Test external access (if domain is configured)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Testing external access (mimiccash.com)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if curl -s -o /dev/null -w "%{http_code}" http://mimiccash.com/health | grep -q "200"; then
    echo "✅ External access is working"
    curl -s http://mimiccash.com/health
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://mimiccash.com/health || echo "000")
    echo "⚠️  External access returned HTTP $HTTP_CODE"
    echo "   (This might be normal if DNS is not configured or firewall is blocking)"
fi
echo ""

# Check service statuses
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
systemctl is-active --quiet mimic && echo "✅ mimic.service: active" || echo "❌ mimic.service: inactive"
systemctl is-active --quiet nginx && echo "✅ nginx.service: active" || echo "❌ nginx.service: inactive"
echo ""

# Check ports
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Port Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if sudo ss -tlnp | grep -q ":8000"; then
    echo "✅ Port 8000 is listening (Gunicorn)"
else
    echo "❌ Port 8000 is NOT listening"
fi

if sudo ss -tlnp | grep -q ":80"; then
    echo "✅ Port 80 is listening (Nginx)"
else
    echo "❌ Port 80 is NOT listening"
fi
echo ""

echo "✅ Testing complete!"
echo ""
