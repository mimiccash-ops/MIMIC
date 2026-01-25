#!/bin/bash
#
# Fix Installation Issues on VPS
# ================================
#
# This script fixes common issues after installation:
# 1. Removes invalid Sentry DSN from .env
# 2. Fixes Redis service
# 3. Runs migrations properly
#

set -e

INSTALL_PATH="/var/www/mimic"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        Fixing Installation Issues                           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

cd "$INSTALL_PATH"

# Fix 1: Remove invalid Sentry DSN from .env
echo -e "${CYAN}ℹ️  Fixing Sentry DSN in .env...${NC}"
if [[ -f .env ]]; then
    # Remove or comment out invalid Sentry DSN
    sed -i 's/^SENTRY_DSN=.*project-id.*/# SENTRY_DSN=  # Optional: Add your Sentry DSN here/' .env
    sed -i 's/^SENTRY_DSN=.*your-sentry-dsn.*/# SENTRY_DSN=  # Optional: Add your Sentry DSN here/' .env
    echo -e "${GREEN}✅ Sentry DSN fixed${NC}"
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
fi
echo ""

# Fix 2: Redis service
echo -e "${CYAN}ℹ️  Checking Redis service...${NC}"
if command -v redis-cli &> /dev/null; then
    # Check if Redis is running
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✅ Redis is running${NC}"
    else
        # Try to start Redis (Ubuntu 24.04 might use different service name)
        if systemctl start redis-server 2>/dev/null || systemctl start redis 2>/dev/null; then
            echo -e "${GREEN}✅ Redis started${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not start Redis automatically. Try manually:${NC}"
            echo "   sudo systemctl start redis-server"
            echo "   or"
            echo "   sudo systemctl start redis"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Redis not installed${NC}"
fi
echo ""

# Fix 3: Run migrations again (now that Sentry is fixed)
echo -e "${CYAN}ℹ️  Running database migrations...${NC}"
if [[ -f migrations/migrate.py ]] && [[ -d venv ]]; then
    source venv/bin/activate
    python migrations/migrate.py
    echo -e "${GREEN}✅ Migrations completed${NC}"
else
    echo -e "${YELLOW}⚠️  Migration script not found${NC}"
fi
echo ""

# Fix 4: Check file permissions
echo -e "${CYAN}ℹ️  Checking file permissions...${NC}"
chown -R mimic:mimic "$INSTALL_PATH" 2>/dev/null || echo -e "${YELLOW}⚠️  Could not change ownership (may need to run as root)${NC}"
chmod 600 "$INSTALL_PATH/.env" 2>/dev/null || true
chmod 600 "$INSTALL_PATH/config.ini" 2>/dev/null || true
echo -e "${GREEN}✅ Permissions checked${NC}"
echo ""

echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Fixes Applied!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "  1. Edit /var/www/mimic/.env and add your configuration"
echo "  2. Edit /var/www/mimic/config.ini and add your API keys"
echo "  3. Start services:"
echo "     sudo systemctl start mimic"
echo "     sudo systemctl start mimic-worker"
echo "     sudo systemctl start mimic-bot"
echo "  4. Check status:"
echo "     sudo systemctl status mimic"
echo ""
