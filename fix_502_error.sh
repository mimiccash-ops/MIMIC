#!/bin/bash
#
# Fix 502 Bad Gateway Error
# ==========================
#
# This script diagnoses and fixes 502 Bad Gateway errors
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
echo -e "${CYAN}║        Fixing 502 Bad Gateway Error                        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

INSTALL_PATH="/var/www/mimic"

cd "$INSTALL_PATH"

# Check what's running
echo -e "${CYAN}ℹ️  Checking running services...${NC}"
echo ""

# Check if Docker is running
if docker ps 2>/dev/null | grep -q mimic; then
    echo -e "${GREEN}✅ Docker containers are running${NC}"
    DOCKER_MODE=true
    
    # Check Docker web container
    if docker ps | grep -q brain_capital_web; then
        echo -e "${GREEN}✅ Docker web container is running${NC}"
        echo -e "${CYAN}ℹ️  Checking Docker web container port...${NC}"
        docker port brain_capital_web | grep 5000 || echo -e "${YELLOW}⚠️  Web container not exposing port 5000${NC}"
    else
        echo -e "${RED}❌ Docker web container is NOT running${NC}"
    fi
else
    DOCKER_MODE=false
    echo -e "${YELLOW}⚠️  Docker containers not found${NC}"
fi

# Check if systemd service is running
if systemctl is-active --quiet mimic; then
    echo -e "${GREEN}✅ Systemd mimic.service is running${NC}"
    SYSTEMD_MODE=true
    
    # Check what port Gunicorn is listening on
    echo -e "${CYAN}ℹ️  Checking Gunicorn port...${NC}"
    if ss -tlnp | grep -q ":8000"; then
        echo -e "${GREEN}✅ Gunicorn is listening on port 8000${NC}"
    elif ss -tlnp | grep -q ":5000"; then
        echo -e "${GREEN}✅ Gunicorn is listening on port 5000${NC}"
    else
        echo -e "${RED}❌ Gunicorn is NOT listening on any port${NC}"
    fi
else
    SYSTEMD_MODE=false
    echo -e "${YELLOW}⚠️  Systemd mimic.service is NOT running${NC}"
fi

echo ""

# Check Nginx configuration
echo -e "${CYAN}ℹ️  Checking Nginx configuration...${NC}"
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✅ Nginx is running${NC}"
    
    # Check what port Nginx expects
    if grep -q "127.0.0.1:5000" /etc/nginx/nginx.conf 2>/dev/null || grep -q "127.0.0.1:5000" /etc/nginx/sites-enabled/* 2>/dev/null; then
        echo -e "${CYAN}ℹ️  Nginx expects backend on port 5000${NC}"
        NGINX_PORT=5000
    elif grep -q "127.0.0.1:8000" /etc/nginx/nginx.conf 2>/dev/null || grep -q "127.0.0.1:8000" /etc/nginx/sites-enabled/* 2>/dev/null; then
        echo -e "${CYAN}ℹ️  Nginx expects backend on port 8000${NC}"
        NGINX_PORT=8000
    else
        echo -e "${YELLOW}⚠️  Could not determine Nginx backend port${NC}"
        NGINX_PORT="unknown"
    fi
else
    echo -e "${RED}❌ Nginx is NOT running${NC}"
    echo -e "${CYAN}ℹ️  Starting Nginx...${NC}"
    systemctl start nginx
fi

echo ""

# Diagnose the issue
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}DIAGNOSIS:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ "$DOCKER_MODE" == true ]]; then
    echo -e "${CYAN}Mode: Docker${NC}"
    echo -e "${CYAN}Nginx expects: port $NGINX_PORT${NC}"
    echo ""
    echo -e "${YELLOW}Solution:${NC}"
    echo "  1. Check Docker web container is running: docker ps | grep web"
    echo "  2. Check Docker web container port: docker port brain_capital_web"
    echo "  3. Ensure docker-compose.yml maps port 5000:5000"
    echo "  4. Restart Docker: docker compose restart web"
    
elif [[ "$SYSTEMD_MODE" == true" ]]; then
    echo -e "${CYAN}Mode: Systemd${NC}"
    echo -e "${CYAN}Nginx expects: port $NGINX_PORT${NC}"
    echo -e "${CYAN}Gunicorn listens: port 8000 (from mimic.service)${NC}"
    echo ""
    
    if [[ "$NGINX_PORT" == "5000" ]]; then
        echo -e "${RED}❌ PORT MISMATCH!${NC}"
        echo -e "${YELLOW}Nginx expects port 5000, but Gunicorn listens on port 8000${NC}"
        echo ""
        echo -e "${CYAN}Solution:${NC}"
        echo "  Option 1: Change mimic.service to use port 5000"
        echo "  Option 2: Change Nginx to use port 8000"
        echo ""
        echo -e "${CYAN}Quick fix (change Gunicorn to port 5000):${NC}"
        echo "  sudo sed -i 's/--bind 127.0.0.1:8000/--bind 127.0.0.1:5000/g' /etc/systemd/system/mimic.service"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl restart mimic"
    else
        echo -e "${GREEN}✅ Ports match${NC}"
    fi
else
    echo -e "${RED}❌ Neither Docker nor Systemd service is running!${NC}"
    echo ""
    echo -e "${CYAN}Solution:${NC}"
    echo "  Start the service:"
    echo "    sudo systemctl start mimic"
    echo "    OR"
    echo "    docker compose up -d"
fi

echo ""

# Check if backend is accessible
echo -e "${CYAN}ℹ️  Testing backend connection...${NC}"
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is accessible on port 5000${NC}"
elif curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is accessible on port 8000${NC}"
    echo -e "${YELLOW}⚠️  But Nginx may be configured for port 5000${NC}"
else
    echo -e "${RED}❌ Backend is NOT accessible on ports 5000 or 8000${NC}"
fi

echo ""
echo -e "${CYAN}ℹ️  Checking Nginx error logs...${NC}"
tail -5 /var/log/nginx/error.log 2>/dev/null || echo "No error log found"

echo ""
