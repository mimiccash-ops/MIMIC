# 🚀 Quick Installation Guide - MIMIC on Linux VPS

## Option 1: Automated Installation (Recommended)

### On Your Linux VPS:

```bash
# Download and run the automated installation script
curl -fsSL https://raw.githubusercontent.com/mimiccash-ops/MIMIC/main/install_vps.sh -o install_vps.sh
sudo chmod +x install_vps.sh
sudo ./install_vps.sh
```

Or if you already have the repository:

```bash
cd MIMIC
sudo chmod +x install_vps.sh
sudo ./install_vps.sh
```

### What the Script Does:

✅ Clones repository from GitHub  
✅ Installs all system dependencies (Python, Node.js, PostgreSQL, Redis, Nginx)  
✅ Creates Python virtual environment  
✅ Installs all Python packages  
✅ Sets up PostgreSQL database  
✅ Configures Redis  
✅ Creates systemd services  
✅ Sets up firewall rules  
✅ Creates configuration files  

---

## Option 2: Manual Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/mimiccash-ops/MIMIC.git /var/www/mimic
cd /var/www/mimic
```

### Step 2: Run Installation Script

```bash
sudo chmod +x install_vps.sh
sudo ./install_vps.sh
```

### Step 3: Configure

Edit the configuration files:

```bash
nano /var/www/mimic/.env
nano /var/www/mimic/config.ini
```

### Step 4: Start Services

```bash
sudo systemctl start mimic
sudo systemctl start mimic-worker
sudo systemctl start mimic-bot
```

---

## Installation Options

```bash
# Install to default path (/var/www/mimic)
sudo ./install_vps.sh

# Install to custom path
sudo ./install_vps.sh /opt/mimic

# Skip Nginx setup
sudo ./install_vps.sh --skip-nginx

# Skip PostgreSQL setup (use existing database)
sudo ./install_vps.sh --skip-db

# Skip Redis setup
sudo ./install_vps.sh --skip-redis

# Show help
sudo ./install_vps.sh --help
```

---

## Post-Installation Checklist

- [ ] Edit `/var/www/mimic/.env` with your settings
- [ ] Edit `/var/www/mimic/config.ini` with your API keys
- [ ] Start services: `sudo systemctl start mimic mimic-worker mimic-bot`
- [ ] Check status: `sudo systemctl status mimic`
- [ ] Configure Nginx (see `LINUX_DEPLOYMENT.md`)
- [ ] Set up SSL certificate with Let's Encrypt
- [ ] Test the application

---

## Useful Commands

```bash
# View logs
sudo journalctl -u mimic -f

# Restart services
sudo systemctl restart mimic

# Update from GitHub
cd /var/www/mimic
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart mimic
```

---

## Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u mimic -n 50

# Check configuration
sudo systemctl status mimic
```

### Database connection issues

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U mimic_user -d mimic_db -h localhost
```

### Permission errors

```bash
# Fix ownership
sudo chown -R mimic:mimic /var/www/mimic
```

---

For detailed instructions, see: [LINUX_DEPLOYMENT.md](LINUX_DEPLOYMENT.md)
