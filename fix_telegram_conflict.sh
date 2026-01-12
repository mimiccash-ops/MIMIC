#!/bin/bash
# =============================================================================
# Fix Telegram Bot Conflict - Stop all instances and restart cleanly
# =============================================================================

echo "🔧 Fixing Telegram Bot Conflicts..."
echo ""

# 1. Stop all services
echo "[1/5] Stopping all services..."
sudo systemctl stop mimic 2>/dev/null
sudo systemctl stop mimic-worker 2>/dev/null

# 2. Kill any remaining processes
echo "[2/5] Killing remaining processes..."
sudo pkill -9 -f "gunicorn.*app:app" 2>/dev/null
sudo pkill -9 -f "python.*worker.py" 2>/dev/null
sudo pkill -9 -f "python.*telegram" 2>/dev/null
sleep 2

# 3. Verify all killed
echo "[3/5] Verifying all processes stopped..."
REMAINING=$(ps aux | grep -E "gunicorn|worker.py" | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  Warning: $REMAINING processes still running"
    ps aux | grep -E "gunicorn|worker.py" | grep -v grep
else
    echo "✅ All processes stopped"
fi

# 4. Start services
echo "[4/5] Starting services..."
sudo systemctl start mimic
sleep 3
sudo systemctl start mimic-worker

# 5. Check status
echo "[5/5] Checking service status..."
echo ""
echo "=== MIMIC Service ==="
sudo systemctl status mimic --no-pager | head -15
echo ""
echo "=== MIMIC Worker Service ==="
sudo systemctl status mimic-worker --no-pager | head -15

echo ""
echo "✅ Done! Check logs with:"
echo "   tail -f /var/www/mimic/logs/error.log"
echo "   journalctl -u mimic-worker -f"
