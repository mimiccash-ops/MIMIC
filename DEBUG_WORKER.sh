#!/bin/bash
# Debug script to find worker error
# Run this on the VPS

cd /var/www/mimic

echo "=== Checking worker stderr logs ==="
tail -50 logs/worker_stderr.log 2>/dev/null || echo "No worker_stderr.log found"

echo ""
echo "=== Checking worker stdout logs ==="
tail -50 logs/worker_stdout.log 2>/dev/null || echo "No worker_stdout.log found"

echo ""
echo "=== Testing worker import manually ==="
source venv/bin/activate
python -c "from worker import WorkerSettings; print('WorkerSettings imported OK')" 2>&1

echo ""
echo "=== Testing trading_engine import ==="
python -c "import trading_engine; print('trading_engine imported OK')" 2>&1

echo ""
echo "=== Testing ARQ worker startup (will fail but show error) ==="
timeout 10 /var/www/mimic/venv/bin/arq worker.WorkerSettings 2>&1 | head -30 || true
