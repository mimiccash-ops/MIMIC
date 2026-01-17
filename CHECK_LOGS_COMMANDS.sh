#!/bin/bash
# Commands to check worker logs on VPS
# Run these on the VPS: root@38.180.147.102

echo "=== Worker Log Locations ==="
echo "1. Systemd journal: journalctl -u mimic-worker -f"
echo "2. Worker stdout: tail -f /var/www/mimic/logs/worker_stdout.log"
echo "3. Worker stderr: tail -f /var/www/mimic/logs/worker_stderr.log"
echo "4. Worker JSON: tail -f /var/www/mimic/logs/worker.json"
echo "5. App logs: tail -f /var/www/mimic/logs/app.log"
echo ""

echo "=== Checking Recent Worker Logs ==="
sudo journalctl -u mimic-worker -n 50 --no-pager | tail -30

echo ""
echo "=== Checking for Error Messages ==="
cd /var/www/mimic
tail -100 logs/app.log 2>/dev/null | grep -E "NO USERS|paused|expired|Quantity|Position too small|Worker executing" || echo "No matches found in app.log"

echo ""
echo "=== Checking Worker JSON Logs ==="
tail -50 logs/worker.json 2>/dev/null | tail -10 || echo "No worker.json logs found"

echo ""
echo "=== Real-time Monitoring (Press Ctrl+C to exit) ==="
echo "Run: sudo journalctl -u mimic-worker -f"
echo "Or: tail -f /var/www/mimic/logs/worker_stdout.log"
