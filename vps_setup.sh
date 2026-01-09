#!/bin/bash
#
# MIMIC - VPS Initial Setup Script
# ==================================
#
# Run this ONCE on your VPS to set up the environment.
# Then use deploy.sh from your local machine to push updates.
#
# USAGE:
#   curl -sSL https://your-repo/vps_setup.sh | bash
#   # OR
#   wget -qO- https://your-repo/vps_setup.sh | bash
#   # OR
#   chmod +x vps_setup.sh && sudo ./vps_setup.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║           MIMIC - VPS Initial Setup                          ║${NC}"
echo -e "${CYAN}║                  https://mimic.cash                          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Configuration
APP_DIR="/var/www/mimic"
LOG_DIR="/var/log/mimic"
APP_USER="www-data"
PYTHON_VERSION="3.11"

echo -e "${CYAN}[1/7] Updating system packages...${NC}"
apt update && apt upgrade -y

echo -e "${CYAN}[2/7] Installing required packages...${NC}"
apt install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    nginx \
    redis-server \
    postgresql \
    postgresql-contrib \
    certbot \
    python3-certbot-nginx \
    supervisor \
    git \
    curl \
    wget \
    htop \
    ufw

# Create Python symlink if needed
if ! command -v python3 &> /dev/null; then
    ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3
fi

echo -e "${CYAN}[3/7] Creating application directories...${NC}"
mkdir -p $APP_DIR
mkdir -p $LOG_DIR
mkdir -p $APP_DIR/static/avatars

# Set permissions
chown -R $APP_USER:$APP_USER $APP_DIR
chown -R $APP_USER:$APP_USER $LOG_DIR
chmod -R 755 $APP_DIR

echo -e "${CYAN}[4/7] Setting up Python virtual environment...${NC}"
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install gunicorn gevent gevent-websocket

echo -e "${CYAN}[5/7] Setting up systemd service...${NC}"
cat > /etc/systemd/system/mimic.service << 'SERVICEEOF'
[Unit]
Description=MIMIC Copy Trading Platform
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/mimic
Environment="FLASK_ENV=production"
Environment="PYTHONUNBUFFERED=1"
Environment="PATH=/var/www/mimic/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=-/var/www/mimic/.env
ExecStart=/var/www/mimic/venv/bin/gunicorn \
    --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
    --workers 4 \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --access-logfile /var/log/mimic/access.log \
    --error-logfile /var/log/mimic/error.log \
    app:app
Restart=always
RestartSec=10
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable mimic

echo -e "${CYAN}[6/7] Setting up Nginx reverse proxy...${NC}"
cat > /etc/nginx/sites-available/mimic << 'NGINXEOF'
server {
    listen 80;
    server_name _;  # Replace with your domain

    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
    }

    location /static/ {
        alias /var/www/mimic/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
NGINXEOF

# Enable site
ln -sf /etc/nginx/sites-available/mimic /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo -e "${CYAN}[7/7] Configuring firewall...${NC}"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  VPS SETUP COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Deploy your code: ${CYAN}./deploy.sh${NC} (from local machine)"
echo -e "  2. Install dependencies: ${CYAN}cd $APP_DIR && source venv/bin/activate && pip install -r requirements.txt${NC}"
echo -e "  3. Generate .env file: ${CYAN}python setup_env.py${NC}"
echo -e "  4. Copy config: ${CYAN}cp config.ini.example config.ini${NC}"
echo -e "  5. Start service: ${CYAN}sudo systemctl start mimic${NC}"
echo -e "  6. (Optional) Add SSL: ${CYAN}sudo certbot --nginx -d yourdomain.com${NC}"
echo ""
echo -e "Useful commands:"
echo -e "  ${CYAN}sudo systemctl status mimic${NC}     - Check status"
echo -e "  ${CYAN}sudo journalctl -u mimic -f${NC}     - View logs"
echo -e "  ${CYAN}sudo systemctl restart mimic${NC}   - Restart"
echo ""
