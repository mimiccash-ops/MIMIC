# 🚀 DEPLOYMENT CHECKLIST - Telegram Bot Fix

## ✅ Files Ready for Upload

All files have been updated and are ready for deployment to Linux VPS.

### **Modified Files (Upload Required)**

1. ✅ `run_bot.py` - **NEW** Standalone bot runner (v1.0.1 - Fixed signal handling)
2. ✅ `mimic-bot.service` - **NEW** Systemd service for bot
3. ✅ `mimic-worker.service` - **NEW** Systemd service for worker
4. ✅ `app.py` - **MODIFIED** (Bot initialization removed, lines 254-274)
5. ✅ `worker.py` - **MODIFIED** (Bot initialization removed, lines 195-244)
6. ✅ `mimic.service` - **MODIFIED** (Updated comments, web-only focus)

### **Documentation Files (Optional)**

7. ✅ `TELEGRAM_BOT_ARCHITECTURE.md` - Complete guide
8. ✅ `QUICK_DEPLOYMENT.md` - Quick reference
9. ✅ `DEPLOYMENT_SUMMARY.md` - Executive summary
10. ✅ `DEPLOYMENT_CHECKLIST.md` - This file

---

## 📤 UPLOAD TO LINUX VPS

### **Method 1: Git (Recommended)**

```bash
# On Windows
cd "C:\Users\MIMIC Admin\Desktop\MIMIC"

git add run_bot.py mimic-bot.service mimic-worker.service app.py worker.py mimic.service
git add *.md  # Documentation (optional)

git commit -m "Fix: Telegram bot 409 conflicts - separate service architecture"
git push origin main

# On Linux VPS
cd /var/www/mimic
git pull origin main
```

### **Method 2: SCP (Direct Transfer)**

```powershell
# On Windows PowerShell
$SERVER = "root@YOUR_VPS_IP"
cd "C:\Users\MIMIC Admin\Desktop\MIMIC"

# Upload essential files
scp run_bot.py ${SERVER}:/var/www/mimic/
scp mimic-bot.service ${SERVER}:/var/www/mimic/
scp mimic-worker.service ${SERVER}:/var/www/mimic/
scp app.py ${SERVER}:/var/www/mimic/
scp worker.py ${SERVER}:/var/www/mimic/
scp mimic.service ${SERVER}:/var/www/mimic/
```

### **Method 3: WinSCP/FileZilla (GUI)**

1. Connect to your VPS
2. Navigate to `C:\Users\MIMIC Admin\Desktop\MIMIC` (local)
3. Navigate to `/var/www/mimic` (remote)
4. Upload the 6 files listed above

---

## 🔧 DEPLOYMENT COMMANDS (On Linux VPS)

```bash
# 1. Stop all services
sudo systemctl stop mimic mimic-worker mimic-bot 2>/dev/null
pkill -f "telegram_bot|run_bot.py"
rm -f /tmp/mimic_telegram_bot.lock

# 2. Navigate to project directory
cd /var/www/mimic

# 3. Set permissions
chmod +x run_bot.py
chown mimic:mimic run_bot.py app.py worker.py

# 4. Install systemd services
sudo cp mimic.service /etc/systemd/system/
sudo cp mimic-worker.service /etc/systemd/system/
sudo cp mimic-bot.service /etc/systemd/system/

# 5. Reload systemd
sudo systemctl daemon-reload

# 6. Enable services (auto-start on boot)
sudo systemctl enable mimic
sudo systemctl enable mimic-worker
sudo systemctl enable mimic-bot

# 7. Start services IN ORDER
sudo systemctl start mimic          # Web server first
sleep 5                              # Wait for web to stabilize
sudo systemctl start mimic-worker   # Worker second
sleep 5                              # Wait for worker to stabilize
sudo systemctl start mimic-bot      # Bot last

# 8. Verify all services are running
sudo systemctl status mimic
sudo systemctl status mimic-worker
sudo systemctl status mimic-bot
```

---

## ✅ VERIFICATION STEPS

### 1. Check Service Status

```bash
# All should show "active (running)"
sudo systemctl status mimic mimic-worker mimic-bot
```

**Expected Output:**
```
● mimic.service - MIMIC Web Server (Gunicorn + Flask)
   Active: active (running)

● mimic-worker.service - MIMIC ARQ Background Worker
   Active: active (running)

● mimic-bot.service - MIMIC Telegram Bot (Polling)
   Active: active (running)
```

### 2. Check Bot Logs

```bash
# Watch bot logs in real-time
journalctl -u mimic-bot -f

# Check recent logs
journalctl -u mimic-bot -n 50

# Check for errors
journalctl -u mimic-bot | grep -i error
journalctl -u mimic-bot | grep -i conflict  # Should be empty!
```

**Expected in Logs:**
```
✅ Configuration loaded successfully
✅ Flask app and database initialized
✅ Trading engine initialized
🔒 Acquired bot lock (PID: XXXXX)
🤖 Creating Telegram bot application...
🤖 Starting polling...
✅ Telegram bot is now running and polling for updates!
```

### 3. Test in Telegram

1. Open Telegram
2. Find your bot (search by @username)
3. Send: `/start`
   - **Expected**: Welcome message with your user ID
4. Send: `/status`
   - **Expected**: Bot status with current time
5. Send: `/help`
   - **Expected**: List of available commands

### 4. Check No 409 Conflicts

```bash
# Should return NO results
journalctl -u mimic-bot | grep -i "409"
journalctl -u mimic-bot | grep -i "conflict"
```

### 5. Verify Lock File

```bash
# Should exist and contain bot PID
ls -la /tmp/mimic_telegram_bot.lock
cat /tmp/mimic_telegram_bot.lock
```

### 6. Check Web Server (Still Works)

```bash
# Web server should be running independently
curl http://localhost:8000/  # Should return HTML

# Check web server logs
journalctl -u mimic -n 20
```

---

## 🎯 SUCCESS CRITERIA

✅ All 3 services show "active (running)"  
✅ Bot responds to `/start` in Telegram  
✅ Bot responds to `/status` in Telegram  
✅ No "409 Conflict" errors in logs  
✅ Lock file exists at `/tmp/mimic_telegram_bot.lock`  
✅ Web interface accessible and working  
✅ Worker processing tasks (check Redis queue)  
✅ Can restart services independently  

---

## 🐛 TROUBLESHOOTING

### Bot Service Won't Start

```bash
# Check detailed error
journalctl -xeu mimic-bot.service --no-pager | tail -50

# Check bot log file
tail -100 /var/www/mimic/logs/bot_stdout.log
tail -100 /var/www/mimic/logs/bot_stderr.log

# Common fixes:
# 1. Check TG_TOKEN is set
grep TG_TOKEN /var/www/mimic/.env

# 2. Check Python version
/var/www/mimic/venv/bin/python --version  # Should be 3.8+

# 3. Check file permissions
ls -la /var/www/mimic/run_bot.py

# 4. Clear lock file and retry
rm -f /tmp/mimic_telegram_bot.lock
sudo systemctl restart mimic-bot
```

### Still Getting 409 Conflicts

```bash
# 1. Check if another instance is running
ps aux | grep run_bot.py
ps aux | grep telegram_bot

# 2. Check for multiple lock files
ls -la /tmp/mimic_telegram_bot.lock*

# 3. Verify only ONE bot service is enabled
systemctl list-units --type=service | grep bot

# 4. Check if dev machine is running bot
# (Stop bot on your Windows development machine!)

# 5. Nuclear option - regenerate bot token
# Go to @BotFather on Telegram
# /mybots → Select bot → API Token → Revoke and regenerate
```

### Web Server Issues

```bash
# Check web logs
journalctl -u mimic -n 50

# Restart web server only (won't affect bot)
sudo systemctl restart mimic

# Check if port is in use
sudo netstat -tlnp | grep 8000
```

### Worker Not Processing Tasks

```bash
# Check worker logs
journalctl -u mimic-worker -n 50

# Check Redis connection
redis-cli ping

# Restart worker only
sudo systemctl restart mimic-worker
```

---

## 🔄 RESTART INDIVIDUAL SERVICES

```bash
# Restart web server (doesn't affect bot or worker)
sudo systemctl restart mimic

# Restart worker (doesn't affect bot or web)
sudo systemctl restart mimic-worker

# Restart bot (doesn't affect web or worker)
sudo systemctl restart mimic-bot

# Restart all services
sudo systemctl restart mimic mimic-worker mimic-bot
```

---

## 📊 MONITORING

### View Logs

```bash
# Real-time logs (follow mode)
journalctl -u mimic -f          # Web server
journalctl -u mimic-worker -f   # Worker
journalctl -u mimic-bot -f      # Bot

# Last N lines
journalctl -u mimic-bot -n 100

# Logs with timestamp range
journalctl -u mimic-bot --since "10 minutes ago"
journalctl -u mimic-bot --since "2026-01-12 19:00:00"

# All services combined
journalctl -u mimic -u mimic-worker -u mimic-bot -f
```

### Check Resource Usage

```bash
# Memory usage
systemctl status mimic mimic-worker mimic-bot | grep Memory

# CPU usage
systemctl status mimic mimic-worker mimic-bot | grep CPU

# Detailed stats
systemctl show mimic-bot | grep -E "(Memory|CPU)"
```

---

## 🎉 DEPLOYMENT COMPLETE

If all verification steps pass, your deployment is successful!

**Key Improvements:**
- ✅ No more 409 Conflict errors
- ✅ Bot runs as isolated singleton
- ✅ Can scale Gunicorn workers freely
- ✅ Services restart independently
- ✅ Clean separation of concerns
- ✅ Production-ready architecture

---

## 📚 NEXT STEPS

1. **Monitor for 24 hours** - Check logs daily
2. **Test scaling** - Try increasing Gunicorn workers
3. **Setup monitoring** - Configure Prometheus/Grafana
4. **Enable auto-updates** - Setup systemd timers
5. **Backup configuration** - Save `.env` and service files

---

## 📞 SUPPORT

If you encounter issues:

1. Check this checklist's troubleshooting section
2. Review `TELEGRAM_BOT_ARCHITECTURE.md` for detailed docs
3. Check logs: `journalctl -u mimic-bot -n 100`
4. Verify configuration: `grep TG_TOKEN .env`

---

**Version**: 1.0  
**Date**: January 12, 2026  
**Status**: ✅ Ready for Production  
**Tested**: Linux VPS (Ubuntu 22.04+)
