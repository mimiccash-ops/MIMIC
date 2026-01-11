#!/bin/bash
# =============================================================================
# SETUP VERIFICATION SCRIPT
# =============================================================================
# Run this on your VPS to verify everything is configured correctly
# =============================================================================

echo "============================================"
echo "  MIMIC SETUP VERIFICATION"
echo "============================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASS_COUNT++))
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAIL_COUNT++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
    ((WARN_COUNT++))
}

echo "📋 Running system checks..."
echo ""

# Check 1: Nginx installed and running
echo "1. Checking Nginx..."
if command -v nginx &> /dev/null; then
    if sudo systemctl is-active --quiet nginx; then
        check_pass "Nginx is installed and running"
    else
        check_fail "Nginx is installed but not running"
        echo "   Fix: sudo systemctl start nginx"
    fi
else
    check_fail "Nginx is not installed"
    echo "   Fix: sudo apt install nginx -y"
fi

# Check 2: Nginx config port
echo "2. Checking Nginx configuration..."
if [ -f /etc/nginx/nginx.conf ]; then
    if sudo grep -q "server 127.0.0.1:5000" /etc/nginx/nginx.conf; then
        check_pass "Nginx configured for port 5000"
    elif sudo grep -q "server 127.0.0.1:8000" /etc/nginx/nginx.conf; then
        check_fail "Nginx still configured for port 8000 (should be 5000)"
        echo "   Fix: Run ./deploy_webhook_fix.sh"
    else
        check_warn "Cannot verify nginx port configuration"
    fi
else
    check_fail "Nginx config not found"
fi

# Check 3: Nginx webhook location
echo "3. Checking Nginx webhook endpoint..."
if sudo grep -q "location = /webhook" /etc/nginx/nginx.conf; then
    check_pass "Webhook location configured in nginx"
else
    check_warn "No dedicated webhook location in nginx"
    echo "   Info: Webhook will use default location rules"
fi

# Check 4: Docker installed
echo "4. Checking Docker..."
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        check_pass "Docker is installed and running"
    else
        check_fail "Docker is installed but cannot connect"
        echo "   Fix: sudo systemctl start docker"
    fi
else
    check_fail "Docker is not installed"
fi

# Check 5: Docker Compose installed
echo "5. Checking Docker Compose..."
if command -v docker-compose &> /dev/null; then
    check_pass "Docker Compose is installed"
else
    check_fail "Docker Compose is not installed"
fi

# Check 6: Docker containers running
echo "6. Checking Docker containers..."
if docker-compose ps &> /dev/null; then
    WEB_STATUS=$(docker-compose ps web | grep "Up" || echo "Down")
    WORKER_STATUS=$(docker-compose ps worker | grep "Up" || echo "Down")
    DB_STATUS=$(docker-compose ps db | grep "Up" || echo "Down")
    REDIS_STATUS=$(docker-compose ps redis | grep "Up" || echo "Down")
    
    if [[ $WEB_STATUS == *"Up"* ]]; then
        check_pass "Web container is running"
    else
        check_fail "Web container is not running"
        echo "   Fix: docker-compose up -d web"
    fi
    
    if [[ $WORKER_STATUS == *"Up"* ]]; then
        check_pass "Worker container is running"
    else
        check_fail "Worker container is not running"
        echo "   Fix: docker-compose up -d worker"
    fi
    
    if [[ $DB_STATUS == *"Up"* ]]; then
        check_pass "Database container is running"
    else
        check_fail "Database container is not running"
        echo "   Fix: docker-compose up -d db"
    fi
    
    if [[ $REDIS_STATUS == *"Up"* ]]; then
        check_pass "Redis container is running"
    else
        check_fail "Redis container is not running"
        echo "   Fix: docker-compose up -d redis"
    fi
else
    check_fail "Cannot check Docker containers (not in project directory?)"
fi

# Check 7: .env file exists
echo "7. Checking environment configuration..."
if [ -f .env ]; then
    check_pass ".env file exists"
    
    # Check critical env vars
    if grep -q "FLASK_SECRET_KEY=" .env && ! grep -q "FLASK_SECRET_KEY=\${" .env; then
        check_pass "FLASK_SECRET_KEY is set"
    else
        check_fail "FLASK_SECRET_KEY is not configured"
    fi
    
    if grep -q "WEBHOOK_PASSPHRASE=" .env && ! grep -q "WEBHOOK_PASSPHRASE=\${" .env; then
        check_pass "WEBHOOK_PASSPHRASE is set"
    else
        check_fail "WEBHOOK_PASSPHRASE is not configured"
    fi
    
    if grep -q "BINANCE_MASTER_API_KEY=" .env && ! grep -q "BINANCE_MASTER_API_KEY=\${" .env; then
        check_pass "Binance API key is configured"
    else
        check_fail "Binance API key is not configured"
    fi
    
    if grep -q "DATABASE_URL=" .env && ! grep -q "DATABASE_URL=\${" .env; then
        check_pass "Database URL is configured"
    else
        check_warn "Database URL not in .env (might be using default)"
    fi
else
    check_fail ".env file not found"
    echo "   Fix: cp production.env.example .env && edit .env"
fi

# Check 8: Firewall
echo "8. Checking firewall..."
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(sudo ufw status | grep "Status:" | awk '{print $2}')
    if [ "$UFW_STATUS" == "active" ]; then
        check_pass "Firewall is active"
        
        if sudo ufw status | grep -q "80/tcp"; then
            check_pass "Port 80 (HTTP) is allowed"
        else
            check_warn "Port 80 (HTTP) is not allowed"
            echo "   Fix: sudo ufw allow 80/tcp"
        fi
        
        if sudo ufw status | grep -q "443/tcp"; then
            check_pass "Port 443 (HTTPS) is allowed"
        else
            check_warn "Port 443 (HTTPS) is not allowed"
            echo "   Fix: sudo ufw allow 443/tcp"
        fi
    else
        check_warn "Firewall is not active"
        echo "   Info: Enable with: sudo ufw enable"
    fi
else
    check_warn "UFW firewall not installed"
fi

# Check 9: Webhook endpoint accessibility
echo "9. Checking webhook endpoint..."
if curl -f -s http://localhost:5000/webhook -X POST -H "Content-Type: application/json" -d '{}' > /dev/null 2>&1; then
    check_pass "Webhook endpoint is accessible"
elif curl -f -s http://localhost:5000/health > /dev/null 2>&1; then
    check_pass "Application is responding (webhook needs passphrase)"
else
    check_fail "Cannot reach application on localhost:5000"
    echo "   Fix: Check if web container is running"
fi

# Check 10: SSL Certificate (if HTTPS enabled)
echo "10. Checking SSL certificate..."
if [ -f /etc/letsencrypt/live/*/fullchain.pem ]; then
    check_pass "SSL certificate found"
    
    # Check expiration
    DOMAIN=$(ls /etc/letsencrypt/live/ | head -n1)
    if [ ! -z "$DOMAIN" ]; then
        EXPIRY=$(sudo openssl x509 -enddate -noout -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem | cut -d= -f2)
        echo "   Info: Certificate expires: $EXPIRY"
    fi
else
    check_warn "No SSL certificate found"
    echo "   Info: Set up with: sudo certbot --nginx"
fi

# Summary
echo ""
echo "============================================"
echo "  VERIFICATION SUMMARY"
echo "============================================"
echo ""
echo -e "${GREEN}Passed${NC}: $PASS_COUNT checks"
echo -e "${YELLOW}Warnings${NC}: $WARN_COUNT checks"
echo -e "${RED}Failed${NC}: $FAIL_COUNT checks"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ SYSTEM READY!${NC}"
    echo ""
    echo "Your system is properly configured."
    echo ""
    echo "Next steps:"
    echo "1. Test webhook: python test_webhook.py --url $(hostname -I | awk '{print $1}')"
    echo "2. Configure TradingView alerts"
    echo "3. Monitor logs: docker-compose logs -f"
else
    echo -e "${RED}⚠️ ISSUES FOUND${NC}"
    echo ""
    echo "Please fix the failed checks above before proceeding."
    echo ""
    echo "Common fixes:"
    echo "- Deploy webhook fix: ./deploy_webhook_fix.sh"
    echo "- Start services: docker-compose up -d"
    echo "- Configure .env: cp production.env.example .env && nano .env"
fi

echo ""
echo "============================================"
