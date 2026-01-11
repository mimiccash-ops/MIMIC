#!/bin/bash
# =============================================================================
# WEBHOOK FIX DEPLOYMENT SCRIPT
# =============================================================================
# This script applies all the webhook fixes to your VPS server
# Run this on your VPS to fix webhook issues immediately
# =============================================================================

set -e  # Exit on error

echo "============================================"
echo "  WEBHOOK FIX DEPLOYMENT"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Check if running as root or with sudo
if [ "$EUID" -eq 0 ]; then
    print_warning "Running as root. This is okay, but not required."
fi

# Check if nginx is installed
if ! command -v nginx &> /dev/null; then
    print_error "Nginx is not installed!"
    echo "Install it with: sudo apt install nginx -y"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed!"
    echo "Install it first, then re-run this script."
    exit 1
fi

echo ""
print_info "Step 1: Backing up current nginx configuration..."

# Backup current nginx config
if [ -f /etc/nginx/nginx.conf ]; then
    sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
    print_success "Nginx config backed up"
else
    print_warning "No existing nginx config found"
fi

echo ""
print_info "Step 2: Installing new nginx configuration..."

# Check if nginx.conf.production exists
if [ ! -f "./nginx.conf.production" ]; then
    print_error "nginx.conf.production not found in current directory!"
    echo "Make sure you're running this script from the MIMIC project directory."
    exit 1
fi

# Copy new config
sudo cp nginx.conf.production /etc/nginx/nginx.conf
print_success "New nginx config installed"

echo ""
print_info "Step 3: Testing nginx configuration..."

# Test nginx config
if sudo nginx -t; then
    print_success "Nginx configuration is valid!"
else
    print_error "Nginx configuration has errors!"
    echo "Restoring backup..."
    sudo cp /etc/nginx/nginx.conf.backup.* /etc/nginx/nginx.conf 2>/dev/null || true
    exit 1
fi

echo ""
print_info "Step 4: Reloading nginx..."

# Reload nginx
if sudo systemctl reload nginx; then
    print_success "Nginx reloaded successfully"
else
    print_error "Failed to reload nginx"
    exit 1
fi

echo ""
print_info "Step 5: Checking Docker containers..."

# Check if containers are running
if docker-compose ps | grep -q "Up"; then
    print_success "Docker containers are running"
    
    echo ""
    print_info "Step 6: Restarting Docker services..."
    
    # Restart containers
    docker-compose down
    docker-compose up -d
    
    # Wait for services to start
    print_info "Waiting for services to start (15 seconds)..."
    sleep 15
    
    if docker-compose ps | grep -q "Up"; then
        print_success "Docker services restarted successfully"
    else
        print_error "Some Docker services failed to start"
        echo "Check logs with: docker-compose logs"
        exit 1
    fi
else
    print_warning "Docker containers are not running"
    echo "Starting containers..."
    docker-compose up -d
    sleep 15
fi

echo ""
print_info "Step 7: Verifying services..."

# Check nginx
if sudo systemctl is-active --quiet nginx; then
    print_success "Nginx is running"
else
    print_error "Nginx is not running"
fi

# Check web container
if docker-compose ps web | grep -q "Up"; then
    print_success "Web container is running"
else
    print_error "Web container is not running"
fi

# Check worker container
if docker-compose ps worker | grep -q "Up"; then
    print_success "Worker container is running"
else
    print_error "Worker container is not running"
fi

echo ""
echo "============================================"
echo "  DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""

# Get VPS IP
VPS_IP=$(hostname -I | awk '{print $1}')

print_success "Webhook fixes have been applied!"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1️⃣  Test your webhook endpoint:"
echo "   From your local machine, run:"
echo "   python test_webhook.py --url $VPS_IP --no-https"
echo ""
echo "2️⃣  Configure TradingView:"
echo "   Webhook URL: http://$VPS_IP/webhook"
echo "   Or if you have a domain: https://your-domain.com/webhook"
echo ""
echo "3️⃣  Alert Message Format:"
echo '   {"passphrase":"mimiccashadministrator","symbol":"{{ticker}}","action":"long","leverage":10,"risk_perc":2,"tp_perc":5,"sl_perc":2}'
echo ""
echo "4️⃣  Monitor webhook logs:"
echo "   sudo tail -f /var/log/nginx/webhook_access.log"
echo "   docker-compose logs -f web | grep -i webhook"
echo ""
echo "============================================"
echo ""

# Show current webhook passphrase
if [ -f .env ]; then
    PASSPHRASE=$(grep WEBHOOK_PASSPHRASE .env | cut -d'=' -f2)
    if [ ! -z "$PASSPHRASE" ]; then
        echo "🔐 Your webhook passphrase: $PASSPHRASE"
        echo ""
        print_warning "SECURITY: Change this passphrase in production!"
        echo "   Edit .env file and update WEBHOOK_PASSPHRASE"
        echo "   Then restart: docker-compose restart web"
        echo ""
    fi
fi

print_success "Ready to receive TradingView webhooks! 🚀"
