#!/bin/bash
# =============================================================================
# MIMIC - All-in-One VPS Control Script
# =============================================================================
# Run the entire MIMIC platform with a single command
#
# Usage:
#   ./mimic-control.sh start     - Start all services
#   ./mimic-control.sh stop      - Stop all services
#   ./mimic-control.sh restart   - Restart all services
#   ./mimic-control.sh status    - Show status of all services
#   ./mimic-control.sh logs      - View live logs
#   ./mimic-control.sh install   - First-time installation
#   ./mimic-control.sh update    - Pull latest code and restart
#
# =============================================================================

set -e

# =============================================================================
# CONFIGURATION - Edit these if your paths differ
# =============================================================================
APP_DIR="/var/www/mimic"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="$APP_DIR/logs"
SECRETS_DIR="$APP_DIR/secrets"
USER="mimic"
GROUP="mimic"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║   ███╗   ███╗ ██╗ ███╗   ███╗ ██╗  ██████╗                  ║"
    echo "║   ████╗ ████║ ██║ ████╗ ████║ ██║ ██╔════╝                  ║"
    echo "║   ██╔████╔██║ ██║ ██╔████╔██║ ██║ ██║                       ║"
    echo "║   ██║╚██╔╝██║ ██║ ██║╚██╔╝██║ ██║ ██║                       ║"
    echo "║   ██║ ╚═╝ ██║ ██║ ██║ ╚═╝ ██║ ██║  ██████╗                  ║"
    echo "║   ╚═╝     ╚═╝ ╚═╝ ╚═╝     ╚═╝ ╚═╝  ╚═════╝                  ║"
    echo "║                                                              ║"
    echo "║           Brain Capital Trading Platform                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# =============================================================================
# SERVICE FUNCTIONS
# =============================================================================

check_service() {
    local service=$1
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

start_postgresql() {
    log_info "Starting PostgreSQL..."
    if check_service postgresql; then
        log_success "PostgreSQL is already running"
    else
        systemctl start postgresql
        sleep 2
        if check_service postgresql; then
            log_success "PostgreSQL started"
        else
            log_error "Failed to start PostgreSQL"
            return 1
        fi
    fi
}

start_redis() {
    log_info "Starting Redis..."
    if check_service redis-server; then
        log_success "Redis is already running"
    elif check_service redis; then
        log_success "Redis is already running"
    else
        # Try redis-server first (Ubuntu/Debian), then redis (CentOS/RHEL)
        if systemctl start redis-server 2>/dev/null || systemctl start redis 2>/dev/null; then
            sleep 1
            log_success "Redis started"
        else
            log_warning "Redis not installed or failed to start (optional service)"
        fi
    fi
}

start_nginx() {
    log_info "Starting Nginx..."
    if check_service nginx; then
        log_success "Nginx is already running"
    else
        systemctl start nginx
        sleep 1
        if check_service nginx; then
            log_success "Nginx started"
        else
            log_error "Failed to start Nginx"
            return 1
        fi
    fi
}

start_mimic() {
    log_info "Starting MIMIC main application..."
    
    # Check if service file exists
    if [[ ! -f /etc/systemd/system/mimic.service ]]; then
        log_info "Installing MIMIC systemd service..."
        install_systemd_service
    fi
    
    if check_service mimic; then
        log_success "MIMIC is already running"
    else
        systemctl start mimic
        sleep 3
        if check_service mimic; then
            log_success "MIMIC started"
        else
            log_error "Failed to start MIMIC"
            journalctl -u mimic -n 20 --no-pager
            return 1
        fi
    fi
}

start_worker() {
    log_info "Starting MIMIC background worker..."
    
    # Check if worker service file exists
    if [[ ! -f /etc/systemd/system/mimic-worker.service ]]; then
        log_info "Installing MIMIC worker systemd service..."
        install_worker_service
    fi
    
    if check_service mimic-worker; then
        log_success "MIMIC worker is already running"
    else
        systemctl start mimic-worker
        sleep 2
        if check_service mimic-worker; then
            log_success "MIMIC worker started"
        else
            log_warning "Failed to start MIMIC worker (optional service)"
        fi
    fi
}

stop_all() {
    log_info "Stopping all MIMIC services..."
    
    systemctl stop mimic-worker 2>/dev/null && log_success "MIMIC worker stopped" || true
    systemctl stop mimic 2>/dev/null && log_success "MIMIC stopped" || true
    
    # Don't stop nginx, postgresql, redis as they might be used by other apps
    log_info "Note: Nginx, PostgreSQL, and Redis left running (shared services)"
}

# =============================================================================
# INSTALLATION FUNCTIONS
# =============================================================================

install_systemd_service() {
    cat > /etc/systemd/system/mimic.service << 'EOF'
[Unit]
Description=MIMIC Brain Capital Trading Platform
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
User=mimic
Group=mimic
WorkingDirectory=/var/www/mimic
Environment="PATH=/var/www/mimic/venv/bin"
Environment="PYTHONUNBUFFERED=1"
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
EOF
    systemctl daemon-reload
    systemctl enable mimic
}

install_worker_service() {
    cat > /etc/systemd/system/mimic-worker.service << 'EOF'
[Unit]
Description=MIMIC ARQ Background Worker
After=network.target redis.service mimic.service
Wants=redis.service

[Service]
User=mimic
Group=mimic
WorkingDirectory=/var/www/mimic
Environment="PATH=/var/www/mimic/venv/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/var/www/mimic/.env
ExecStart=/var/www/mimic/venv/bin/python worker.py
Restart=always
RestartSec=5
StandardOutput=append:/var/www/mimic/logs/worker.log
StandardError=append:/var/www/mimic/logs/worker-error.log

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable mimic-worker
}

install_nginx_config() {
    # Get domain from .env or use default
    DOMAIN=$(grep -E "^PRODUCTION_DOMAIN=" "$APP_DIR/.env" 2>/dev/null | cut -d'=' -f2 | sed 's|https://||' | sed 's|http://||' || echo "localhost")
    
    cat > /etc/nginx/sites-available/mimic << EOF
# MIMIC Rate limiting
limit_req_zone \$binary_remote_addr zone=mimic_limit:10m rate=10r/s;

# Upstream application
upstream mimic_app {
    server 127.0.0.1:5000;
    keepalive 32;
}

server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    # SSL (update paths after running certbot)
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    limit_req zone=mimic_limit burst=20 nodelay;
    client_max_body_size 16M;

    # Static files
    location /static/ {
        alias /var/www/mimic/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
        access_log off;
    }

    # WebSocket
    location /socket.io/ {
        proxy_pass http://mimic_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
        proxy_buffering off;
    }

    # Main app
    location / {
        proxy_pass http://mimic_app;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF
    
    ln -sf /etc/nginx/sites-available/mimic /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
}

full_install() {
    print_banner
    log_info "Starting full MIMIC installation..."
    echo ""
    
    check_root
    
    # Check if project exists
    if [[ ! -d "$APP_DIR" ]]; then
        log_error "Project directory $APP_DIR not found!"
        log_info "Please clone your repository first:"
        echo ""
        echo "    sudo mkdir -p $APP_DIR"
        echo "    sudo git clone https://github.com/YOUR_USERNAME/MIMIC.git $APP_DIR"
        echo ""
        exit 1
    fi
    
    cd "$APP_DIR"
    
    # Create user if not exists
    if ! id -u "$USER" >/dev/null 2>&1; then
        log_info "Creating $USER user..."
        useradd -m -s /bin/bash "$USER"
        log_success "User $USER created"
    fi
    
    # Create directories
    log_info "Creating directories..."
    mkdir -p "$LOG_DIR"
    mkdir -p "$SECRETS_DIR"
    chmod 700 "$SECRETS_DIR"
    
    # Check for .env file
    if [[ ! -f "$APP_DIR/.env" ]]; then
        if [[ -f "$APP_DIR/production.env.example" ]]; then
            log_info "Creating .env from template..."
            cp "$APP_DIR/production.env.example" "$APP_DIR/.env"
            log_warning "Please edit $APP_DIR/.env with your settings!"
        else
            log_error ".env file not found! Please create it."
            exit 1
        fi
    fi
    
    # Check for config.ini
    if [[ ! -f "$APP_DIR/config.ini" ]]; then
        if [[ -f "$APP_DIR/config.ini.example" ]]; then
            log_info "Creating config.ini from template..."
            cp "$APP_DIR/config.ini.example" "$APP_DIR/config.ini"
            log_warning "Please edit $APP_DIR/config.ini with your settings!"
        fi
    fi
    
    # Generate master key if not exists
    if [[ ! -f "$SECRETS_DIR/master.key" ]]; then
        log_info "Generating encryption master key..."
        source "$VENV_DIR/bin/activate" 2>/dev/null || true
        python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > "$SECRETS_DIR/master.key"
        chmod 600 "$SECRETS_DIR/master.key"
        log_success "Master key generated"
    fi
    
    # Create virtual environment if not exists
    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
        log_success "Virtual environment created"
    fi
    
    # Install Python dependencies
    log_info "Installing Python dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip -q
    pip install -r "$APP_DIR/requirements.txt" -q
    pip install gunicorn eventlet -q
    log_success "Dependencies installed"
    
    # Set permissions
    log_info "Setting permissions..."
    chown -R "$USER:$GROUP" "$APP_DIR"
    chmod 600 "$APP_DIR/.env"
    chmod 600 "$APP_DIR/config.ini" 2>/dev/null || true
    chmod 755 "$LOG_DIR"
    log_success "Permissions set"
    
    # Install systemd services
    log_info "Installing systemd services..."
    install_systemd_service
    install_worker_service
    log_success "Systemd services installed"
    
    # Install nginx config
    if command -v nginx >/dev/null 2>&1; then
        log_info "Installing Nginx configuration..."
        install_nginx_config
        log_success "Nginx config installed"
        log_warning "Run 'sudo certbot --nginx -d yourdomain.com' to get SSL certificate"
    fi
    
    # Run migrations
    log_info "Running database migrations..."
    cd "$APP_DIR"
    source "$VENV_DIR/bin/activate"
    python migrate_all.py 2>/dev/null || log_warning "Migration script not found or failed"
    
    echo ""
    log_success "Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Edit $APP_DIR/.env with your settings"
    echo "  2. Edit $APP_DIR/config.ini with Binance API keys"
    echo "  3. Run: sudo ./mimic-control.sh start"
    echo ""
}

# =============================================================================
# STATUS & LOGS
# =============================================================================

show_status() {
    print_banner
    echo ""
    echo "Service Status:"
    echo "═══════════════════════════════════════════════════════════════"
    
    # PostgreSQL
    printf "  PostgreSQL:     "
    if check_service postgresql; then
        echo -e "${GREEN}● Running${NC}"
    else
        echo -e "${RED}○ Stopped${NC}"
    fi
    
    # Redis
    printf "  Redis:          "
    if check_service redis-server || check_service redis; then
        echo -e "${GREEN}● Running${NC}"
    else
        echo -e "${YELLOW}○ Not running (optional)${NC}"
    fi
    
    # Nginx
    printf "  Nginx:          "
    if check_service nginx; then
        echo -e "${GREEN}● Running${NC}"
    else
        echo -e "${RED}○ Stopped${NC}"
    fi
    
    # MIMIC
    printf "  MIMIC App:      "
    if check_service mimic; then
        echo -e "${GREEN}● Running${NC}"
    else
        echo -e "${RED}○ Stopped${NC}"
    fi
    
    # MIMIC Worker
    printf "  MIMIC Worker:   "
    if check_service mimic-worker; then
        echo -e "${GREEN}● Running${NC}"
    else
        echo -e "${YELLOW}○ Not running (optional)${NC}"
    fi
    
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    # Check if app is responding
    if check_service mimic; then
        printf "  Health Check:   "
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/health 2>/dev/null | grep -q "200"; then
            echo -e "${GREEN}● Healthy${NC}"
        else
            echo -e "${YELLOW}○ Not responding yet (starting up?)${NC}"
        fi
    fi
    
    echo ""
}

show_logs() {
    echo "Showing live logs (Ctrl+C to exit)..."
    echo ""
    journalctl -u mimic -u mimic-worker -f --no-pager
}

# =============================================================================
# UPDATE FUNCTION
# =============================================================================

update_code() {
    print_banner
    log_info "Updating MIMIC from git..."
    
    cd "$APP_DIR"
    
    # Pull latest code
    log_info "Pulling latest code..."
    sudo -u "$USER" git pull
    
    # Install any new dependencies
    log_info "Updating dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install -r requirements.txt -q
    
    # Run migrations
    log_info "Running migrations..."
    python migrate_all.py 2>/dev/null || true
    
    # Restart services
    log_info "Restarting services..."
    systemctl restart mimic
    systemctl restart mimic-worker 2>/dev/null || true
    
    sleep 3
    log_success "Update complete!"
    show_status
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

case "${1:-}" in
    start)
        check_root
        print_banner
        log_info "Starting all MIMIC services..."
        echo ""
        start_postgresql
        start_redis
        start_nginx
        start_mimic
        start_worker
        echo ""
        log_success "All services started!"
        echo ""
        show_status
        ;;
    
    stop)
        check_root
        print_banner
        stop_all
        echo ""
        log_success "MIMIC services stopped"
        ;;
    
    restart)
        check_root
        print_banner
        log_info "Restarting MIMIC services..."
        stop_all
        sleep 2
        start_postgresql
        start_redis
        start_nginx
        start_mimic
        start_worker
        echo ""
        log_success "All services restarted!"
        show_status
        ;;
    
    status)
        show_status
        ;;
    
    logs)
        show_logs
        ;;
    
    install)
        full_install
        ;;
    
    update)
        check_root
        update_code
        ;;
    
    *)
        print_banner
        echo "Usage: $0 {start|stop|restart|status|logs|install|update}"
        echo ""
        echo "Commands:"
        echo "  start    - Start all services (PostgreSQL, Redis, Nginx, MIMIC)"
        echo "  stop     - Stop MIMIC services"
        echo "  restart  - Restart all services"
        echo "  status   - Show status of all services"
        echo "  logs     - View live logs (Ctrl+C to exit)"
        echo "  install  - First-time installation setup"
        echo "  update   - Pull latest code from git and restart"
        echo ""
        exit 1
        ;;
esac

exit 0
