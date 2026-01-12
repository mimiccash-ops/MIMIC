# MIMIC Worker Setup Guide

## Problem
The Flask web app receives webhook signals and queues them, but **without a worker process running**, the trades are never executed!

## Quick Start (Testing)

### Option 1: Run worker manually in a screen session

```bash
# Connect to your VPS
cd /var/www/mimic

# Make the script executable
chmod +x run_worker.sh

# Start a screen session for the worker
screen -S mimic-worker

# Run the worker
./run_worker.sh

# Detach from screen: Press Ctrl+A, then D
# To reattach: screen -r mimic-worker
```

### Option 2: Run worker in background with nohup

```bash
cd /var/www/mimic
source venv/bin/activate
nohup python3 worker.py > logs/worker.log 2>&1 &

# Check it's running
ps aux | grep worker.py

# View logs
tail -f logs/worker.log
```

## Production Setup (Recommended)

### Install Worker as Systemd Service

```bash
# Copy the service file
sudo cp mimic-worker.service /etc/systemd/system/

# Edit paths if your installation is not in /var/www/mimic
sudo nano /etc/systemd/system/mimic-worker.service

# Reload systemd
sudo systemctl daemon-reload

# Enable worker to start on boot
sudo systemctl enable mimic-worker

# Start the worker
sudo systemctl start mimic-worker

# Check status
sudo systemctl status mimic-worker

# View logs
journalctl -u mimic-worker -f
```

### Managing Both Services

```bash
# Start both services
sudo systemctl start mimic
sudo systemctl start mimic-worker

# Restart both services
sudo systemctl restart mimic mimic-worker

# Check status of both
sudo systemctl status mimic mimic-worker

# View logs from both
journalctl -u mimic -u mimic-worker -f
```

## Verification

After starting the worker, send a test webhook from TradingView. You should see logs like:

```
INFO:ARQ.Worker:📥 Processing signal: LONG ASRUSDT
INFO:ARQ.Worker:👥 Found 3 subscribers for strategy_id=1
INFO:ARQ.Worker:🔄 Executing trade for user: john@example.com
INFO:ARQ.Worker:✅ Trade executed on Binance: LONG ASRUSDT
```

## Troubleshooting

### Worker not processing signals?

1. Check if Redis is running:
   ```bash
   sudo systemctl status redis
   ```

2. Check worker logs:
   ```bash
   tail -f /var/www/mimic/logs/worker.log
   # or
   journalctl -u mimic-worker -f
   ```

3. Check if worker process is running:
   ```bash
   ps aux | grep worker.py
   ```

### Redis connection issues?

Make sure Redis is accessible:
```bash
redis-cli ping
# Should return: PONG
```

If Redis is not running:
```bash
sudo systemctl start redis
sudo systemctl enable redis
```

## Architecture

```
TradingView Webhook
    ↓
Flask App (app.py) → Queue Signal to Redis
    ↓
Worker (worker.py) → Process Signal → Execute Trades on Exchanges
```

Both processes must be running for trades to execute!
