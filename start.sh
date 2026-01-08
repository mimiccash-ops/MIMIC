#!/bin/bash
# =============================================================================
# ██████╗ ██████╗  █████╗ ██╗███╗   ██╗     ██████╗ █████╗ ██████╗ ██╗████████╗ █████╗ ██╗     
# ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║    ██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝██╔══██║██║     
# ██████╔╝██████╔╝███████║██║██╔██╗ ██║    ██║     ███████║██████╔╝██║   ██║   ███████║██║     
# ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║    ██║     ██╔══██║██╔═══╝ ██║   ██║   ██╔══██║██║     
# ██████╔╝██║  ██║██║  ██║██║██║ ╚████║    ╚██████╗██║  ██║██║     ██║   ██║   ██║  ██║███████╗
# ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝     ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝
# =============================================================================
#                    UNIFIED STARTUP SCRIPT v1.0
#                        https://mimic.cash
# =============================================================================
#
# This script handles everything:
#   1. Validates admin_settings.ini configuration
#   2. Generates .env and config.ini files
#   3. Checks Python and installs dependencies
#   4. Sets up database and runs migrations
#   5. Starts the application (Docker or Direct)
#
# Usage:
#   ./start.sh              - Interactive menu
#   ./start.sh docker       - Start with Docker
#   ./start.sh direct       - Start directly (no Docker)
#   ./start.sh dev          - Development mode
#   ./start.sh validate     - Only validate settings
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Change to script directory
cd "$(dirname "$0")"

# Parse arguments
MODE="${1:-menu}"

# =============================================================================
# FUNCTIONS
# =============================================================================

show_banner() {
    clear
    echo -e "${CYAN}"
    echo "  ╔═══════════════════════════════════════════════════════════════════╗"
    echo "  ║                                                                   ║"
    echo "  ║   ██████╗ ██████╗  █████╗ ██╗███╗   ██╗                          ║"
    echo "  ║   ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║                          ║"
    echo "  ║   ██████╔╝██████╔╝███████║██║██╔██╗ ██║                          ║"
    echo "  ║   ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║                          ║"
    echo "  ║   ██████╔╝██║  ██║██║  ██║██║██║ ╚████║                          ║"
    echo "  ║   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   CAPITAL               ║"
    echo "  ║                                                                   ║"
    echo "  ║                   Unified Startup Script v1.0                     ║"
    echo "  ║                      https://mimic.cash                           ║"
    echo "  ║                                                                   ║"
    echo "  ╚═══════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

show_help() {
    echo ""
    echo "  Brain Capital - Unified Startup Script"
    echo "  ======================================"
    echo ""
    echo "  Usage: ./start.sh [mode]"
    echo ""
    echo "  Modes:"
    echo "    (none)     Show interactive menu"
    echo "    docker     Start with Docker Compose (recommended)"
    echo "    direct     Start Python directly (production mode)"
    echo "    dev        Start in development mode (debug enabled)"
    echo "    validate   Only validate settings, don't start"
    echo "    worker     Start background worker only"
    echo "    help       Show this help message"
    echo ""
    echo "  Examples:"
    echo "    ./start.sh              # Interactive menu"
    echo "    ./start.sh docker       # Start Docker containers"
    echo "    ./start.sh direct       # Start production server"
    echo "    ./start.sh dev          # Start development server"
    echo ""
    exit 0
}

check_python() {
    echo -e "  ${BLUE}[1/6]${NC} Checking Python installation..."
    
    PYTHON_CMD=""
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        PYTHON_VER=$(python3 --version 2>&1 | cut -d' ' -f2)
        echo -e "        ${GREEN}✓${NC} Found Python $PYTHON_VER"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
        PYTHON_VER=$(python --version 2>&1 | cut -d' ' -f2)
        echo -e "        ${GREEN}✓${NC} Found Python $PYTHON_VER"
    else
        echo -e "        ${RED}✗${NC} Python not found!"
        echo ""
        echo "        Please install Python 3.10+:"
        echo "        - Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
        echo "        - macOS: brew install python"
        echo ""
        exit 1
    fi
    
    # Check version
    PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        echo -e "        ${RED}✗${NC} Python 3.10+ required (found $PYTHON_VER)"
        exit 1
    fi
}

check_config() {
    echo ""
    echo -e "  ${BLUE}[2/6]${NC} Checking configuration..."
    
    if [ ! -f "admin_settings.ini" ]; then
        echo -e "        ${RED}✗${NC} admin_settings.ini not found!"
        echo ""
        echo "        Please create admin_settings.ini and configure it."
        echo "        Then run this script again."
        echo ""
        exit 1
    fi
    
    echo -e "        ${GREEN}✓${NC} admin_settings.ini found"
    echo "        Validating settings..."
    echo ""
    
    $PYTHON_CMD validate_settings.py --generate
    
    if [ $? -ne 0 ]; then
        echo ""
        echo -e "  ${RED}╔═══════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${RED}║  ✗ CONFIGURATION ERROR                                            ║${NC}"
        echo -e "  ${RED}║                                                                   ║${NC}"
        echo -e "  ${RED}║  Please fix the errors in admin_settings.ini and try again.      ║${NC}"
        echo -e "  ${RED}╚═══════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        exit 1
    fi
}

install_dependencies() {
    echo ""
    echo -e "  ${BLUE}[3/6]${NC} Installing dependencies..."
    
    # Create venv if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "        Creating virtual environment..."
        $PYTHON_CMD -m venv venv
    fi
    
    # Activate venv
    source venv/bin/activate 2>/dev/null || true
    PYTHON_CMD="python"
    
    # Check if already installed
    if $PYTHON_CMD -c "import flask; import flask_socketio" &> /dev/null; then
        echo -e "        ${GREEN}✓${NC} Dependencies ready"
    else
        echo "        Installing packages from requirements.txt..."
        $PYTHON_CMD -m pip install --upgrade pip -q
        $PYTHON_CMD -m pip install -r requirements.txt -q
        echo -e "        ${GREEN}✓${NC} Dependencies installed"
    fi
}

setup_database() {
    echo ""
    echo -e "  ${BLUE}[4/6]${NC} Setting up database..."
    
    if [ -f "brain_capital.db" ]; then
        echo -e "        ${GREEN}✓${NC} SQLite database exists"
        echo "        Running migrations..."
        $PYTHON_CMD migrate_all.py > /dev/null 2>&1 || true
        echo -e "        ${GREEN}✓${NC} Migrations complete"
    else
        echo "        Creating new database..."
        $PYTHON_CMD -c "from app import app, db; app.app_context().push(); db.create_all()" 2>/dev/null
        echo -e "        ${GREEN}✓${NC} Database created"
    fi
}

show_menu() {
    echo ""
    echo -e "  ${BLUE}[5/6]${NC} Ready to start!"
    echo ""
    echo -e "  ${CYAN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${CYAN}║                     SELECT STARTUP MODE                           ║${NC}"
    echo -e "  ${CYAN}╠═══════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║   [1] Docker Mode (Recommended for Production)                    ║${NC}"
    echo -e "  ${CYAN}║       - Starts PostgreSQL, Redis, Web, Worker, Monitoring         ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║   [2] Direct Mode (Production without Docker)                     ║${NC}"
    echo -e "  ${CYAN}║       - Runs with Gunicorn, uses SQLite                           ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║   [3] Development Mode (Debug Enabled)                            ║${NC}"
    echo -e "  ${CYAN}║       - Flask debug mode with auto-reload                         ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║   [4] Start Worker Only                                           ║${NC}"
    echo -e "  ${CYAN}║       - Starts background task processor                          ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║   [5] Edit Admin Settings                                         ║${NC}"
    echo -e "  ${CYAN}║       - Open configuration file                                   ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║   [0] Exit                                                        ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    read -p "  Enter choice [1-5, 0 to exit]: " choice
    
    case $choice in
        1) start_docker ;;
        2) start_direct ;;
        3) start_dev ;;
        4) start_worker ;;
        5) ${EDITOR:-nano} admin_settings.ini; show_menu ;;
        0) exit 0 ;;
        *) echo "  Invalid choice."; show_menu ;;
    esac
}

start_docker() {
    echo ""
    echo -e "  ${BLUE}[6/6]${NC} Starting with Docker..."
    echo ""
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "        ${RED}✗${NC} Docker not found!"
        echo "        Please install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "        ${RED}✗${NC} Docker is not running!"
        echo "        Please start Docker and try again."
        exit 1
    fi
    
    echo -e "        ${GREEN}✓${NC} Docker is ready"
    echo ""
    echo -e "  ${CYAN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${CYAN}║                    STARTING DOCKER CONTAINERS                     ║${NC}"
    echo -e "  ${CYAN}╠═══════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Services starting:                                               ║${NC}"
    echo -e "  ${CYAN}║   • PostgreSQL Database                                           ║${NC}"
    echo -e "  ${CYAN}║   • Redis Cache/Queue                                             ║${NC}"
    echo -e "  ${CYAN}║   • Web Application (port 5000)                                   ║${NC}"
    echo -e "  ${CYAN}║   • Background Worker                                             ║${NC}"
    echo -e "  ${CYAN}║   • Prometheus Metrics (port 9090)                                ║${NC}"
    echo -e "  ${CYAN}║   • Grafana Dashboard (port 3000)                                 ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Press Ctrl+C to stop all containers                              ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    docker-compose down > /dev/null 2>&1 || true
    docker-compose up -d --build
    
    echo ""
    echo -e "  ${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${GREEN}║                       ✓ STARTUP COMPLETE!                         ║${NC}"
    echo -e "  ${GREEN}╠═══════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "  ${GREEN}║                                                                   ║${NC}"
    echo -e "  ${GREEN}║  Access URLs:                                                     ║${NC}"
    echo -e "  ${GREEN}║   • Web App:    http://localhost:5000                             ║${NC}"
    echo -e "  ${GREEN}║   • Grafana:    http://localhost:3000                             ║${NC}"
    echo -e "  ${GREEN}║   • Prometheus: http://localhost:9090                             ║${NC}"
    echo -e "  ${GREEN}║                                                                   ║${NC}"
    echo -e "  ${GREEN}║  Default Login: admin / admin                                     ║${NC}"
    echo -e "  ${GREEN}║  (Change the password immediately!)                               ║${NC}"
    echo -e "  ${GREEN}║                                                                   ║${NC}"
    echo -e "  ${GREEN}║  Commands:                                                        ║${NC}"
    echo -e "  ${GREEN}║   • View logs:    docker-compose logs -f                          ║${NC}"
    echo -e "  ${GREEN}║   • Stop:         docker-compose down                             ║${NC}"
    echo -e "  ${GREEN}║   • Restart:      docker-compose restart                          ║${NC}"
    echo -e "  ${GREEN}║                                                                   ║${NC}"
    echo -e "  ${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    read -p "  Press Enter to view logs, or Ctrl+C to exit..."
    docker-compose logs -f
}

start_direct() {
    echo ""
    echo -e "  ${BLUE}[6/6]${NC} Starting in Direct Mode (Production)..."
    echo ""
    
    # Load environment
    set -a
    source .env 2>/dev/null || true
    set +a
    export FLASK_ENV=production
    
    # Check/install gunicorn
    if ! $PYTHON_CMD -c "import gunicorn" &> /dev/null; then
        echo "        Installing gunicorn..."
        $PYTHON_CMD -m pip install gunicorn gevent gevent-websocket -q
    fi
    
    echo -e "  ${CYAN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${CYAN}║                    PRODUCTION SERVER STARTING                     ║${NC}"
    echo -e "  ${CYAN}╠═══════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Mode: Production (Gunicorn WSGI Server)                          ║${NC}"
    echo -e "  ${CYAN}║  Port: 5000                                                       ║${NC}"
    echo -e "  ${CYAN}║  URL:  http://localhost:5000                                      ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Default Login: admin / admin                                     ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Press Ctrl+C to stop                                             ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    gunicorn --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
             --workers 4 \
             --bind 0.0.0.0:5000 \
             --timeout 120 \
             --keep-alive 5 \
             --access-logfile - \
             --error-logfile - \
             "app:app"
}

start_dev() {
    echo ""
    echo -e "  ${BLUE}[6/6]${NC} Starting in Development Mode..."
    echo ""
    
    # Load environment
    set -a
    source .env 2>/dev/null || true
    set +a
    export FLASK_ENV=development
    
    echo -e "  ${CYAN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${CYAN}║                   DEVELOPMENT SERVER STARTING                     ║${NC}"
    echo -e "  ${CYAN}╠═══════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Mode: Development (Flask Debug Server)                           ║${NC}"
    echo -e "  ${CYAN}║  Port: 5000                                                       ║${NC}"
    echo -e "  ${CYAN}║  URL:  http://localhost:5000                                      ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Features:                                                        ║${NC}"
    echo -e "  ${CYAN}║   • Auto-reload on code changes                                   ║${NC}"
    echo -e "  ${CYAN}║   • Debug error pages                                             ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Press Ctrl+C to stop                                             ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    $PYTHON_CMD app.py
}

start_worker() {
    echo ""
    echo -e "  ${BLUE}[6/6]${NC} Starting Background Worker..."
    echo ""
    
    # Check Redis
    if ! $PYTHON_CMD -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379, db=0); r.ping()" &> /dev/null; then
        echo -e "        ${RED}✗${NC} Redis not accessible at 127.0.0.1:6379"
        echo "        Please start Redis first, or use Docker mode."
        exit 1
    fi
    
    echo -e "        ${GREEN}✓${NC} Redis connected"
    
    export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
    
    echo ""
    echo -e "  ${CYAN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${CYAN}║                     BACKGROUND WORKER STARTING                    ║${NC}"
    echo -e "  ${CYAN}╠═══════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}║  Processing background tasks (trade execution, notifications)     ║${NC}"
    echo -e "  ${CYAN}║  Press Ctrl+C to stop                                             ║${NC}"
    echo -e "  ${CYAN}║                                                                   ║${NC}"
    echo -e "  ${CYAN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    $PYTHON_CMD worker.py
}

# =============================================================================
# MAIN
# =============================================================================

# Handle help
if [ "$MODE" == "help" ] || [ "$MODE" == "-h" ] || [ "$MODE" == "--help" ]; then
    show_help
fi

# Show banner
show_banner

# Run checks
check_python
check_config

# Exit if validate only
if [ "$MODE" == "validate" ]; then
    echo ""
    echo "  Validation complete. Run ./start.sh again to start the application."
    exit 0
fi

install_dependencies
setup_database

# Start based on mode
case $MODE in
    docker) start_docker ;;
    direct) start_direct ;;
    dev) start_dev ;;
    worker) start_worker ;;
    menu|*) show_menu ;;
esac

echo ""
echo "  ════════════════════════════════════════════════════════════════════"
echo "                         APPLICATION STOPPED"
echo "  ════════════════════════════════════════════════════════════════════"

