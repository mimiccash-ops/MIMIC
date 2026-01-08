#!/bin/bash
# =============================================================================
# MIMIC (BRAIN CAPITAL) - COMPLETE SETUP AND STARTUP SCRIPT (Linux/Mac)
# =============================================================================
# This script performs a complete setup and starts the application:
#   1. Checks Python installation
#   2. Creates virtual environment (optional)
#   3. Installs/upgrades dependencies
#   4. Generates security keys (.env file)
#   5. Copies config.ini if missing
#   6. Runs database migrations
#   7. Starts the application
# =============================================================================
# Usage: ./setup_and_start.sh [--production]
#        Add --production flag for production mode (requires root for port 80)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to script directory
cd "$(dirname "$0")"

echo ""
echo "============================================================"
echo "  MIMIC (Brain Capital) - Setup and Startup"
echo "  https://mimic.cash"
echo "============================================================"
echo ""

# Check for production flag
PRODUCTION_MODE=false
if [ "$1" == "--production" ] || [ "$1" == "-p" ]; then
    PRODUCTION_MODE=true
fi

# =============================================================================
# STEP 1: Check Python Installation
# =============================================================================
echo -e "${BLUE}[1/7] Checking Python installation...${NC}"

PYTHON_CMD=""

# Try python3 first (preferred on Linux/Mac)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VER=$(python3 --version 2>&1 | cut -d' ' -f2)
    echo -e "      ${GREEN}[OK]${NC} Found Python $PYTHON_VER"
# Try python
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PYTHON_VER=$(python --version 2>&1 | cut -d' ' -f2)
    echo -e "      ${GREEN}[OK]${NC} Found Python $PYTHON_VER"
else
    echo -e "      ${RED}[ERROR]${NC} Python is not installed!"
    echo ""
    echo "      Please install Python 3.10 or higher:"
    echo "      - Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "      - macOS: brew install python"
    echo ""
    exit 1
fi

# Check Python version is 3.10+
PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo -e "      ${RED}[ERROR]${NC} Python 3.10 or higher is required!"
    echo "      Current version: $PYTHON_VER"
    exit 1
fi

# =============================================================================
# STEP 2: Create Virtual Environment (Optional)
# =============================================================================
echo ""
echo -e "${BLUE}[2/7] Checking virtual environment...${NC}"

if [ -d "venv" ]; then
    echo -e "      ${GREEN}[OK]${NC} Virtual environment exists"
    source venv/bin/activate 2>/dev/null || true
    echo -e "      ${GREEN}[OK]${NC} Activated virtual environment"
else
    echo "      Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    echo -e "      ${GREEN}[OK]${NC} Created and activated virtual environment"
fi

# Update PYTHON_CMD to use venv python
PYTHON_CMD="python"

# =============================================================================
# STEP 3: Install/Upgrade Dependencies
# =============================================================================
echo ""
echo -e "${BLUE}[3/7] Installing dependencies...${NC}"

# Upgrade pip
$PYTHON_CMD -m pip install --upgrade pip -q

# Install requirements
$PYTHON_CMD -m pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo -e "      ${RED}[ERROR]${NC} Failed to install dependencies!"
    exit 1
fi
echo -e "      ${GREEN}[OK]${NC} Dependencies installed"

# =============================================================================
# STEP 4: Generate Security Keys (.env file)
# =============================================================================
echo ""
echo -e "${BLUE}[4/7] Setting up security keys...${NC}"

if [ -f ".env" ]; then
    echo -e "      ${GREEN}[OK]${NC} .env file already exists"
else
    echo "      Generating new security keys..."
    $PYTHON_CMD setup_env.py
    if [ $? -ne 0 ]; then
        echo -e "      ${RED}[ERROR]${NC} Failed to generate security keys!"
        exit 1
    fi
    echo -e "      ${GREEN}[OK]${NC} Security keys generated"
fi

# =============================================================================
# STEP 5: Copy config.ini if missing
# =============================================================================
echo ""
echo -e "${BLUE}[5/7] Checking configuration file...${NC}"

if [ -f "config.ini" ]; then
    echo -e "      ${GREEN}[OK]${NC} config.ini already exists"
else
    if [ -f "config.ini.example" ]; then
        cp config.ini.example config.ini
        echo -e "      ${GREEN}[OK]${NC} Created config.ini from example"
        echo ""
        echo -e "      ${YELLOW}================================================${NC}"
        echo -e "      ${YELLOW}IMPORTANT: Edit config.ini with your API keys!${NC}"
        echo -e "      ${YELLOW}================================================${NC}"
        echo ""
    else
        echo -e "      ${YELLOW}[WARNING]${NC} config.ini.example not found!"
    fi
fi

# =============================================================================
# STEP 6: Run Database Migrations
# =============================================================================
echo ""
echo -e "${BLUE}[6/7] Running database migrations...${NC}"

if [ -f "brain_capital.db" ]; then
    echo "      Database found, checking for migrations..."
    $PYTHON_CMD migrate_all.py || echo -e "      ${YELLOW}[WARNING]${NC} Migration had issues, but continuing..."
    echo -e "      ${GREEN}[OK]${NC} Database migrations complete"
else
    echo -e "      ${GREEN}[OK]${NC} No existing database - will be created on first run"
fi

# =============================================================================
# STEP 7: Start the Application
# =============================================================================
echo ""
echo -e "${BLUE}[7/7] Starting application...${NC}"
echo ""
echo "============================================================"
echo -e "  ${GREEN}SETUP COMPLETE!${NC} Starting MIMIC..."
echo "============================================================"
echo ""
echo "  Access the application at:"
echo "  - Local:   http://localhost:5000"
echo "  - Network: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'YOUR_IP'):5000"
echo ""
echo "  Default login: admin / admin"
echo "  (Change the password immediately!)"
echo ""
echo "  Press Ctrl+C to stop the server"
echo "============================================================"
echo ""

if [ "$PRODUCTION_MODE" = true ]; then
    echo -e "${GREEN}[INFO]${NC} Running in PRODUCTION mode"
    export FLASK_ENV=production
    
    # Check if running as root (needed for port 80)
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}[WARNING]${NC} Not running as root - using port 5000 instead of 80"
        $PYTHON_CMD run_server.py
    else
        echo -e "${GREEN}[INFO]${NC} Running on port 80"
        $PYTHON_CMD run_server.py
    fi
else
    echo -e "${GREEN}[INFO]${NC} Running in DEVELOPMENT mode"
    echo "      Use --production flag for production mode"
    echo ""
    $PYTHON_CMD app.py
fi

echo ""
echo "============================================================"
echo "  APPLICATION STOPPED"
echo "============================================================"

