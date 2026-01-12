# Telegram Bot Architecture - Deployment Guide

## 🎯 Problem Solved

**Issue**: `System Error: Exception happened while polling for updates` with 409 Conflict errors

**Root Cause**: Multiple Gunicorn worker processes were each trying to start the Telegram bot, causing conflicts since Telegram only allows ONE polling connection per token.

**Solution**: Complete architectural separation - the bot now runs as an independent service.

---

## 🏗️ New Architecture

### Service Separation

```
┌─────────────────────────────────────────────────────────────┐
│                    MIMIC PLATFORM                             │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   WEB SERVER │ │    WORKER    │ │  TELEGRAM BOT│
    │  (Gunicorn)  │ │     (ARQ)    │ │  (Polling)   │
    └──────────────┘ └──────────────┘ └──────────────┘
    │  mimic.service  mimic-worker     mimic-bot.service
    │                  .service
    │
    ├─ Flask app
    ├─ WebSockets
    ├─ HTTP endpoints
    ├─ Multiple workers ✅
    └─ NO BOT (removed)
                     │
                     ├─ Redis queue
                     ├─ Cron jobs
                     ├─ DCA checks
                     ├─ Trailing SL
                     └─ NO BOT (removed)
                                    │
                                    ├─ Commands (/start, /help)
                                    ├─ Panic close (/panic_close_all)
                                    ├─ OTP verification
                                    ├─ File locking (singleton)
                                    └─ 409 conflict prevention
```

### Key Benefits

✅ **No More 409 Conflicts**: Only ONE process polls Telegram  
✅ **Scalable Web Server**: Scale Gunicorn workers without affecting the bot  
✅ **Independent Restarts**: Restart web/worker/bot independently  
✅ **Clean Separation**: Each service has one responsibility  
✅ **Better Debugging**: Isolated logs for each component  
✅ **Production Ready**: Industry-standard microservices pattern  

---

## 📦 Files Modified/Created

### Created Files

1. **`run_bot.py`** - Standalone bot runner script
   - Cross-platform file locking
   - Graceful shutdown handling
   - Database connection for commands
   - Trading engine integration for panic close

2. **`mimic-bot.service`** - Systemd service for bot
   - Runs `run_bot.py` as a daemon
   - Auto-restart on failure
   - Resource limits
   - Security hardening

3. **`mimic-worker.service`** - Systemd service for worker
   - Runs ARQ worker for background tasks
   - No bot initialization
   - Prometheus metrics on port 9091

### Modified Files

1. **`app.py`** (lines 254-308)
   - ❌ Removed: `init_telegram_bot()` call
   - ✅ Added: Comment explaining bot runs separately
   - Result: Web server focuses on HTTP/WebSocket only

2. **`worker.py`** (lines 195-247)
   - ❌ Removed: Bot initialization in startup()
   - ✅ Added: Comment explaining bot runs separately
   - Result: Worker focuses on task processing only

3. **`mimic.service`** (header comments)
   - ✅ Updated: Clarified it runs web server ONLY
   - ✅ Added: Architecture diagram in comments
   - ✅ Added: Deployment order instructions

### Unchanged Files

- **`telegram_bot.py`** - Bot logic remains the same (already had locking)
- **`telegram_notifier.py`** - Notifications still work (independent from polling)
- **`config.py`** - No changes needed

---

## 🚀 Deployment Instructions

### Step 1: Stop All Services

```bash
# Stop existing services
sudo systemctl stop mimic
sudo systemctl stop mimic-worker  # If exists

# Kill any lingering bot processes
pkill -f "telegram_bot"
pkill -f "run_bot.py"

# Clear lock file
rm -f /tmp/mimic_telegram_bot.lock
```

### Step 2: Update Code

```bash
cd /var/www/mimic

# Pull latest code (or copy the modified files)
git pull  # If using git

# Or manually copy these files:
# - run_bot.py
# - mimic-bot.service
# - mimic-worker.service
# - app.py (updated)
# - worker.py (updated)
# - mimic.service (updated)

# Set permissions
chmod +x run_bot.py
```

### Step 3: Install Systemd Services

```bash
# Copy service files to systemd directory
sudo cp mimic.service /etc/systemd/system/
sudo cp mimic-worker.service /etc/systemd/system/
sudo cp mimic-bot.service /etc/systemd/system/

# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable mimic
sudo systemctl enable mimic-worker
sudo systemctl enable mimic-bot
```

### Step 4: Start Services in Order

```bash
# 1. Start web server first
sudo systemctl start mimic
sudo systemctl status mimic

# 2. Start worker (depends on web server)
sudo systemctl start mimic-worker
sudo systemctl status mimic-worker

# 3. Start bot last (independent)
sudo systemctl start mimic-bot
sudo systemctl status mimic-bot
```

### Step 5: Verify Everything Works

```bash
# Check all services are running
sudo systemctl status mimic
sudo systemctl status mimic-worker
sudo systemctl status mimic-bot

# View logs
journalctl -u mimic -f           # Web server logs
journalctl -u mimic-worker -f    # Worker logs
journalctl -u mimic-bot -f       # Bot logs

# Check for errors
tail -f /var/www/mimic/logs/app.log
tail -f /var/www/mimic/logs/worker.json
tail -f /var/www/mimic/logs/telegram_bot.log
```

### Step 6: Test Telegram Bot

```bash
# 1. Open Telegram and find your bot
# 2. Send: /start
# 3. Expected: Welcome message with your user ID

# 4. Send: /status
# 5. Expected: Bot status, OTP status, current time

# 6. If you have OTP configured:
#    Send: /panic_close_all 123456
#    (Replace 123456 with your current OTP code)
```

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Telegram Bot Configuration
TG_TOKEN=123456789:ABCdefGHI...             # Bot token from @BotFather
TG_CHAT_ID=123456789                        # Your Telegram user/chat ID
TG_ENABLED=true                             # Enable notifications

# Panic Command Configuration (Optional)
PANIC_OTP_SECRET=JBSWY3DPEHPK3PXP          # Base32 secret for OTP
PANIC_AUTHORIZED_USERS=123456789,987654321  # Comma-separated user IDs

# Polling Configuration
TG_POLLING_STARTUP_DELAY=30                 # Seconds to wait before polling starts
```

### Get Your Telegram Configuration

#### 1. Get Bot Token

```
1. Open Telegram
2. Search for @BotFather
3. Send: /newbot
4. Follow prompts to create bot
5. Copy the token (looks like: 123456789:ABCdefGHIjkl...)
6. Add to .env: TG_TOKEN=your_token_here
```

#### 2. Get Your Chat ID

```
1. Start your bot in Telegram
2. Send any message to it
3. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
4. Look for "chat":{"id":123456789}
5. Add to .env: TG_CHAT_ID=your_chat_id
```

#### 3. Setup OTP for Panic Commands (Optional)

```bash
# Generate OTP secret
python -c "import pyotp; print(pyotp.random_base32())"

# Add to .env
PANIC_OTP_SECRET=YOUR_GENERATED_SECRET

# Add authorized users (your Telegram user ID)
PANIC_AUTHORIZED_USERS=123456789

# Setup in Google Authenticator:
# 1. Open Google Authenticator app
# 2. Click "+"
# 3. Choose "Enter a setup key"
# 4. Account: MIMIC/BrainCapital
# 5. Key: YOUR_GENERATED_SECRET
# 6. Time-based: Yes
```

---

## 🔍 Troubleshooting

### Bot Shows "409 Conflict" Error

```bash
# 1. Check if multiple bot instances are running
ps aux | grep run_bot.py

# 2. Check lock file
ls -la /tmp/mimic_telegram_bot.lock

# 3. Stop all bot instances
sudo systemctl stop mimic-bot
pkill -f "run_bot.py"

# 4. Clear lock file
rm -f /tmp/mimic_telegram_bot.lock

# 5. Restart bot
sudo systemctl start mimic-bot

# 6. If still failing, check for external instances:
#    - Other servers using same bot token
#    - Developer machines running the bot
#    - Docker containers
#    - Screen/tmux sessions
```

### Bot Not Responding to Commands

```bash
# 1. Check if bot service is running
sudo systemctl status mimic-bot

# 2. Check logs for errors
journalctl -u mimic-bot -n 100

# 3. Verify configuration
cat .env | grep TG_TOKEN

# 4. Test bot token manually
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"

# 5. Check if bot has lock file
ls -la /tmp/mimic_telegram_bot.lock

# 6. Restart bot
sudo systemctl restart mimic-bot
```

### Web Server Can't Scale Workers

**Good News**: You can now safely scale Gunicorn workers!

```bash
# Edit mimic.service
sudo nano /etc/systemd/system/mimic.service

# Change: --workers 1
# To:     --workers 4

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart mimic

# Verify workers
ps aux | grep gunicorn
```

### Worker Not Processing Tasks

```bash
# 1. Check Redis connection
redis-cli ping

# 2. Check worker status
sudo systemctl status mimic-worker

# 3. Check worker logs
journalctl -u mimic-worker -f

# 4. Verify ARQ queue
redis-cli LLEN arq:queue

# 5. Restart worker
sudo systemctl restart mimic-worker
```

---

## 📊 Monitoring

### Check Service Status

```bash
# Quick status of all services
sudo systemctl status mimic mimic-worker mimic-bot

# Detailed logs
journalctl -u mimic -f          # Web server
journalctl -u mimic-worker -f   # Worker
journalctl -u mimic-bot -f      # Bot
```

### Log Files

```
/var/www/mimic/logs/
├── app.log                    # Flask application logs
├── access.log                 # Gunicorn access logs
├── error.log                  # Gunicorn error logs
├── worker.json                # Worker JSON logs (for Loki)
├── telegram_bot.log           # Bot logs
├── bot_stdout.log             # Bot stdout (systemd)
├── bot_stderr.log             # Bot stderr (systemd)
├── worker_stdout.log          # Worker stdout (systemd)
└── worker_stderr.log          # Worker stderr (systemd)
```

### Prometheus Metrics

```bash
# Web server metrics (if enabled)
curl http://localhost:8000/metrics

# Worker metrics
curl http://localhost:9091/metrics
```

---

## 🎓 Understanding the Fix

### Before (BROKEN)

```
Gunicorn Master Process
├─ Worker 1 → Flask App → Tries to start bot ❌
├─ Worker 2 → Flask App → Tries to start bot ❌
├─ Worker 3 → Flask App → Tries to start bot ❌
└─ Worker 4 → Flask App → Tries to start bot ❌

Result: 409 Conflict! All workers fight for Telegram connection.
```

### After (FIXED)

```
┌─────────────────────────────────────────┐
│  Gunicorn Master Process                │
│  ├─ Worker 1 → Flask App (web only) ✅  │
│  ├─ Worker 2 → Flask App (web only) ✅  │
│  ├─ Worker 3 → Flask App (web only) ✅  │
│  └─ Worker 4 → Flask App (web only) ✅  │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  ARQ Worker Process                     │
│  └─ Tasks only (no bot) ✅              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Bot Process (SINGLETON)                │
│  └─ Telegram polling ONLY ✅            │
│     - File lock prevents duplicates     │
│     - 409 conflict prevention           │
│     - Independent scaling               │
└─────────────────────────────────────────┘

Result: Clean separation, no conflicts! 🎉
```

---

## 🔐 Security Notes

### File Locking

The bot uses **cross-platform file locking** to ensure only ONE instance runs:

- **Linux/Mac**: Uses `fcntl.flock()` (POSIX standard)
- **Windows**: Uses `msvcrt.locking()` (Windows API)
- **Lock File**: `/tmp/mimic_telegram_bot.lock` (or `%TEMP%` on Windows)

If the bot crashes, the lock is automatically released by the OS.

### OTP Verification

The panic close command requires **TOTP (Time-based One-Time Password)**:

- Industry standard (RFC 6238)
- Compatible with Google Authenticator, Authy, etc.
- 30-second validity window
- 6-digit codes
- Rate limiting: 3 attempts per 5 minutes

### Authorized Users

Only specific Telegram user IDs can execute panic commands:

```bash
# Add user IDs to .env
PANIC_AUTHORIZED_USERS=123456789,987654321
```

To get a user's ID:
1. Have them send `/start` to your bot
2. Check logs: `journalctl -u mimic-bot -f`
3. Look for `User ID: 123456789`

---

## 📚 Additional Resources

### Service Management Cheat Sheet

```bash
# Start services
sudo systemctl start mimic
sudo systemctl start mimic-worker
sudo systemctl start mimic-bot

# Stop services
sudo systemctl stop mimic
sudo systemctl stop mimic-worker
sudo systemctl stop mimic-bot

# Restart services
sudo systemctl restart mimic
sudo systemctl restart mimic-worker
sudo systemctl restart mimic-bot

# Enable auto-start on boot
sudo systemctl enable mimic
sudo systemctl enable mimic-worker
sudo systemctl enable mimic-bot

# Disable auto-start on boot
sudo systemctl disable mimic
sudo systemctl disable mimic-worker
sudo systemctl disable mimic-bot

# View status
sudo systemctl status mimic
sudo systemctl status mimic-worker
sudo systemctl status mimic-bot

# View logs (last 50 lines)
journalctl -u mimic -n 50
journalctl -u mimic-worker -n 50
journalctl -u mimic-bot -n 50

# Follow logs (real-time)
journalctl -u mimic -f
journalctl -u mimic-worker -f
journalctl -u mimic-bot -f

# Reload systemd after editing service files
sudo systemctl daemon-reload
```

### Testing Commands

```bash
# Test bot token
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"

# Test Redis
redis-cli ping

# Test database
python -c "from app import app, db; app.app_context().push(); print(db.engine.url)"

# Test if bot port is blocked
nc -zv api.telegram.org 443

# Check disk space
df -h

# Check memory
free -h

# Check processes
ps aux | grep -E "(gunicorn|arq|run_bot)"
```

---

## 🎉 Success Indicators

Your deployment is successful when:

✅ All three services show "active (running)" in `systemctl status`  
✅ Bot responds to `/start` and `/status` in Telegram  
✅ Web interface accessible and responsive  
✅ No "409 Conflict" errors in logs  
✅ Trading signals processed by worker  
✅ You can scale Gunicorn workers without bot issues  

---

## 💡 Tips

1. **Scale Gunicorn Workers Freely**: You can now use `--workers 4` or more without any bot conflicts!

2. **Independent Restarts**: Restart the web server without affecting the bot, or vice versa.

3. **Use Nginx**: For production, use Nginx as a reverse proxy in front of Gunicorn.

4. **Monitor Logs**: Set up log rotation for the log files to prevent disk space issues.

5. **Backup Config**: Keep a backup of your `.env` file (without committing to git).

---

## ❓ FAQ

**Q: Can I run the bot on a different server?**  
A: Yes! Just copy `run_bot.py` and the `.env` file to another server and run it there.

**Q: What happens if the bot crashes?**  
A: Systemd automatically restarts it (see `Restart=on-failure` in service file).

**Q: Can I disable the bot temporarily?**  
A: Yes, just stop the service: `sudo systemctl stop mimic-bot`

**Q: How do I update the bot code?**  
A: Update `run_bot.py` or `telegram_bot.py`, then: `sudo systemctl restart mimic-bot`

**Q: What if I need webhooks instead of polling?**  
A: Contact support. Polling is simpler for most use cases, but webhooks are more scalable for very high traffic.

---

**Version**: 1.0.0  
**Date**: January 2026  
**Author**: Brain Capital Team  
**Status**: Production Ready ✅
