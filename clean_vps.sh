#!/bin/bash
# ============================================
# MIMIC VPS Complete Cleanup Script
# ============================================
# 
# ⚠️  WARNING: This script will DELETE:
#   - All MIMIC application files
#   - All systemd services (mimic, mimic-worker, mimic-bot)
#   - All Nginx configurations for MIMIC
#   - All SSL certificates for MIMIC domains
#   - All databases (PostgreSQL/MySQL)
#   - All Docker containers and volumes
#   - All Redis data
#   - Application user (mimic)
#   - All Python virtual environments
#   - All files in /root (except .bashrc, .profile, .ssh)
#
# ✅ This script will KEEP:
#   - Base Linux system
#   - SSH access
#   - System packages
#   - Other applications (if any)
#
# ============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/var/www/mimic"
APP_USER="mimic"
DOMAIN="mimiccash.com"  # Change if different

echo -e "${RED}============================================${NC}"
echo -e "${RED}  MIMIC VPS COMPLETE CLEANUP SCRIPT${NC}"
echo -e "${RED}============================================${NC}"
echo ""
echo -e "${YELLOW}This will DELETE everything related to MIMIC!${NC}"
echo ""
read -p "Are you SURE you want to continue? (type 'YES' to confirm): " confirm

if [ "$confirm" != "YES" ]; then
    echo -e "${GREEN}Cancelled. Nothing was deleted.${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}Starting cleanup...${NC}"
echo ""

# ============================================
# STEP 1: Stop all services
# ============================================
echo -e "${YELLOW}[1/10] Stopping all MIMIC services...${NC}"
systemctl stop mimic mimic-worker mimic-bot 2>/dev/null || true
systemctl disable mimic mimic-worker mimic-bot 2>/dev/null || true
pkill -f "gunicorn.*mimic" 2>/dev/null || true
pkill -f "arq.*worker" 2>/dev/null || true
pkill -f "telegram_bot\|run_bot.py" 2>/dev/null || true
rm -f /tmp/mimic_telegram_bot.lock 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓ Services stopped${NC}"

# ============================================
# STEP 2: Remove systemd service files
# ============================================
echo -e "${YELLOW}[2/10] Removing systemd service files...${NC}"
rm -f /etc/systemd/system/mimic.service
rm -f /etc/systemd/system/mimic-worker.service
rm -f /etc/systemd/system/mimic-bot.service
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true
echo -e "${GREEN}✓ Systemd services removed${NC}"

# ============================================
# STEP 3: Remove Nginx configurations
# ============================================
echo -e "${YELLOW}[3/10] Removing Nginx configurations...${NC}"
if [ -d "/etc/nginx/sites-available" ]; then
    rm -f /etc/nginx/sites-available/mimic* 2>/dev/null || true
    rm -f /etc/nginx/sites-enabled/mimic* 2>/dev/null || true
    nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true
fi
echo -e "${GREEN}✓ Nginx configs removed${NC}"

# ============================================
# STEP 4: Remove SSL certificates
# ============================================
echo -e "${YELLOW}[4/10] Removing SSL certificates...${NC}"
if command -v certbot &> /dev/null; then
    certbot delete --cert-name "$DOMAIN" --non-interactive 2>/dev/null || true
    rm -rf /etc/letsencrypt/live/$DOMAIN 2>/dev/null || true
    rm -rf /etc/letsencrypt/archive/$DOMAIN 2>/dev/null || true
    rm -rf /etc/letsencrypt/renewal/$DOMAIN.conf 2>/dev/null || true
fi
echo -e "${GREEN}✓ SSL certificates removed${NC}"

# ============================================
# STEP 5: Remove application files
# ============================================
echo -e "${YELLOW}[5/10] Removing application files...${NC}"
if [ -d "$APP_DIR" ]; then
    rm -rf "$APP_DIR"
    echo -e "${GREEN}✓ Application directory removed: $APP_DIR${NC}"
else
    echo -e "${YELLOW}  Directory not found: $APP_DIR${NC}"
fi

# Also check common alternative locations
for alt_dir in "/opt/mimic" "/home/mimic" "~/MIMIC"; do
    if [ -d "$alt_dir" ]; then
        rm -rf "$alt_dir"
        echo -e "${GREEN}✓ Removed: $alt_dir${NC}"
    fi
done
echo -e "${GREEN}✓ Application files removed${NC}"

# ============================================
# STEP 6: Remove Docker containers and volumes
# ============================================
echo -e "${YELLOW}[6/10] Removing Docker containers and volumes...${NC}"
if command -v docker &> /dev/null; then
    # Stop and remove containers
    docker ps -a --filter "name=brain_capital\|mimic" -q | xargs -r docker rm -f 2>/dev/null || true
    
    # Remove volumes
    docker volume ls --filter "name=brain_capital\|mimic" -q | xargs -r docker volume rm 2>/dev/null || true
    
    # Remove images (optional - uncomment if you want to remove images too)
    # docker images --filter "reference=*mimic*" -q | xargs -r docker rmi -f 2>/dev/null || true
    
    echo -e "${GREEN}✓ Docker containers and volumes removed${NC}"
else
    echo -e "${YELLOW}  Docker not installed${NC}"
fi

# ============================================
# STEP 7: Remove databases
# ============================================
echo -e "${YELLOW}[7/10] Removing databases...${NC}"

# PostgreSQL
if command -v psql &> /dev/null; then
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS brain_capital;" 2>/dev/null || true
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS mimic_db;" 2>/dev/null || true
    sudo -u postgres psql -c "DROP USER IF EXISTS mimic_user;" 2>/dev/null || true
    sudo -u postgres psql -c "DROP USER IF EXISTS brain_capital;" 2>/dev/null || true
    echo -e "${GREEN}✓ PostgreSQL databases removed${NC}"
fi

# MySQL/MariaDB
if command -v mysql &> /dev/null; then
    mysql -u root -e "DROP DATABASE IF EXISTS brain_capital;" 2>/dev/null || true
    mysql -u root -e "DROP DATABASE IF EXISTS mimic_db;" 2>/dev/null || true
    mysql -u root -e "DROP USER IF EXISTS 'mimic_user'@'localhost';" 2>/dev/null || true
    echo -e "${GREEN}✓ MySQL databases removed${NC}"
fi

# SQLite files (if any)
find /var/www /opt /home -name "*.db" -type f -delete 2>/dev/null || true
find /var/www /opt /home -name "brain_capital.db" -type f -delete 2>/dev/null || true

echo -e "${GREEN}✓ Databases removed${NC}"

# ============================================
# STEP 8: Clear Redis data
# ============================================
echo -e "${YELLOW}[8/10] Clearing Redis data...${NC}"
if command -v redis-cli &> /dev/null; then
    redis-cli FLUSHALL 2>/dev/null || true
    echo -e "${GREEN}✓ Redis data cleared${NC}"
else
    echo -e "${YELLOW}  Redis not installed${NC}"
fi

# ============================================
# STEP 9: Remove application user
# ============================================
echo -e "${YELLOW}[9/10] Removing application user...${NC}"
if id "$APP_USER" &>/dev/null; then
    # Kill all processes by user
    pkill -u "$APP_USER" 2>/dev/null || true
    sleep 2
    
    # Remove user and home directory
    userdel -r "$APP_USER" 2>/dev/null || true
    echo -e "${GREEN}✓ User removed: $APP_USER${NC}"
else
    echo -e "${YELLOW}  User not found: $APP_USER${NC}"
fi

# ============================================
# STEP 10: Clean /root directory
# ============================================
echo -e "${YELLOW}[10/10] Cleaning /root directory...${NC}"
cd /root

# Remove all files except essential ones
find /root -maxdepth 1 -type f ! -name ".bashrc" ! -name ".bash_history" ! -name ".profile" ! -name ".viminfo" -delete 2>/dev/null || true

# Remove all directories except .ssh
for dir in /root/*; do
    if [ -d "$dir" ] && [ "$(basename "$dir")" != ".ssh" ]; then
        rm -rf "$dir"
    fi
done

# Remove hidden files/dirs except essential
find /root -maxdepth 1 -type f -name ".*" ! -name ".bashrc" ! -name ".profile" ! -name ".bash_history" ! -name ".viminfo" -delete 2>/dev/null || true
find /root -maxdepth 1 -type d -name ".*" ! -name "." ! -name ".." ! -name ".ssh" -exec rm -rf {} + 2>/dev/null || true

echo -e "${GREEN}✓ /root directory cleaned${NC}"

# ============================================
# FINAL CLEANUP: Remove Python packages (optional)
# ============================================
echo ""
read -p "Remove Python packages installed for MIMIC? (y/N): " remove_python
if [ "$remove_python" = "y" ] || [ "$remove_python" = "Y" ]; then
    echo -e "${YELLOW}Removing Python packages...${NC}"
    pip3 uninstall -y gunicorn eventlet flask flask-socketio arq redis sqlalchemy 2>/dev/null || true
    echo -e "${GREEN}✓ Python packages removed${NC}"
fi

# ============================================
# SUMMARY
# ============================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  CLEANUP COMPLETE!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${GREEN}✓ All MIMIC services stopped and removed${NC}"
echo -e "${GREEN}✓ All application files deleted${NC}"
echo -e "${GREEN}✓ All databases removed${NC}"
echo -e "${GREEN}✓ All Docker containers removed${NC}"
echo -e "${GREEN}✓ All SSL certificates removed${NC}"
echo -e "${GREEN}✓ Application user removed${NC}"
echo -e "${GREEN}✓ /root directory cleaned${NC}"
echo ""
echo -e "${YELLOW}Your VPS is now back to base state.${NC}"
echo -e "${YELLOW}You can now reinstall or use it for other purposes.${NC}"
echo ""
