# 🐧 Linux VPS Deployment Guide for Brain Capital (MIMIC)

## Quick Overview
```
Windows (develop) → GitHub (push) → Linux VPS (auto-deploy)
```

---

## 📋 PART 1: First-Time Setup on Linux VPS

### 1.1 Connect to Your VPS via SSH

```bash
# From your Windows PowerShell or Terminal
ssh root@YOUR_VPS_IP
```

### 1.2 Update System & Install Dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx curl

# Verify installations
python3 --version
git --version
nginx -v
```

### 1.3 Create Project Directory & Clone Repository

```bash
# Create web directory
sudo mkdir -p /var/www/mimic
sudo chown $USER:$USER /var/www/mimic
cd /var/www/mimic

# Clone your GitHub repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git .

# If your repo is private, use SSH:
# git clone git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git .
```

### 1.4 Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 1.5 Create Configuration Files

```bash
# Copy example configs
cp production.env.example .env
cp config.ini.example config.ini

# Create secrets directory
mkdir -p secrets

# Generate encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/master.key
chmod 600 secrets/master.key

# Edit .env with your settings
nano .env
```

**Important settings in `.env`:**
```bash
FLASK_ENV=production
FLASK_SECRET_KEY=your-generated-secret-key
PRODUCTION_DOMAIN=https://yourdomain.com
HTTPS_ENABLED=true
```

---

## 📋 PART 2: Set Up Systemd Service (Auto-Start on Boot)

### 2.1 Create Service File

```bash
sudo nano /etc/systemd/system/mimic.service
```

**Paste this content:**
```ini
[Unit]
Description=Brain Capital MIMIC Trading Platform
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/mimic
Environment="PATH=/var/www/mimic/venv/bin"
EnvironmentFile=/var/www/mimic/.env
ExecStart=/var/www/mimic/venv/bin/gunicorn \
    --worker-class eventlet \
    --workers 1 \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile /var/www/mimic/logs/access.log \
    --error-logfile /var/www/mimic/logs/error.log \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 2.2 Create Logs Directory & Enable Service

```bash
# Create logs directory
mkdir -p /var/www/mimic/logs

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable mimic

# Start the service
sudo systemctl start mimic

# Check status
sudo systemctl status mimic
```

---

## 📋 PART 3: Configure Nginx (Web Server + HTTPS)

### 3.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/mimic
```

**Paste this content (replace `yourdomain.com` with your actual domain):**
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=mimic_limit:10m rate=10r/s;

# Upstream Flask app
upstream mimic_app {
    server 127.0.0.1:5000;
    keepalive 32;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # For Let's Encrypt verification
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # Redirect HTTP to HTTPS (after SSL is set up)
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (will be added by certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limiting
    limit_req zone=mimic_limit burst=20 nodelay;

    # Static files
    location /static/ {
        alias /var/www/mimic/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # WebSocket support
    location /socket.io/ {
        proxy_pass http://mimic_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Main app
    location / {
        proxy_pass http://mimic_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3.2 Enable Site & Get SSL Certificate

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/mimic /etc/nginx/sites-enabled/

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx config (ignore SSL errors for now)
sudo nginx -t

# Get free SSL certificate from Let's Encrypt
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Restart nginx
sudo systemctl restart nginx
```

---

## 📋 PART 4: Set Up GitHub Auto-Deploy (SSH Keys)

### 4.1 Create SSH Key on Linux VPS (for GitHub to connect)

```bash
# On your Linux VPS
ssh-keygen -t ed25519 -C "deploy-key" -f ~/.ssh/deploy_key -N ""

# Show the public key (add this to GitHub as deploy key)
cat ~/.ssh/deploy_key.pub

# Show the private key (you'll add this to GitHub Secrets)
cat ~/.ssh/deploy_key
```

### 4.2 Add Keys to GitHub Repository

1. Go to your GitHub repository
2. **Settings** → **Deploy keys** → **Add deploy key**
   - Title: `VPS Deploy Key`
   - Key: Paste content of `~/.ssh/deploy_key.pub`
   - ✅ Allow write access

3. **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
   Add these secrets:
   - `VPS_HOST`: Your VPS IP address (e.g., `123.45.67.89`)
   - `VPS_USER`: `root` (or your username)
   - `VPS_SSH_KEY`: Paste entire content of `~/.ssh/deploy_key`
   - `VPS_PORT`: `22`

### 4.3 Allow Your Server's SSH Key

```bash
# On your VPS, add the deploy key to authorized_keys
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
```

---

## 📋 PART 5: Daily Workflow (Windows)

### Push Changes to GitHub (Auto-Deploys to VPS!)

```powershell
# In your Windows project folder (C:\Users\MIMIC Admin\Desktop\MIMIC)

# Add all changes
git add .

# Commit with message
git commit -m "Your update description"

# Push to GitHub (this triggers auto-deploy!)
git push origin main
```

**That's it!** GitHub Actions will automatically:
1. ✅ Receive your push
2. ✅ Connect to your Linux VPS
3. ✅ Pull the latest code
4. ✅ Install dependencies
5. ✅ Restart the application

---

## 📋 PART 6: Useful Commands

### On Linux VPS:

```bash
# View application status
sudo systemctl status mimic

# Restart application
sudo systemctl restart mimic

# View live logs
sudo journalctl -u mimic -f

# View app logs
tail -f /var/www/mimic/logs/error.log

# Manual deploy (if auto-deploy fails)
cd /var/www/mimic
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart mimic
```

### On Windows:

```powershell
# Quick deploy script
git add . && git commit -m "Quick update" && git push origin main
```

---

## 🔒 Firewall Setup (Important!)

```bash
# On Linux VPS
sudo ufw allow 22      # SSH
sudo ufw allow 80      # HTTP
sudo ufw allow 443     # HTTPS
sudo ufw enable
sudo ufw status
```

---

## 🐳 Alternative: Docker Deployment

If you prefer Docker, use the included `docker-compose.yml`:

```bash
# On Linux VPS with Docker installed
cd /var/www/mimic

# Create .env file first
cp production.env.example .env
nano .env

# Create secrets
mkdir -p secrets
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/master.key

# Start everything
docker-compose up -d

# View logs
docker-compose logs -f web
```

---

## ❓ Troubleshooting

### Site not loading?
```bash
sudo systemctl status mimic
sudo systemctl status nginx
sudo nginx -t
```

### 502 Bad Gateway?
```bash
# Check if app is running
curl http://localhost:5000
sudo systemctl restart mimic
```

### SSL certificate issues?
```bash
sudo certbot renew --dry-run
```

### Permission errors?
```bash
sudo chown -R $USER:$USER /var/www/mimic
chmod -R 755 /var/www/mimic
```

---

## 📞 Quick Reference

| What | Command |
|------|---------|
| Start app | `sudo systemctl start mimic` |
| Stop app | `sudo systemctl stop mimic` |
| Restart app | `sudo systemctl restart mimic` |
| View status | `sudo systemctl status mimic` |
| View logs | `sudo journalctl -u mimic -f` |
| Update code | `cd /var/www/mimic && git pull` |
| Restart nginx | `sudo systemctl restart nginx` |

---

**Your site will be available at: `https://yourdomain.com`**

