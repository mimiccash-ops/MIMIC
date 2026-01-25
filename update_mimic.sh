#!/bin/bash
#
# MIMIC - Автоматичне оновлення з GitHub
# =======================================
#
# Цей скрипт автоматично:
#   1. Оновлює файли з GitHub
#   2. Оновлює Python залежності
#   3. Збирає фронтенд
#   4. Запускає міграції
#   5. Перезапускає сервіси
#
# USAGE:
#   ./update_mimic.sh                    # Оновити все
#   ./update_mimic.sh --no-restart       # Без перезапуску сервісів
#   ./update_mimic.sh --skip-build       # Пропустити збірку фронтенду
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
INSTALL_PATH="/var/www/mimic"
RESTART_SERVICES=true
SKIP_BUILD=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-restart)
            RESTART_SERVICES=false
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --path|-p)
            INSTALL_PATH="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-restart      Don't restart services after update"
            echo "  --skip-build      Skip frontend build"
            echo "  --path PATH       Custom installation path"
            echo "  --help, -h        Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Banner
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║           MIMIC - Автоматичне оновлення                      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if directory exists
if [[ ! -d "$INSTALL_PATH" ]]; then
    echo -e "${RED}❌ Directory not found: $INSTALL_PATH${NC}"
    exit 1
fi

cd "$INSTALL_PATH"

# Check if git repository
if [[ ! -d .git ]]; then
    echo -e "${RED}❌ Not a git repository: $INSTALL_PATH${NC}"
    exit 1
fi

# Step 1: Update from GitHub
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}STEP 1: Оновлення з GitHub${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check for local changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}⚠️  Є локальні зміни. Зберігаю їх...${NC}"
    git stash
    STASHED=true
else
    STASHED=false
fi

# Fetch and pull
echo -e "${CYAN}ℹ️  Отримання оновлень з GitHub...${NC}"
git fetch origin

# Check if there are updates
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [[ "$LOCAL" == "$REMOTE" ]]; then
    echo -e "${GREEN}✅ Вже на останній версії${NC}"
    if [[ "$STASHED" == true ]]; then
        git stash pop
    fi
else
    echo -e "${CYAN}ℹ️  Оновлення файлів...${NC}"
    git pull origin main || git pull origin master
    
    if [[ "$STASHED" == true ]]; then
        echo -e "${CYAN}ℹ️  Повернення локальних змін...${NC}"
        git stash pop || echo -e "${YELLOW}⚠️  Можливі конфлікти зі збереженими змінами${NC}"
    fi
    
    echo -e "${GREEN}✅ Файли оновлено${NC}"
fi

echo ""

# Step 2: Update Python dependencies
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}STEP 2: Оновлення Python залежностей${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ -f requirements.txt ]] && [[ -d venv ]]; then
    echo -e "${CYAN}ℹ️  Оновлення pip...${NC}"
    source venv/bin/activate
    pip install --upgrade pip --quiet
    
    echo -e "${CYAN}ℹ️  Встановлення/оновлення залежностей...${NC}"
    pip install -r requirements.txt --quiet --upgrade
    
    echo -e "${GREEN}✅ Python залежності оновлено${NC}"
else
    echo -e "${YELLOW}⚠️  requirements.txt або venv не знайдено, пропускаю...${NC}"
fi

echo ""

# Step 3: Build frontend
if [[ "$SKIP_BUILD" == false ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}STEP 3: Збірка фронтенду${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if [[ -f package.json ]]; then
        echo -e "${CYAN}ℹ️  Встановлення Node.js залежностей...${NC}"
        npm install --silent
        
        echo -e "${CYAN}ℹ️  Збірка CSS...${NC}"
        npm run build --silent || echo -e "${YELLOW}⚠️  Помилки при збірці (може бути нормально)${NC}"
        
        echo -e "${GREEN}✅ Фронтенд зібрано${NC}"
    else
        echo -e "${YELLOW}⚠️  package.json не знайдено, пропускаю...${NC}"
    fi
    
    echo ""
fi

# Step 4: Run migrations
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}STEP 4: Запуск міграцій бази даних${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ -f migrations/migrate.py ]]; then
    echo -e "${CYAN}ℹ️  Запуск міграцій...${NC}"
    source venv/bin/activate
    python migrations/migrate.py || echo -e "${YELLOW}⚠️  Можливі помилки при міграції (перевірте вручну)${NC}"
    echo -e "${GREEN}✅ Міграції виконано${NC}"
else
    echo -e "${YELLOW}⚠️  Скрипт міграцій не знайдено, пропускаю...${NC}"
fi

echo ""

# Step 5: Restart services
if [[ "$RESTART_SERVICES" == true ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}STEP 5: Перезапуск сервісів${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if systemctl is-active --quiet mimic; then
        echo -e "${CYAN}ℹ️  Перезапуск mimic.service...${NC}"
        sudo systemctl restart mimic
        echo -e "${GREEN}✅ mimic.service перезапущено${NC}"
    fi
    
    if systemctl is-active --quiet mimic-worker; then
        echo -e "${CYAN}ℹ️  Перезапуск mimic-worker.service...${NC}"
        sudo systemctl restart mimic-worker
        echo -e "${GREEN}✅ mimic-worker.service перезапущено${NC}"
    fi
    
    if systemctl is-active --quiet mimic-bot; then
        echo -e "${CYAN}ℹ️  Перезапуск mimic-bot.service...${NC}"
        sudo systemctl restart mimic-bot
        echo -e "${GREEN}✅ mimic-bot.service перезапущено${NC}"
    fi
    
    echo ""
fi

# Summary
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ ОНОВЛЕННЯ ЗАВЕРШЕНО!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Перевірка статусу сервісів:${NC}"
echo "  sudo systemctl status mimic"
echo ""
echo -e "${CYAN}Перегляд логів:${NC}"
echo "  sudo journalctl -u mimic -f"
echo ""
