# 🚀 WEBHOOK QUICK START GUIDE

## ⚡ IMMEDIATE FIX FOR VPS WEBHOOK

Your webhook wasn't working because of a **port mismatch** in nginx configuration. This has been **FIXED**!

---

## 🔧 What Was Fixed

1. **Nginx port corrected**: Changed from port 8000 → 5000 (to match Docker/Gunicorn)
2. **Webhook endpoint optimized**: Added special `/webhook` location with:
   - No rate limiting (critical for TradingView)
   - Longer timeouts (120s)
   - Better logging for debugging
3. **TradingView IP whitelist**: Added documentation for TradingView's webhook IPs

---

## 📋 STEP-BY-STEP TO GET WEBHOOKS WORKING NOW

### Step 1: Apply nginx Configuration (ON YOUR VPS)

```bash
# SSH into your VPS
ssh your-user@your-vps-ip

# Navigate to your project
cd /path/to/MIMIC

# Backup current nginx config
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup

# Copy the fixed config
sudo cp nginx.conf.production /etc/nginx/nginx.conf

# Test nginx configuration
sudo nginx -t

# If test passes, reload nginx
sudo systemctl reload nginx

# Check nginx status
sudo systemctl status nginx
```

### Step 2: Restart Docker Services (ON YOUR VPS)

```bash
# Restart all services with the correct configuration
docker-compose down
docker-compose up -d

# Check if services are running
docker-compose ps

# Check logs
docker-compose logs -f web
```

### Step 3: Test Your Webhook (FROM YOUR LOCAL MACHINE)

```bash
# Install Python requests if needed
pip install requests python-dotenv

# Test webhook (replace with your VPS domain/IP)
python test_webhook.py --url your-vps-domain.com

# Or if using IP address
python test_webhook.py --url 1.2.3.4

# If you haven't set up SSL yet, use HTTP
python test_webhook.py --url your-vps-ip --no-https
```

### Step 4: Configure TradingView Alert

1. **Open TradingView** → Go to your chart
2. **Create Alert** → Click the alarm icon
3. **Set Webhook URL**:
   ```
   https://your-vps-domain.com/webhook
   ```
   Or if no SSL:
   ```
   http://your-vps-ip/webhook
   ```

4. **Alert Message** (JSON format):
   ```json
   {
     "passphrase": "mimiccashadministrator",
     "symbol": "{{ticker}}",
     "action": "long",
     "leverage": 10,
     "risk_perc": 2,
     "tp_perc": 5,
     "sl_perc": 2,
     "strategy_id": 1
   }
   ```

5. **Test the Alert** → Click "Test" button in TradingView

---

## 🔍 Troubleshooting

### ❌ Connection Refused / Timeout

**Problem**: Can't reach webhook endpoint

**Solutions**:
```bash
# Check if firewall is blocking ports
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check if nginx is running
sudo systemctl status nginx

# Check if Docker containers are running
docker-compose ps

# Check application logs
docker-compose logs web | tail -50
```

### ❌ 401 Unauthorized

**Problem**: Wrong passphrase

**Solution**: Check your `.env` file has the correct `WEBHOOK_PASSPHRASE`

```bash
cat .env | grep WEBHOOK_PASSPHRASE
```

### ❌ 502 Bad Gateway

**Problem**: Nginx can't reach the application

**Solutions**:
```bash
# Check if web container is healthy
docker-compose ps

# Check port is correct in nginx config
sudo cat /etc/nginx/nginx.conf | grep "server 127.0.0.1"
# Should show: server 127.0.0.1:5000;

# Restart services
docker-compose restart web
sudo systemctl reload nginx
```

### ❌ Positions Not Opening

**Problem**: Webhook received but no trades executed

**Solutions**:
```bash
# Check worker logs (where trades are executed)
docker-compose logs -f worker

# Check if API keys are valid
docker-compose exec web python -c "from config import Config; print('Binance Key:', Config.BINANCE_MASTER_KEY[:10] + '...')"

# Check if exchanges are approved and active
# Login to your dashboard → Admin → Exchanges → Check status
```

---

## 📊 Verify Webhook is Working

### Check Nginx Logs (ON VPS)
```bash
# Watch webhook access logs in real-time
sudo tail -f /var/log/nginx/webhook_access.log

# Check for errors
sudo tail -f /var/log/nginx/webhook_error.log
```

### Check Application Logs (ON VPS)
```bash
# Watch application logs
docker-compose logs -f web | grep -i webhook

# Check worker logs (where trades execute)
docker-compose logs -f worker | grep -i signal
```

### Check Database (ON VPS)
```bash
# Connect to database
docker-compose exec db psql -U brain_capital -d brain_capital

# Check recent trades
SELECT * FROM trades ORDER BY entry_time DESC LIMIT 5;

# Check positions
SELECT * FROM positions ORDER BY entry_time DESC LIMIT 5;

# Exit psql
\q
```

---

## 🎯 TradingView Alert Examples

### Long Position
```json
{
  "passphrase": "mimiccashadministrator",
  "symbol": "{{ticker}}",
  "action": "long",
  "leverage": 10,
  "risk_perc": 2,
  "tp_perc": 5,
  "sl_perc": 2,
  "strategy_id": 1
}
```

### Short Position
```json
{
  "passphrase": "mimiccashadministrator",
  "symbol": "{{ticker}}",
  "action": "short",
  "leverage": 10,
  "risk_perc": 2,
  "tp_perc": 5,
  "sl_perc": 2,
  "strategy_id": 1
}
```

### Close Position
```json
{
  "passphrase": "mimiccashadministrator",
  "symbol": "{{ticker}}",
  "action": "close",
  "strategy_id": 1
}
```

---

## 🔐 Security Notes

1. **Change Default Passphrase**: Update `WEBHOOK_PASSPHRASE` in `.env` to something unique
2. **Use HTTPS**: Always use HTTPS in production (set up SSL certificate)
3. **Firewall**: Only allow necessary ports (80, 443, 22)
4. **Monitor Logs**: Regularly check logs for suspicious activity

---

## 📞 Quick Commands Reference

```bash
# Restart everything
docker-compose down && docker-compose up -d

# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f web
docker-compose logs -f worker

# Check service status
docker-compose ps

# Test webhook locally
python test_webhook.py --url localhost --no-https

# Check nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

---

## ✅ Verification Checklist

Before testing TradingView webhooks, verify:

- [ ] Nginx is running: `sudo systemctl status nginx`
- [ ] Docker containers are running: `docker-compose ps`
- [ ] Port 5000 is mapped correctly in docker-compose.yml
- [ ] Webhook endpoint is accessible: `curl http://localhost:5000/webhook`
- [ ] Firewall allows ports 80/443: `sudo ufw status`
- [ ] SSL certificate is valid (if using HTTPS)
- [ ] `.env` file has correct `WEBHOOK_PASSPHRASE`
- [ ] Binance API keys are configured and working
- [ ] User exchanges are APPROVED and ACTIVE in admin panel

---

## 🎉 SUCCESS!

Once the webhook test passes, your system is ready to receive TradingView signals and automatically open positions on Binance!

**Your webhook URL**: `https://your-vps-domain.com/webhook`

Now you can create alerts in TradingView and they will automatically trigger trades on your VPS server! 🚀
