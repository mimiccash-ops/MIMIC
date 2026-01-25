#!/bin/bash
#
# MIMIC - Automated Linux VPS Installation Script
# ================================================
#
# This script automatically:
#   1. Clones the repository from GitHub
#   2. Installs all system dependencies
#   3. Sets up Python virtual environment
#   4. Installs Python packages
#   5. Configures PostgreSQL database
#   6. Sets up Redis
#   7. Creates systemd services
#   8. Configures Nginx (optional)
#   9. Sets up firewall
#
# USAGE:
#   sudo ./install_vps.sh                    # Install to /var/www/mimic
#   sudo ./install_vps.sh /custom/path       # Install to custom path
#   sudo ./install_vps.sh --skip-nginx       # Skip Nginx setup
#   sudo ./install_vps.sh --skip-db          # Skip PostgreSQL setup
#
# REQUIREMENTS:
#   - Ubuntu 22.04+ or Debian 11+
#   - Root/sudo access
#   - Internet connection
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GITHUB_REPO="https://github.com/mimiccash-ops/MIMIC.git"
INSTALL_PATH="/var/www/mimic"
APP_USER="mimic"
SKIP_NGINX=false
SKIP_DB=false
SKIP_REDIS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-nginx)
            SKIP_NGINX=true
            shift
            ;;
        --skip-db)
            SKIP_DB=true
            shift
            ;;
        --skip-redis)
            SKIP_REDIS=true
            shift
            ;;
        --help|-h)
            echo ""
            echo "MIMIC Automated VPS Installation Script"
            echo ""
            echo "Usage: sudo $0 [OPTIONS] [INSTALL_PATH]"
            echo ""
            echo "Options:"
            echo "  --skip-nginx    Skip Nginx installation and configuration"
            echo "  --skip-db       Skip PostgreSQL installation and setup"
            echo "  --skip-redis    Skip Redis installation"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Examples:"
            echo "  sudo $0                          # Install to /var/www/mimic"
            echo "  sudo $0 /opt/mimic               # Install to custom path"
            echo "  sudo $0 --skip-nginx            # Skip Nginx setup"
            echo ""
            exit 0
            ;;
        *)
            if [[ -z "$INSTALL_PATH" ]] || [[ "$INSTALL_PATH" == "/var/www/mimic" ]]; then
                INSTALL_PATH="$1"
            fi
            shift
            ;;
    esac
done

# Banner
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     MIMIC - Automated Linux VPS Installation Script          ║${NC}"
echo -e "${CYAN}║              https://github.com/mimiccash-ops/MIMIC           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Check OS
if [[ ! -f /etc/os-release ]]; then
    echo -e "${RED}❌ Cannot detect OS version${NC}"
    exit 1
fi

source /etc/os-release
echo -e "${CYAN}ℹ️  Detected OS: ${ID} ${VERSION_ID}${NC}"
echo ""

# ============================================================================
# STEP 1: Update System & Install Base Dependencies
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}STEP 1: Updating System & Installing Base Dependencies${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}ℹ️  Updating package lists...${NC}"
apt update -qq

echo -e "${CYAN}ℹ️  Installing base dependencies...${NC}"
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    wget \
    build-essential \
    libpq-dev \
    supervisor \
    ufw \
    > /dev/null 2>&1

# Install Node.js (for Tailwind CSS build)
if ! command -v node &> /dev/null; then
    echo -e "${CYAN}ℹ️  Installing Node.js...${NC}"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt install -y nodejs > /dev/null 2>&1
fi

echo -e "${GREEN}✅ Base dependencies installed${NC}"
echo ""

# ============================================================================
# STEP 2: Create Application User
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}STEP 2: Creating Application User${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if id "$APP_USER" &>/dev/null; then
    echo -e "${YELLOW}⚠️  User '$APP_USER' already exists, skipping...${NC}"
else
    echo -e "${CYAN}ℹ️  Creating user '$APP_USER'...${NC}"
    useradd -m -s /bin/bash "$APP_USER" || true
    usermod -aG sudo "$APP_USER" || true
    echo -e "${GREEN}✅ User '$APP_USER' created${NC}"
fi
echo ""

# ============================================================================
# STEP 3: Clone Repository from GitHub
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}STEP 3: Cloning Repository from GitHub${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}ℹ️  Repository: ${GITHUB_REPO}${NC}"
echo -e "${CYAN}ℹ️  Install path: ${INSTALL_PATH}${NC}"
echo ""

# Create directory
mkdir -p "$INSTALL_PATH"
chown "$APP_USER:$APP_USER" "$INSTALL_PATH"

# Clone or update repository
if [[ -d "$INSTALL_PATH/.git" ]]; then
    echo -e "${YELLOW}⚠️  Repository already exists, pulling latest changes...${NC}"
    cd "$INSTALL_PATH"
    sudo -u "$APP_USER" git pull origin main || sudo -u "$APP_USER" git pull origin master
else
    echo -e "${CYAN}ℹ️  Cloning repository...${NC}"
    sudo -u "$APP_USER" git clone "$GITHUB_REPO" "$INSTALL_PATH"
fi

cd "$INSTALL_PATH"
echo -e "${GREEN}✅ Repository cloned/updated${NC}"
echo ""

# ============================================================================
# STEP 4: Set Up Python Virtual Environment
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}STEP 4: Setting Up Python Virtual Environment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ -d "$INSTALL_PATH/venv" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists${NC}"
else
    echo -e "${CYAN}ℹ️  Creating virtual environment...${NC}"
    sudo -u "$APP_USER" python3 -m venv "$INSTALL_PATH/venv"
fi

echo -e "${CYAN}ℹ️  Upgrading pip...${NC}"
sudo -u "$APP_USER" "$INSTALL_PATH/venv/bin/pip" install --upgrade pip --quiet

echo -e "${CYAN}ℹ️  Installing Python dependencies (this may take a few minutes)...${NC}"
sudo -u "$APP_USER" "$INSTALL_PATH/venv/bin/pip" install -r "$INSTALL_PATH/requirements.txt" --quiet

# Install production server
echo -e "${CYAN}ℹ️  Installing production server (gunicorn)...${NC}"
sudo -u "$APP_USER" "$INSTALL_PATH/venv/bin/pip" install gunicorn eventlet --quiet

echo -e "${GREEN}✅ Python environment set up${NC}"
echo ""

# ============================================================================
# STEP 5: Install Node.js Dependencies & Build Frontend
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}STEP 5: Building Frontend${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ -f "$INSTALL_PATH/package.json" ]]; then
    echo -e "${CYAN}ℹ️  Installing Node.js dependencies...${NC}"
    cd "$INSTALL_PATH"
    sudo -u "$APP_USER" npm install --silent
    
    echo -e "${CYAN}ℹ️  Building frontend CSS...${NC}"
    sudo -u "$APP_USER" npm run build --silent || echo -e "${YELLOW}⚠️  Frontend build may have warnings (continuing...)${NC}"
    echo -e "${GREEN}✅ Frontend built${NC}"
else
    echo -e "${YELLOW}⚠️  No package.json found, skipping frontend build${NC}"
fi
echo ""

# ============================================================================
# STEP 6: PostgreSQL Setup
# ============================================================================
if [[ "$SKIP_DB" == false ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}STEP 6: Setting Up PostgreSQL Database${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if ! command -v psql &> /dev/null; then
        echo -e "${CYAN}ℹ️  Installing PostgreSQL...${NC}"
        apt install -y postgresql postgresql-contrib > /dev/null 2>&1
        systemctl start postgresql
        systemctl enable postgresql
    else
        echo -e "${YELLOW}⚠️  PostgreSQL already installed${NC}"
    fi

    # Generate random password
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    DB_USER="mimic_user"
    DB_NAME="mimic_db"

    echo -e "${CYAN}ℹ️  Creating database and user...${NC}"
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || echo -e "${YELLOW}⚠️  User may already exist${NC}"
    sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || echo -e "${YELLOW}⚠️  Database may already exist${NC}"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null || true

    echo -e "${GREEN}✅ PostgreSQL database created${NC}"
    echo -e "${CYAN}ℹ️  Database URL: postgresql://$DB_USER:****@localhost:5432/$DB_NAME${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠️  Skipping PostgreSQL setup (--skip-db)${NC}"
    echo ""
fi

# ============================================================================
# STEP 7: Redis Setup
# ============================================================================
if [[ "$SKIP_REDIS" == false ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}STEP 7: Setting Up Redis${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if ! command -v redis-cli &> /dev/null; then
        echo -e "${CYAN}ℹ️  Installing Redis...${NC}"
        apt install -y redis-server > /dev/null 2>&1
        
        # Configure Redis
        sed -i 's/^supervised no/supervised systemd/' /etc/redis/redis.conf || true
        
        systemctl restart redis
        systemctl enable redis
        echo -e "${GREEN}✅ Redis installed and started${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis already installed${NC}"
        systemctl start redis || true
        systemctl enable redis || true
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  Skipping Redis setup (--skip-redis)${NC}"
    echo ""
fi

# ============================================================================
# STEP 8: Create Configuration Files
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}STEP 8: Creating Configuration Files${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

cd "$INSTALL_PATH"

# Create .env file if it doesn't exist
if [[ ! -f "$INSTALL_PATH/.env" ]]; then
    echo -e "${CYAN}ℹ️  Creating .env file...${NC}"
    if [[ -f "$INSTALL_PATH/production.env.example" ]]; then
        cp "$INSTALL_PATH/production.env.example" "$INSTALL_PATH/.env"
    else
        # Create basic .env
        cat > "$INSTALL_PATH/.env" << EOF
FLASK_ENV=production
HTTPS_ENABLED=true
FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
EOF
        if [[ "$SKIP_DB" == false ]]; then
            echo "DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME" >> "$INSTALL_PATH/.env"
        fi
        if [[ "$SKIP_REDIS" == false ]]; then
            echo "REDIS_URL=redis://localhost:6379/0" >> "$INSTALL_PATH/.env"
        fi
    fi
    chown "$APP_USER:$APP_USER" "$INSTALL_PATH/.env"
    chmod 600 "$INSTALL_PATH/.env"
    echo -e "${GREEN}✅ .env file created${NC}"
else
    echo -e "${YELLOW}⚠️  .env file already exists${NC}"
fi

# Create config.ini if it doesn't exist
if [[ ! -f "$INSTALL_PATH/config.ini" ]]; then
    echo -e "${CYAN}ℹ️  Creating config.ini file...${NC}"
    if [[ -f "$INSTALL_PATH/config.ini.example" ]]; then
        cp "$INSTALL_PATH/config.ini.example" "$INSTALL_PATH/config.ini"
        chown "$APP_USER:$APP_USER" "$INSTALL_PATH/config.ini"
        chmod 600 "$INSTALL_PATH/config.ini"
        echo -e "${GREEN}✅ config.ini file created (please edit with your API keys)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  config.ini file already exists${NC}"
fi

# Create secrets directory
mkdir -p "$INSTALL_PATH/secrets"
chmod 700 "$INSTALL_PATH/secrets"
chown "$APP_USER:$APP_USER" "$INSTALL_PATH/secrets"

# Generate master key if it doesn't exist
if [[ ! -f "$INSTALL_PATH/secrets/master.key" ]]; then
    echo -e "${CYAN}ℹ️  Generating encryption master key...${NC}"
    sudo -u "$APP_USER" "$INSTALL_PATH/venv/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > "$INSTALL_PATH/secrets/master.key"
    chmod 600 "$INSTALL_PATH/secrets/master.key"
    chown "$APP_USER:$APP_USER" "$INSTALL_PATH/secrets/master.key"
    echo -e "${GREEN}✅ Master key generated${NC}"
fi

# Create logs directory
mkdir -p "$INSTALL_PATH/logs"
chmod 755 "$INSTALL_PATH/logs"
chown "$APP_USER:$APP_USER" "$INSTALL_PATH/logs"

echo ""

# ============================================================================
# STEP 9: Run Database Migrations
# ============================================================================
if [[ "$SKIP_DB" == false ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}STEP 9: Running Database Migrations${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if [[ -f "$INSTALL_PATH/migrations/migrate.py" ]]; then
        echo -e "${CYAN}ℹ️  Running migrations...${NC}"
        cd "$INSTALL_PATH"
        sudo -u "$APP_USER" "$INSTALL_PATH/venv/bin/python" migrations/migrate.py || echo -e "${YELLOW}⚠️  Migration may have warnings (check manually)${NC}"
        echo -e "${GREEN}✅ Migrations completed${NC}"
    else
        echo -e "${YELLOW}⚠️  No migration script found${NC}"
    fi
    echo ""
fi

# ============================================================================
# STEP 10: Set Up Systemd Services
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}STEP 10: Setting Up Systemd Services${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Update service files with correct paths
SED_INSTALL_PATH=$(echo "$INSTALL_PATH" | sed 's/\//\\\//g')

# Main web service
if [[ -f "$INSTALL_PATH/mimic.service" ]]; then
    echo -e "${CYAN}ℹ️  Installing mimic.service...${NC}"
    sed "s/\/var\/www\/mimic/$SED_INSTALL_PATH/g" "$INSTALL_PATH/mimic.service" > /etc/systemd/system/mimic.service
    systemctl daemon-reload
    systemctl enable mimic
    echo -e "${GREEN}✅ mimic.service installed${NC}"
fi

# Worker service
if [[ -f "$INSTALL_PATH/mimic-worker.service" ]]; then
    echo -e "${CYAN}ℹ️  Installing mimic-worker.service...${NC}"
    sed "s/\/var\/www\/mimic/$SED_INSTALL_PATH/g" "$INSTALL_PATH/mimic-worker.service" > /etc/systemd/system/mimic-worker.service
    systemctl daemon-reload
    systemctl enable mimic-worker
    echo -e "${GREEN}✅ mimic-worker.service installed${NC}"
fi

# Bot service
if [[ -f "$INSTALL_PATH/mimic-bot.service" ]]; then
    echo -e "${CYAN}ℹ️  Installing mimic-bot.service...${NC}"
    sed "s/\/var\/www\/mimic/$SED_INSTALL_PATH/g" "$INSTALL_PATH/mimic-bot.service" > /etc/systemd/system/mimic-bot.service
    systemctl daemon-reload
    systemctl enable mimic-bot
    echo -e "${GREEN}✅ mimic-bot.service installed${NC}"
fi

echo ""

# ============================================================================
# STEP 11: Configure Firewall
# ============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}STEP 11: Configuring Firewall${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}ℹ️  Configuring UFW firewall...${NC}"
ufw allow 22/tcp comment 'SSH' || true
ufw allow 80/tcp comment 'HTTP' || true
ufw allow 443/tcp comment 'HTTPS' || true
ufw --force enable || true
echo -e "${GREEN}✅ Firewall configured${NC}"
echo ""

# ============================================================================
# STEP 12: Nginx Setup (Optional)
# ============================================================================
if [[ "$SKIP_NGINX" == false ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}STEP 12: Setting Up Nginx (Optional)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if ! command -v nginx &> /dev/null; then
        echo -e "${CYAN}ℹ️  Installing Nginx...${NC}"
        apt install -y nginx certbot python3-certbot-nginx > /dev/null 2>&1
    fi

    if [[ -f "$INSTALL_PATH/nginx.conf.production" ]]; then
        echo -e "${CYAN}ℹ️  Nginx configuration file found${NC}"
        echo -e "${YELLOW}⚠️  Please manually configure Nginx using:${NC}"
        echo -e "${CYAN}   $INSTALL_PATH/nginx.conf.production${NC}"
        echo -e "${CYAN}   See LINUX_DEPLOYMENT.md for detailed instructions${NC}"
    fi

    echo -e "${GREEN}✅ Nginx installed (configuration required)${NC}"
    echo ""
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ INSTALLATION COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Installation Path:${NC} $INSTALL_PATH"
echo -e "${CYAN}Application User:${NC} $APP_USER"
echo ""

if [[ "$SKIP_DB" == false ]]; then
    echo -e "${CYAN}Database Information:${NC}"
    echo -e "  User: $DB_USER"
    echo -e "  Database: $DB_NAME"
    echo -e "  Password: $DB_PASSWORD"
    echo -e "  ${YELLOW}⚠️  Save this password!${NC}"
    echo ""
fi

echo -e "${YELLOW}⚠️  IMPORTANT NEXT STEPS:${NC}"
echo ""
echo -e "1. ${CYAN}Edit configuration files:${NC}"
echo -e "   - $INSTALL_PATH/.env"
echo -e "   - $INSTALL_PATH/config.ini (add your API keys)"
echo ""
echo -e "2. ${CYAN}Start the services:${NC}"
echo -e "   sudo systemctl start mimic"
if [[ "$SKIP_REDIS" == false ]]; then
    echo -e "   sudo systemctl start mimic-worker"
fi
echo -e "   sudo systemctl start mimic-bot"
echo ""
echo -e "3. ${CYAN}Check service status:${NC}"
echo -e "   sudo systemctl status mimic"
echo ""
if [[ "$SKIP_NGINX" == false ]]; then
    echo -e "4. ${CYAN}Configure Nginx:${NC}"
    echo -e "   See: $INSTALL_PATH/LINUX_DEPLOYMENT.md"
    echo ""
fi
echo -e "5. ${CYAN}View logs:${NC}"
echo -e "   sudo journalctl -u mimic -f"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
