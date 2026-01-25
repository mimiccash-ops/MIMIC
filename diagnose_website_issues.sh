#!/bin/bash
#
# Diagnose website issues (Internal Server Error, design problems)
# ===============================================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔍 Diagnosing website issues..."
echo ""

cd "$INSTALL_PATH"

# ============================================================================
# STEP 1: Check Application Status
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Checking Application Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check systemd service
if systemctl is-active --quiet mimic; then
    echo "✅ mimic.service is running"
else
    echo "❌ mimic.service is NOT running"
    echo "   Starting service..."
    sudo systemctl start mimic
    sleep 2
fi

# Check if Gunicorn is listening
if sudo ss -tlnp | grep -q ":8000"; then
    echo "✅ Gunicorn is listening on port 8000"
else
    echo "❌ Gunicorn is NOT listening on port 8000"
fi

# Test local connection
echo ""
echo "Testing local connection..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Application responds on localhost:8000"
    curl -s http://localhost:8000/health
else
    echo "❌ Application does NOT respond on localhost:8000"
fi

echo ""

# ============================================================================
# STEP 2: Check Application Logs
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Checking Application Logs (last 50 lines)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check systemd logs
echo "Systemd logs:"
sudo journalctl -u mimic -n 50 --no-pager | tail -20

echo ""
echo "Application error logs:"
if [[ -f "$INSTALL_PATH/logs/error.log" ]]; then
    tail -30 "$INSTALL_PATH/logs/error.log" 2>/dev/null || echo "No error.log found"
else
    echo "No error.log file found"
fi

echo ""

# ============================================================================
# STEP 3: Check Static Files
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Checking Static Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if static directory exists
if [[ -d "$INSTALL_PATH/static" ]]; then
    echo "✅ Static directory exists"
    
    # Check CSS files
    if [[ -f "$INSTALL_PATH/static/css/main.css" ]] || find "$INSTALL_PATH/static" -name "*.css" | head -1 | grep -q .; then
        echo "✅ CSS files found"
        find "$INSTALL_PATH/static" -name "*.css" | head -3
    else
        echo "❌ No CSS files found - this may cause design issues!"
        echo "   Run: npm run build (if using Tailwind CSS)"
    fi
    
    # Check JS files
    if find "$INSTALL_PATH/static" -name "*.js" | head -1 | grep -q .; then
        echo "✅ JS files found"
    else
        echo "⚠️  No JS files found"
    fi
else
    echo "❌ Static directory does NOT exist!"
fi

echo ""

# ============================================================================
# STEP 4: Check Nginx Configuration
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Checking Nginx Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if systemctl is-active --quiet nginx; then
    echo "✅ Nginx is running"
    
    # Test Nginx config
    if sudo nginx -t 2>&1 | grep -q "successful"; then
        echo "✅ Nginx configuration is valid"
    else
        echo "❌ Nginx configuration has errors:"
        sudo nginx -t
    fi
    
    # Check Nginx error logs
    echo ""
    echo "Nginx error logs (last 20 lines):"
    sudo tail -20 /var/log/nginx/error.log 2>/dev/null || echo "No error log found"
else
    echo "❌ Nginx is NOT running"
fi

echo ""

# ============================================================================
# STEP 5: Check Database Connection
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5: Checking Database Connection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check DATABASE_URL
if grep -q "DATABASE_URL" .env; then
    DB_URL=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2- | head -1)
    echo "DATABASE_URL found: ${DB_URL:0:50}..."
    
    # Try to connect
    if python3 -c "
import os
import sys
sys.path.insert(0, '$INSTALL_PATH')
from app import app, db
with app.app_context():
    try:
        db.engine.connect()
        print('✅ Database connection successful')
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        sys.exit(1)
" 2>/dev/null; then
        echo "✅ Database is accessible"
    else
        echo "❌ Database connection test failed"
    fi
else
    echo "⚠️  DATABASE_URL not found in .env"
fi

echo ""

# ============================================================================
# STEP 6: Check Frontend Build
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 6: Checking Frontend Build"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ -f "$INSTALL_PATH/package.json" ]]; then
    echo "✅ package.json found"
    
    # Check if node_modules exists
    if [[ -d "$INSTALL_PATH/node_modules" ]]; then
        echo "✅ node_modules exists"
    else
        echo "⚠️  node_modules not found - run: npm install"
    fi
    
    # Check if CSS was built
    if find "$INSTALL_PATH/static" -name "*.css" | grep -q "main\|app\|style"; then
        echo "✅ CSS files found in static/"
    else
        echo "❌ No CSS files found - frontend may not be built"
        echo "   Run: npm run build"
    fi
else
    echo "⚠️  No package.json found (frontend may not be needed)"
fi

echo ""

# ============================================================================
# SUMMARY AND RECOMMENDATIONS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SUMMARY AND RECOMMENDATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Common fixes for Internal Server Error:"
echo "  1. Check application logs: sudo journalctl -u mimic -f"
echo "  2. Rebuild frontend: cd $INSTALL_PATH && npm run build"
echo "  3. Restart services: sudo systemctl restart mimic nginx"
echo "  4. Check database: Ensure PostgreSQL is running and accessible"
echo "  5. Check permissions: ls -la $INSTALL_PATH/static"
echo ""
echo "Common fixes for design issues:"
echo "  1. Rebuild CSS: cd $INSTALL_PATH && npm run build"
echo "  2. Check Nginx static file serving: sudo nginx -t"
echo "  3. Clear browser cache"
echo "  4. Check static file permissions: chmod -R 755 $INSTALL_PATH/static"
echo ""
