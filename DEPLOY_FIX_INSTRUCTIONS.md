# Trading Engine Fix - Deployment Instructions

## Quick Fix Deployed
Fixed critical silent failure issues in `trading_engine.py`. The system will now log detailed errors showing why trades aren't executing.

## Issues Fixed:
1. ✅ Silent failure when no users configured
2. ✅ Silent is_paused checks  
3. ✅ Silent subscription expiry
4. ✅ Silent quantity/notional validation failures
5. ✅ Missing strategy subscription warnings

## Deploy to VPS (Option 1: Manual SSH)

**Connect to your VPS:**
```bash
ssh root@38.180.147.102
# Password: BY2YQ35j3v
```

**Once connected, run these commands:**

```bash
# Navigate to app directory (adjust path if different)
cd /var/www/mimic || cd ~/MIMIC || cd /opt/mimic

# Backup current file
cp trading_engine.py trading_engine.py.backup.$(date +%Y%m%d_%H%M%S)

# Copy the fixed file (you'll need to upload it or use git pull)
# If using git:
# git pull origin main

# Restart worker service
sudo systemctl restart mimic-worker

# Check worker status
sudo systemctl status mimic-worker

# View live logs (press Ctrl+C to exit)
sudo journalctl -u mimic-worker -f -n 100

# Or check app logs
tail -f logs/app.log | grep -E "NO USERS|paused|expired|Quantity|Position too small"
```

## Deploy to VPS (Option 2: Using SCP from Windows)

**From your Windows machine, run in PowerShell:**

```powershell
# Navigate to project directory
cd "C:\Users\MIMIC Admin\Desktop\MIMIC"

# Copy file to VPS (use plink if OpenSSH not available)
scp trading_engine.py root@38.180.147.102:/var/www/mimic/trading_engine.py

# SSH and restart
ssh root@38.180.147.102 "sudo systemctl restart mimic-worker && sudo systemctl status mimic-worker"
```

## Verify the Fix

After deployment, check logs for these new error messages:

**1. Check if no users are configured:**
```bash
grep "NO USERS TO PROCESS" logs/app.log
```

**2. Check for paused users:**
```bash
grep "User is paused" logs/app.log
```

**3. Check for subscription issues:**
```bash
grep "Subscription expired" logs/app.log
```

**4. Check for position size issues:**
```bash
grep -E "Quantity is 0|Position too small" logs/app.log
```

**5. Check for strategy subscription issues:**
```bash
grep "NO SUBSCRIPTIONS FOUND" logs/app.log
```

## What to Look For

When you send a webhook signal, the logs should now show:
- ✅ If signal was received and queued
- ✅ How many users (master/slave) are being processed  
- ✅ **Why** trades are being skipped (if any)

## Test a Signal

Send a test webhook and immediately check logs:
```bash
# In one terminal, watch logs
tail -f logs/app.log

# Send test webhook from TradingView or curl
curl -X POST http://your-domain/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","action":"long","passphrase":"YOUR_PASSPHRASE","risk":3,"lev":20}'
```

You should see detailed logs showing exactly what happened with each user account.
