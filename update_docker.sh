#!/bin/bash
#
# MIMIC - Docker Update Script
# ==============================
#
# This script safely updates MIMIC running in Docker containers
# WITHOUT deleting database volumes
#
# USAGE:
#   ./update_docker.sh                    # Full update
#   ./update_docker.sh --no-rebuild       # Skip image rebuild
#   ./update_docker.sh --no-migrate       # Skip migrations
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REBUILD=true
RUN_MIGRATIONS=true
PROJECT_DIR="${1:-/root/mimic}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-rebuild)
            REBUILD=false
            shift
            ;;
        --no-migrate)
            RUN_MIGRATIONS=false
            shift
            ;;
        --dir|-d)
            PROJECT_DIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [PROJECT_DIR]"
            echo ""
            echo "Options:"
            echo "  --no-rebuild    Skip Docker image rebuild"
            echo "  --no-migrate    Skip database migrations"
            echo "  --dir DIR       Project directory (default: /root/mimic)"
            echo "  --help, -h      Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                          # Full update"
            echo "  $0 --no-rebuild             # Update without rebuild"
            echo "  $0 /opt/mimic               # Update from custom directory"
            exit 0
            ;;
        *)
            if [[ -z "$PROJECT_DIR" ]] || [[ "$PROJECT_DIR" == "/root/mimic" ]]; then
                PROJECT_DIR="$1"
            fi
            shift
            ;;
    esac
done

# Banner
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        MIMIC - Docker Update Script                         ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if directory exists
if [[ ! -d "$PROJECT_DIR" ]]; then
    echo -e "${RED}❌ Directory not found: $PROJECT_DIR${NC}"
    exit 1
fi

cd "$PROJECT_DIR"

# Check if git repository
if [[ ! -d .git ]]; then
    echo -e "${RED}❌ Not a git repository: $PROJECT_DIR${NC}"
    exit 1
fi

# Check if docker-compose.yml exists
if [[ ! -f docker-compose.yml ]]; then
    echo -e "${RED}❌ docker-compose.yml not found${NC}"
    exit 1
fi

# Step 1: Update code from GitHub
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}STEP 1: Updating code from GitHub${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check for local changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}⚠️  Local changes detected. Stashing...${NC}"
    git stash
    STASHED=true
else
    STASHED=false
fi

# Fetch and pull
echo -e "${CYAN}ℹ️  Fetching updates from GitHub...${NC}"
git fetch origin

# Check if there are updates
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [[ "$LOCAL" == "$REMOTE" ]]; then
    echo -e "${GREEN}✅ Already up to date${NC}"
    if [[ "$STASHED" == true ]]; then
        git stash pop
    fi
    echo ""
    echo -e "${CYAN}ℹ️  No updates available. Exiting.${NC}"
    exit 0
else
    echo -e "${CYAN}ℹ️  Pulling changes...${NC}"
    git pull origin main || git pull origin master
    
    if [[ "$STASHED" == true ]]; then
        echo -e "${CYAN}ℹ️  Restoring local changes...${NC}"
        git stash pop || echo -e "${YELLOW}⚠️  Possible conflicts with stashed changes${NC}"
    fi
    
    echo -e "${GREEN}✅ Code updated${NC}"
fi

echo ""

# Step 2: Pull Docker images (if not rebuilding)
if [[ "$REBUILD" == false ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}STEP 2: Pulling Docker images${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    echo -e "${CYAN}ℹ️  Pulling latest images...${NC}"
    docker compose pull || echo -e "${YELLOW}⚠️  Some images may not be available${NC}"
    echo -e "${GREEN}✅ Images pulled${NC}"
    echo ""
fi

# Step 3: Stop containers (SAFELY - without removing volumes)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}STEP 3: Stopping containers${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}ℹ️  Stopping containers (preserving volumes)...${NC}"
docker compose down

echo -e "${GREEN}✅ Containers stopped${NC}"
echo ""

# Step 4: Rebuild images (if needed)
if [[ "$REBUILD" == true ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}STEP 4: Rebuilding Docker images${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    echo -e "${CYAN}ℹ️  Building images (this may take a few minutes)...${NC}"
    docker compose build --no-cache
    
    echo -e "${GREEN}✅ Images rebuilt${NC}"
    echo ""
fi

# Step 5: Start containers
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}STEP 5: Starting containers${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}ℹ️  Starting containers...${NC}"
docker compose up -d

echo -e "${GREEN}✅ Containers started${NC}"
echo ""

# Step 6: Run migrations (if needed)
if [[ "$RUN_MIGRATIONS" == true ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}STEP 6: Running database migrations${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    echo -e "${CYAN}ℹ️  Waiting for database to be ready...${NC}"
    sleep 5
    
    echo -e "${CYAN}ℹ️  Running migrations...${NC}"
    docker compose run --rm web python migrations/migrate.py || echo -e "${YELLOW}⚠️  Migrations may have warnings${NC}"
    
    echo -e "${GREEN}✅ Migrations completed${NC}"
    echo ""
fi

# Step 7: Check status
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}STEP 7: Checking container status${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}ℹ️  Container status:${NC}"
docker compose ps

echo ""

# Summary
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ UPDATE COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo "  docker compose ps              # View container status"
echo "  docker compose logs -f web     # View web logs"
echo "  docker compose logs -f worker  # View worker logs"
echo "  docker compose restart web     # Restart web container"
echo ""
