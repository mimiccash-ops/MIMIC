# Quick Deployment Guide - Telegram Bot Fix

## 🚀 TL;DR

```bash
# 1. Stop everything
sudo systemctl stop mimic mimic-worker 2>/dev/null
pkill -f "telegram_bot|run_bot.py"
rm -f /tmp/mimic_telegram_bot.lock

# 2. Update files (already done in your codebase)
cd /var/www/mimic
chmod +x run_bot.py

# 3. Install services
sudo cp mimic.service /etc/systemd/system/
sudo cp mimic-worker.service /etc/systemd/system/
sudo cp mimic-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# 4. Enable services
sudo systemctl enable mimic mimic-worker mimic-bot

# 5. Start services IN ORDER
sudo systemctl start mimic          # Web server
sudo systemctl start mimic-worker   # Task processor
sudo systemctl start mimic-bot      # Telegram bot

# 6. Verify
sudo systemctl status mimic mimic-worker mimic-bot
journalctl -u mimic-bot -f          # Watch bot logs

# 7. Test bot in Telegram
# Send to your bot: /start
# Expected: Welcome message
```

## ✅ What Changed

| Component | Before | After |
|-----------|--------|-------|
| **Web Server** | Tried to start bot ❌ | Web only ✅ |
| **Worker** | Tried to start bot ❌ | Tasks only ✅ |
| **Bot** | N/A | **NEW:** Separate service ✅ |

## 📋 Files You Need

All files already created in your codebase:

- ✅ `run_bot.py` - Standalone bot runner
- ✅ `mimic-bot.service` - Bot systemd service
- ✅ `mimic-worker.service` - Worker systemd service
- ✅ `mimic.service` - Updated web service (no bot)
- ✅ `app.py` - Updated (bot removed)
- ✅ `worker.py` - Updated (bot removed)

## 🎯 Critical Points

1. **Service Order Matters**: Start web → worker → bot
2. **Only ONE Bot Instance**: The lock file ensures this
3. **Scale Freely**: You can now use `--workers 4` in Gunicorn
4. **Independent Restarts**: Restart web/worker/bot separately

## 🔍 Verify Success

```bash
# All services should be "active (running)"
sudo systemctl status mimic mimic-worker mimic-bot

# No 409 errors in bot logs
journalctl -u mimic-bot -n 50 | grep -i conflict

# Bot responds in Telegram
# Send: /start
# Should reply with welcome message
```

## 🆘 If Something Goes Wrong

```bash
# Check bot status
sudo systemctl status mimic-bot

# View recent errors
journalctl -u mimic-bot -n 100

# Restart bot
sudo systemctl restart mimic-bot

# Clear lock and restart
rm -f /tmp/mimic_telegram_bot.lock
sudo systemctl restart mimic-bot
```

## 📱 Test Telegram Bot

1. Open Telegram
2. Find your bot (search by username)
3. Send: `/start`
4. Expected: Welcome message with your user ID
5. Send: `/status`
6. Expected: Bot status, time, OTP status

## 🎉 Done!

Your Telegram bot now runs as a **singleton service**, completely isolated from Gunicorn workers.

**No more 409 Conflicts!** 🎊

For detailed docs, see: `TELEGRAM_BOT_ARCHITECTURE.md`
