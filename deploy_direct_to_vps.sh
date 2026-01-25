#!/bin/bash
#
# Deploy MIMIC Directly to VPS (Without GitHub)
# ===============================================
#
# This script copies files directly from your local machine to the VPS
# using rsync. No GitHub needed!
#
# USAGE:
#   ./deploy_direct_to_vps.sh                    # Use default settings
#   ./deploy_direct_to_vps.sh root@1.2.3.4      # Specify VPS
#   ./deploy_direct_to_vps.sh --path /opt/mimic  # Custom path
#

set -e

# Configuration
VPS_USER="root"
VPS_HOST=""
VPS_PORT="22"
REMOTE_PATH="/var/www/mimic"
SSH_KEY=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
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
        --key|-k)
            SSH_KEY="$2"
            shift 2
            ;;
        --port)
            VPS_PORT="$2"
            shift 2
            ;;
        --help|-h)
            echo ""
            echo "Deploy MIMIC Directly to VPS"
            echo ""
            echo "Usage: $0 [OPTIONS] [VPS_HOST]"
            echo ""
            echo "Options:"
            echo "  --server, -s USER@HOST    VPS server (e.g., root@1.2.3.4)"
            echo "  --path, -p PATH           Remote path (default: /var/www/mimic)"
            echo "  --key, -k PATH            SSH key path"
            echo "  --port PORT              SSH port (default: 22)"
            echo "  --help, -h                Show this help"
            echo ""
            echo "Examples:"
            echo "  $0 root@1.2.3.4"
            echo "  $0 --server root@1.2.3.4 --path /opt/mimic"
            echo ""
            exit 0
            ;;
        *)
            if [[ -z "$VPS_HOST" ]]; then
                if [[ "$1" == *"@"* ]]; then
                    VPS_USER="${1%%@*}"
                    VPS_HOST="${1#*@}"
                else
                    VPS_HOST="$1"
                fi
            fi
            shift
            ;;
    esac
done

# Banner
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        MIMIC - Direct VPS Deployment (No GitHub)           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Validate VPS host
if [[ -z "$VPS_HOST" ]]; then
    echo -e "${RED}❌ VPS host not specified!${NC}"
    echo ""
    echo "Usage: $0 root@YOUR_VPS_IP"
    echo "   or: $0 --server root@YOUR_VPS_IP"
    echo ""
    exit 1
fi

# Check for rsync
if ! command -v rsync &> /dev/null; then
    echo -e "${RED}❌ rsync is not installed!${NC}"
    echo "Install it with: sudo apt install rsync  (Linux)"
    echo "                or: brew install rsync    (macOS)"
    exit 1
fi

SSH_TARGET="$VPS_USER@$VPS_HOST"

# Build SSH options
SSH_OPTS="-o StrictHostKeyChecking=no -o BatchMode=yes -p $VPS_PORT"
if [[ -n "$SSH_KEY" ]]; then
    SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
fi

echo -e "${CYAN}ℹ️  Target: ${SSH_TARGET}:${REMOTE_PATH}${NC}"
echo ""

# Test SSH connection
echo -e "${CYAN}ℹ️  Testing SSH connection...${NC}"
if ! ssh $SSH_OPTS "$SSH_TARGET" "echo 'Connection successful'" &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to VPS!${NC}"
    echo ""
    echo "Please check:"
    echo "  - VPS IP address is correct"
    echo "  - SSH is enabled on VPS"
    echo "  - SSH key is configured (or password authentication is enabled)"
    echo "  - Firewall allows SSH (port $VPS_PORT)"
    exit 1
fi
echo -e "${GREEN}✅ SSH connection successful${NC}"
echo ""

# Create remote directory
echo -e "${CYAN}ℹ️  Creating remote directory...${NC}"
ssh $SSH_OPTS "$SSH_TARGET" "mkdir -p $REMOTE_PATH && chown -R $VPS_USER:$VPS_USER $REMOTE_PATH" || true

# Files/directories to exclude
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
    "instance/"
)

# Build exclude arguments
EXCLUDE_ARGS=""
for pattern in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=$pattern"
done

# Get script directory (source of files)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}ℹ️  Syncing files to VPS...${NC}"
echo ""

# Execute rsync
rsync -avz --progress --delete $EXCLUDE_ARGS \
    -e "ssh $SSH_OPTS" \
    "$SCRIPT_DIR/" "$SSH_TARGET:$REMOTE_PATH/"

RSYNC_EXIT=$?

if [[ $RSYNC_EXIT -ne 0 ]]; then
    echo ""
    echo -e "${RED}❌ rsync failed with exit code $RSYNC_EXIT${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Files synchronized to VPS${NC}"
echo ""

# Run installation script on VPS
echo -e "${CYAN}ℹ️  Running installation script on VPS...${NC}"
echo ""

ssh $SSH_OPTS "$SSH_TARGET" << EOF
    cd $REMOTE_PATH
    if [[ -f install_vps.sh ]]; then
        chmod +x install_vps.sh
        echo "Installation script is ready. Run manually with:"
        echo "  sudo ./install_vps.sh"
        echo ""
        echo "Or run it now? (This will install all dependencies)"
    else
        echo "⚠️  install_vps.sh not found. Files copied but installation needed."
    fi
EOF

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  DEPLOYMENT COMPLETE${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Files copied to: ${SSH_TARGET}:${REMOTE_PATH}"
echo ""
echo -e "${YELLOW}Next steps on VPS:${NC}"
echo "  1. SSH to VPS: ssh $SSH_TARGET"
echo "  2. Navigate: cd $REMOTE_PATH"
echo "  3. Run: sudo chmod +x install_vps.sh"
echo "  4. Run: sudo ./install_vps.sh"
echo ""
echo "Or run installation automatically now? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo -e "${CYAN}ℹ️  Running installation script...${NC}"
    ssh $SSH_OPTS "$SSH_TARGET" "cd $REMOTE_PATH && sudo ./install_vps.sh" || {
        echo -e "${YELLOW}⚠️  Installation script needs to be run manually${NC}"
    }
fi

echo ""
