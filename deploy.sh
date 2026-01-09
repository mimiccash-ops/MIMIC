#!/bin/bash
#
# MIMIC - One-Command VPS Deployment Script
# ==========================================
#
# USAGE:
#   ./deploy.sh                    # Deploy using config settings
#   ./deploy.sh --restart          # Deploy and restart service
#   ./deploy.sh --dry-run          # Preview changes without deploying
#   ./deploy.sh --help             # Show help
#
# FIRST TIME SETUP:
#   1. Edit the CONFIGURATION section below
#   2. Set VPS_HOST to your VPS IP address
#   3. Ensure SSH key authentication is configured
#   4. chmod +x deploy.sh && ./deploy.sh
#

set -e

# ============================================================================
# CONFIGURATION - Edit these values for your VPS
# ============================================================================

VPS_USER="root"                      # SSH username
VPS_HOST="YOUR_VPS_IP"               # VPS IP or hostname (e.g., 38.180.143.20)
VPS_PORT="22"                        # SSH port (default: 22)
REMOTE_PATH="/var/www/mimic"         # Where to deploy on VPS
SSH_KEY=""                           # Path to SSH key (leave empty for default)
SERVICE_NAME="mimic"                 # systemd service name

# Files/directories to exclude from sync
EXCLUDES=(
    ".git"
    ".gitignore"
    ".env"
    "*.db"
    "__pycache__"
    "*.pyc"
    ".pytest_cache"
    "venv"
    ".venv"
    "node_modules"
    "*.log"
    "logs/"
    "secrets/"
    ".idea"
    ".vscode"
    "*.tmp"
    "*.bak"
    "deploy.ps1"
    "DEPLOY.bat"
    "deploy.sh"
    "static/avatars/*"
)

# ============================================================================
# SCRIPT LOGIC - No need to edit below
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
RESTART=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --restart|-r)
            RESTART=true
            shift
            ;;
        --server|-s)
            if [[ "$2" == *"@"* ]]; then
                VPS_USER="${2%%@*}"
                VPS_HOST="${2#*@}"
            else
                VPS_HOST="$2"
            fi
            shift 2
            ;;
        --path|-p)
            REMOTE_PATH="$2"
            shift 2
            ;;
        --help|-h)
            echo ""
            echo "MIMIC VPS Deployment Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run, -n     Show what would be transferred without making changes"
            echo "  --restart, -r     Restart service after deployment"
            echo "  --server, -s      Override server (user@host)"
            echo "  --path, -p        Override remote path"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Deploy with default settings"
            echo "  $0 --restart                 # Deploy and restart service"
            echo "  $0 --server root@1.2.3.4    # Deploy to specific server"
            echo "  $0 --dry-run                 # Preview without deploying"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Banner
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║           MIMIC - VPS Deployment Script                      ║${NC}"
echo -e "${CYAN}║                  https://mimic.cash                          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Validate configuration
if [[ "$VPS_HOST" == "YOUR_VPS_IP" ]] || [[ -z "$VPS_HOST" ]]; then
    echo -e "${RED}❌ VPS_HOST not configured!${NC}"
    echo ""
    echo -e "${YELLOW}Please edit deploy.sh and set your VPS details:${NC}"
    echo '    VPS_HOST="your-vps-ip-address"'
    echo ""
    exit 1
fi

# Check for rsync
if ! command -v rsync &> /dev/null; then
    echo -e "${RED}❌ rsync is not installed!${NC}"
    echo "Install it with: sudo apt install rsync"
    exit 1
fi

# Build SSH options
SSH_OPTS="-o StrictHostKeyChecking=no -o BatchMode=yes -p $VPS_PORT"
if [[ -n "$SSH_KEY" ]]; then
    SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
fi

SSH_TARGET="$VPS_USER@$VPS_HOST"

echo -e "${CYAN}ℹ️  Target: ${SSH_TARGET}:${REMOTE_PATH}${NC}"
echo ""

# Build exclude arguments
EXCLUDE_ARGS=""
for pattern in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=$pattern"
done

# Build rsync command
RSYNC_OPTS="-avz --progress --delete"
if $DRY_RUN; then
    RSYNC_OPTS="$RSYNC_OPTS --dry-run"
fi

# Get script directory (source of files)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}ℹ️  Syncing files...${NC}"
echo ""

# Execute rsync
rsync $RSYNC_OPTS $EXCLUDE_ARGS \
    -e "ssh $SSH_OPTS" \
    "$SCRIPT_DIR/" "$SSH_TARGET:$REMOTE_PATH/"

RSYNC_EXIT=$?

if [[ $RSYNC_EXIT -ne 0 ]]; then
    echo ""
    echo -e "${RED}❌ rsync failed with exit code $RSYNC_EXIT${NC}"
    exit 1
fi

if $DRY_RUN; then
    echo ""
    echo -e "${YELLOW}⚠️  [DRY RUN] No files were transferred${NC}"
else
    echo ""
    echo -e "${GREEN}✅ Files synchronized${NC}"
fi

# Restart service if requested
if $RESTART && ! $DRY_RUN; then
    echo ""
    echo -e "${CYAN}ℹ️  Restarting service: $SERVICE_NAME...${NC}"
    
    ssh $SSH_OPTS "$SSH_TARGET" "sudo systemctl restart $SERVICE_NAME && sudo systemctl status $SERVICE_NAME --no-pager"
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ Service restarted${NC}"
    else
        echo -e "${YELLOW}⚠️  Service restart may have issues, check logs${NC}"
    fi
fi

# Summary
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
if $DRY_RUN; then
    echo -e "${YELLOW}  DRY RUN COMPLETE - No changes made${NC}"
else
    echo -e "${GREEN}  DEPLOYMENT COMPLETE${NC}"
fi
echo -e "  Target: ${SSH_TARGET}:${REMOTE_PATH}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
