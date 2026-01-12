# Telegram Bot Conflict - FIXED! 🎉

## What Was Wrong

The **Telegram bot was starting in TWO places**:
1. ❌ Flask app (Gunicorn) - shouldn't be running here
2. ✅ Worker - correct place

This caused **409 Conflict** errors because Telegram doesn't allow multiple `getUpdates` requests from the same bot.

## What I Fixed

Updated `telegram_bot.py` to check for Gunicorn **BEFORE** creating the bot handler, not after. Now the Flask app will skip the bot entirely and return `None`.

## Deploy the Fix on Your VPS

```bash
# SSH into your VPS
ssh root@38.180.147.102

# Go to your directory
cd /var/www/mimic

# Pull the latest fix
git fetch origin && git reset --hard origin/main

# Install worker service (if not already done)
sudo cp mimic-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mimic-worker

# Stop everything
sudo systemctl stop mimic
sudo systemctl stop mimic-worker
sudo pkill -9 -f "gunicorn.*app:app"
sudo pkill -9 -f "python.*worker.py"
sleep 5

# Start clean
sudo systemctl start mimic
sleep 3
sudo systemctl start mimic-worker

# Check both are running
sudo systemctl status mimic --no-pager | head -10
sudo systemctl status mimic-worker --no-pager | head -10

# Watch logs - you should see NO more 409 Conflict errors!
journalctl -u mimic-worker -f
```

## What You Should See

### Flask App (Gunicorn):
```
INFO:TelegramBot:🤖 Skipping Telegram bot in Gunicorn (will run in Worker only)
INFO:TelegramBot:   Bot notifications will be handled by Worker process
```

### Worker:
```
INFO:TelegramBot:✅ Telegram Bot started (basic commands only)
INFO:ARQ.Worker:✅ Telegram Bot started in Worker (sole instance)
INFO:TelegramBot:🤖 Telegram bot is now running
```

**No 409 Conflict errors!**

## Verify It's Working

Send a webhook from TradingView:

```bash
curl -X POST -H "Content-Type: application/json" \
-d '{"passphrase": "mimiccashadmin", "symbol": "BTCUSDT", "action": "long"}' \
http://127.0.0.1:8000/webhook
```

You should see:
```json
{"action":"long","mode":"memory","status":"queued","strategy_id":1,"symbol":"BTCUSDT"}
```

Then check worker logs:
```bash
journalctl -u mimic-worker -f
```

You should see the worker processing the signal!

## Troubleshooting

### Still seeing 409 errors?

1. Make sure you stopped ALL instances:
   ```bash
   ps aux | grep -E "gunicorn|worker.py"
   sudo pkill -9 -f "python.*telegram"
   ```

2. Wait 60 seconds after killing for Telegram to release the session

3. Restart services

### Worker not processing signals?

Check Redis is running:
```bash
sudo systemctl status redis
redis-cli ping  # Should return PONG
```

### Need help?

Check logs:
```bash
# Flask app logs
tail -f /var/www/mimic/logs/error.log

# Worker logs
journalctl -u mimic-worker -f

# Both together
journalctl -u mimic -u mimic-worker -f
```
