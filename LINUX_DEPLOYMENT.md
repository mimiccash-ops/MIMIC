# 🐧 MIMIC - Complete Linux VPS Deployment Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Part 1: Initial VPS Setup](#part-1-initial-vps-setup)
4. [Part 2: Project Installation](#part-2-project-installation)
5. [Part 3: Configuration](#part-3-configuration)
6. [Part 4: Systemd Service](#part-4-systemd-service)
7. [Part 5: Nginx & SSL](#part-5-nginx--ssl)
8. [Part 6: Database Setup](#part-6-database-setup)
9. [Part 7: Redis Setup (Optional)](#part-7-redis-setup-optional)
10. [Part 8: Auto-Deploy from GitHub](#part-8-auto-deploy-from-github)
11. [Part 9: Monitoring](#part-9-monitoring)
12. [Quick Commands Reference](#quick-commands-reference)
13. [Troubleshooting](#troubleshooting)

---

## Overview

This guide covers deploying MIMIC (Brain Capital) from scratch on a Linux VPS.

```
Development Flow:
Windows (develop) → GitHub (push) → Linux VPS (auto-deploy)
```

**Tested on:** Ubuntu 22.04 LTS, Debian 12

---

## Prerequisites

### VPS Requirements
- **OS:** Ubuntu 22.04+ or Debian 11+
- **RAM:** 2GB minimum (4GB recommended)
- **CPU:** 2 vCPUs minimum
- **Storage:** 20GB minimum
- **Network:** Public IP address

### Domain (Recommended)
- A domain name pointed to your VPS IP
- DNS A records configured

### Local Machine
- SSH client (built into Windows 10+, Linux, macOS)
- Git installed

---

## Part 1: Initial VPS Setup

### 1.1 Connect to Your VPS

```bash
# From your local machine
ssh root@38.180.147.102
```

### 1.2 Update System & Install Dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    nginx \
    certbot \
    python3-certbot-nginx \
    curl \
    wget \
    ufw \
    build-essential \
    libpq-dev \
    supervisor

# Verify installations
python3 --version  # Should be 3.10+
git --version
nginx -v
```

### 1.3 Create Application User (Security Best Practice)

```bash
# Create a dedicated user for the application
sudo useradd -m -s /bin/bash mimic
sudo usermod -aG sudo mimic

# Set a strong password
sudo passwd mimic
```

### 1.4 Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

---

## Part 2: Project Installation

### 2.1 Create Project Directory

```bash
# Create web directory
sudo mkdir -p /var/www/mimic
sudo chown -R $USER:$USER /var/www/mimic
cd /var/www/mimic
```

### 2.2 Clone Repository

```bash
# Option A: Clone from public repository
git clone https://github.com/mimiccash-ops/MIMIC.git .

# Option B: Clone from private repository (need SSH key)
git clone git@github.com:YOUR_USERNAME/YOUR_REPO.git .
```

### 2.3 Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install production server
pip install gunicorn eventlet
```

---

## Part 3: Configuration

### 3.1 Create Configuration Files

```bash
# Copy example configs
cp production.env.example .env
cp config.ini.example config.ini

# Create secrets directory
mkdir -p secrets
chmod 700 secrets

# Generate encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/master.key
chmod 600 secrets/master.key
```

### 3.2 Edit Environment File

```bash
nano .env
```

**Required settings:**
```bash
# Production mode
FLASK_ENV=production
HTTPS_ENABLED=true

# Security keys (REQUIRED)
FLASK_SECRET_KEY=your-64-char-secret-key-here
# Note: BRAIN_CAPITAL_MASTER_KEY is loaded from secrets/master.key

# Domain
PRODUCTION_DOMAIN=https://yourdomain.com

# Database (use PostgreSQL for production)
DATABASE_URL=postgresql://mimic_user:your_password@localhost:5432/mimic_db

# Redis (optional but recommended)
REDIS_URL=redis://localhost:6379/0
```

Generate a strong secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3.3 Edit Config File

```bash
nano config.ini
```

**Minimum required settings:**
```ini
[MasterAccount]
api_key = your_binance_api_key
api_secret = your_binance_api_secret

[Webhook]
passphrase = your_strong_webhook_passphrase

[Settings]
testnet = False
max_open_positions = 10

[Telegram]
bot_token = your_telegram_bot_token
chat_id = your_telegram_chat_id
enabled = True
```

### 3.4 Run Database Migrations

```bash
# Activate virtual environment if not active
source /var/www/mimic/venv/bin/activate

# Run migrations
python migrations/migrate.py
```

---

## Part 4: Systemd Service

### 4.1 Create Service File

```bash
sudo nano /etc/systemd/system/mimic.service
```

**Paste this content:**
```ini
[Unit]
Description=MIMIC Brain Capital Trading Platform
After=network.target postgresql.service redis.service

[Service]
User=mimic
Group=mimic
WorkingDirectory=/var/www/mimic
Environment="PATH=/var/www/mimic/venv/bin"
EnvironmentFile=/var/www/mimic/.env
ExecStart=/var/www/mimic/venv/bin/gunicorn \
    --worker-class eventlet \
    --workers 1 \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile /var/www/mimic/logs/access.log \
    --error-logfile /var/www/mimic/logs/error.log \
    --capture-output \
    app:app
Restart=always
RestartSec=5
StandardOutput=append:/var/www/mimic/logs/stdout.log
StandardError=append:/var/www/mimic/logs/stderr.log

[Install]
WantedBy=multi-user.target
```

### 4.2 Create Logs Directory & Enable Service

```bash
# Create logs directory
mkdir -p /var/www/mimic/logs
chmod 755 /var/www/mimic/logs

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

## Part 5: Nginx & SSL

### 5.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/mimic
```

**Paste this content (replace `yourdomain.com`):**
```nginx
# Rate limiting zone
limit_req_zone $binary_remote_addr zone=mimic_limit:10m rate=10r/s;

# Upstream Flask app
upstream mimic_app {
    server 127.0.0.1:5000;
    keepalive 32;
}

# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Let's Encrypt verification
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (will be created by certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL settings
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Rate limiting
    limit_req zone=mimic_limit burst=20 nodelay;

    # Max upload size
    client_max_body_size 16M;

    # Static files (served directly by nginx)
    location /static/ {
        alias /var/www/mimic/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
        access_log off;
    }

    # WebSocket support for Socket.IO
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
        proxy_buffering off;
    }

    # Main application
    location / {
        proxy_pass http://mimic_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### 5.2 Enable Site & Get SSL Certificate

```bash
# Enable the site
sudo ln -sf /etc/nginx/sites-available/mimic /etc/nginx/sites-enabled/

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx config (ignore SSL errors for now)
sudo nginx -t

# Get free SSL certificate from Let's Encrypt
# (First, temporarily comment out SSL lines in nginx config)
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Restart nginx
sudo systemctl restart nginx
```

---

## Part 6: Database Setup

### 6.1 Install PostgreSQL

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start and enable service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 6.2 Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# In psql shell:
CREATE USER mimic_user WITH PASSWORD 'your_strong_password';
CREATE DATABASE mimic_db OWNER mimic_user;
GRANT ALL PRIVILEGES ON DATABASE mimic_db TO mimic_user;
\q
```

### 6.3 Update .env

```bash
# Update DATABASE_URL in .env
DATABASE_URL=postgresql://mimic_user:your_strong_password@localhost:5432/mimic_db
```

### 6.4 Run Migrations

```bash
cd /var/www/mimic
source venv/bin/activate
python migrations/migrate.py
```

---

## Part 7: Redis Setup (Optional)

Redis enables the task queue for background processing.

### 7.1 Install Redis

```bash
sudo apt install -y redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf

# Find and change:
# supervised no → supervised systemd

# Start and enable Redis
sudo systemctl restart redis
sudo systemctl enable redis
```

### 7.2 Test Redis

```bash
redis-cli ping
# Should return: PONG
```

### 7.3 Update .env

```bash
REDIS_URL=redis://localhost:6379/0
```

### 7.4 Start Worker (Optional)

If using background tasks:
```bash
# Create worker service
sudo nano /etc/systemd/system/mimic-worker.service
```

```ini
[Unit]
Description=MIMIC ARQ Worker
After=network.target redis.service

[Service]
User=mimic
Group=mimic
WorkingDirectory=/var/www/mimic
Environment="PATH=/var/www/mimic/venv/bin"
EnvironmentFile=/var/www/mimic/.env
ExecStart=/var/www/mimic/venv/bin/python worker.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mimic-worker
sudo systemctl start mimic-worker
```

---

## Part 8: Auto-Deploy from GitHub

### 8.1 Create SSH Key on VPS

```bash
# Generate deploy key
ssh-keygen -t ed25519 -C "deploy-key" -f ~/.ssh/deploy_key -N ""

# Show public key (add to GitHub as deploy key)
cat ~/.ssh/deploy_key.pub

# Show private key (add to GitHub Secrets)
cat ~/.ssh/deploy_key
```

### 8.2 Add Keys to GitHub

1. Go to your GitHub repository
2. **Settings** → **Deploy keys** → **Add deploy key**
   - Title: `VPS Deploy Key`
   - Key: Paste `~/.ssh/deploy_key.pub`
   - ✅ Allow write access

3. **Settings** → **Secrets and variables** → **Actions**
   Add these secrets:
   - `VPS_HOST`: Your VPS IP
   - `VPS_USER`: `root`
   - `VPS_SSH_KEY`: Content of `~/.ssh/deploy_key`
   - `VPS_PORT`: `22`

### 8.3 Allow Deploy Key

```bash
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
```

### 8.4 GitHub Actions Workflow

The repository includes `.github/workflows/deploy.yml` which:
1. Triggers on push to `main` branch
2. Connects to your VPS via SSH
3. Pulls latest code
4. Installs dependencies
5. Restarts the service

---

## Part 9: Monitoring

### 9.1 View Logs

```bash
# Application logs
tail -f /var/www/mimic/logs/error.log

# Systemd journal
sudo journalctl -u mimic -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 9.2 Setup Log Rotation

```bash
sudo nano /etc/logrotate.d/mimic
```

```
/var/www/mimic/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 mimic mimic
    sharedscripts
    postrotate
        systemctl reload mimic > /dev/null 2>&1 || true
    endscript
}
```

### 9.3 Health Check

```bash
# Check if service is running
sudo systemctl status mimic

# Check if nginx is running
sudo systemctl status nginx

# Test the application
curl -I http://localhost:5000/health
curl -I https://yourdomain.com
```

---

## Quick Commands Reference

| Action | Command |
|--------|---------|
| Start app | `sudo systemctl start mimic` |
| Stop app | `sudo systemctl stop mimic` |
| Restart app | `sudo systemctl restart mimic` |
| View status | `sudo systemctl status mimic` |
| View logs | `sudo journalctl -u mimic -f` |
| Update code | `cd /var/www/mimic && git pull` |
| Install deps | `source venv/bin/activate && pip install -r requirements.txt` |
| Run migrations | `source venv/bin/activate && python migrations/migrate.py` |
| Restart nginx | `sudo systemctl restart nginx` |
| Renew SSL | `sudo certbot renew` |
| Backup DB | `pg_dump mimic_db > backup.sql` |

---

## Troubleshooting

### Site Not Loading

```bash
# Check service status
sudo systemctl status mimic
sudo systemctl status nginx

# Check if port 5000 is listening
sudo ss -tlnp | grep 5000

# Check nginx configuration
sudo nginx -t
```

### 502 Bad Gateway

```bash
# App might not be running
sudo systemctl restart mimic

# Check if gunicorn is running
ps aux | grep gunicorn

# Check logs
tail -100 /var/www/mimic/logs/error.log
```

### SSL Certificate Issues

```bash
# Test renewal
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U mimic_user -d mimic_db -h localhost
```

### Permission Errors

```bash
# Fix ownership (use mimic user created in Part 1)
sudo chown -R mimic:mimic /var/www/mimic
sudo chmod -R 755 /var/www/mimic
sudo chmod 600 /var/www/mimic/.env
sudo chmod 600 /var/www/mimic/config.ini
```

### Out of Memory

```bash
# Check memory usage
free -m

# Add swap if needed
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 🎉 Deployment Complete!

Your site should now be available at: `https://yourdomain.com`

**Default login:** `admin` / `admin`

> ⚠️ **Change the default password immediately!**

---

*Last Updated: January 9, 2026*
