#!/bin/bash
#
# Fix mimic.service startup issues
# =================================
#

set -e

INSTALL_PATH="/var/www/mimic"

echo "🔧 Fixing mimic.service..."
echo ""

cd "$INSTALL_PATH"

# ============================================================================
# STEP 1: Check Service Status
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Checking Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

systemctl status mimic --no-pager -l || true
echo ""

# ============================================================================
# STEP 2: Check Recent Logs
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Checking Recent Logs (last 50 lines)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sudo journalctl -u mimic -n 50 --no-pager | tail -30
echo ""

# ============================================================================
# STEP 3: Check for Errors
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Checking for Errors"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ERRORS=$(sudo journalctl -u mimic -n 100 --no-pager | grep -iE "(error|exception|traceback|failed|fatal)" | tail -10)

if [[ -n "$ERRORS" ]]; then
    echo "Found errors:"
    echo "$ERRORS"
else
    echo "No recent errors found"
fi

echo ""

# ============================================================================
# STEP 4: Check Application Logs
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Checking Application Logs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ -f "$INSTALL_PATH/logs/error.log" ]]; then
    echo "Error log (last 20 lines):"
    tail -20 "$INSTALL_PATH/logs/error.log" 2>/dev/null || echo "Cannot read error.log"
else
    echo "No error.log found"
fi

echo ""

if [[ -f "$INSTALL_PATH/logs/stderr.log" ]]; then
    echo "Stderr log (last 20 lines):"
    tail -20 "$INSTALL_PATH/logs/stderr.log" 2>/dev/null || echo "Cannot read stderr.log"
else
    echo "No stderr.log found"
fi

echo ""

# ============================================================================
# STEP 5: Check Port and Process
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5: Checking Port and Process"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if port 8000 is in use
if sudo ss -tlnp | grep -q ":8000"; then
    echo "✅ Port 8000 is in use:"
    sudo ss -tlnp | grep ":8000"
else
    echo "❌ Port 8000 is NOT in use"
    echo "   Service may have failed to start"
fi

echo ""

# Check for gunicorn processes
if pgrep -f "gunicorn.*mimic" > /dev/null; then
    echo "✅ Gunicorn process found:"
    ps aux | grep "gunicorn.*mimic" | grep -v grep
else
    echo "❌ No Gunicorn process found"
fi

echo ""

# ============================================================================
# STEP 6: Try to Start Service
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 6: Attempting to Start Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Stop service first
echo "Stopping service..."
sudo systemctl stop mimic 2>/dev/null || true
sleep 2

# Start service
echo "Starting service..."
sudo systemctl start mimic
sleep 5

# Check status
if systemctl is-active --quiet mimic; then
    echo "✅ Service started successfully"
    
    # Wait a bit and check port
    sleep 3
    if sudo ss -tlnp | grep -q ":8000"; then
        echo "✅ Gunicorn is listening on port 8000"
        
        # Test connection
        if curl -s http://localhost:8000/health > /dev/null; then
            echo "✅ Application responds to health check"
            curl -s http://localhost:8000/health
        else
            echo "⚠️  Application does not respond to health check"
        fi
    else
        echo "⚠️  Service is active but port 8000 is not listening"
    fi
else
    echo "❌ Service failed to start"
    echo ""
    echo "Recent logs:"
    sudo journalctl -u mimic -n 30 --no-pager
fi

echo ""
echo "✅ Service fix complete!"
echo ""
