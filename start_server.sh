#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs/startup"
mkdir -p "$LOG_DIR"

fail() { echo "[ERROR] $1" >&2; exit 1; }
info() { echo "[INFO] $1"; }
warn() { echo "[WARN] $1"; }

if [ ! -f ".env" ]; then
  fail ".env not found. Copy production.env.example to .env and configure it."
fi

set -a
source ".env"
set +a

if [ ! -f "config.ini" ]; then
  fail "config.ini not found. Create it from config.ini.example and configure it."
fi

MODE="${START_MODE:-}"
if [ -z "$MODE" ]; then
  if [[ "${DATABASE_URL:-}" == *"@db:"* ]] || [[ "${REDIS_URL:-}" == *"redis://redis"* ]]; then
    MODE="docker"
  else
    MODE="local"
  fi
fi

info "Start mode: $MODE"
export PYTHONUNBUFFERED=1

require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "Missing dependency: $1"; }

get_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
  elif command -v python >/dev/null 2>&1; then
    echo "python"
  else
    return 1
  fi
}

ensure_python_version() {
  local py_cmd="$1"
  local major minor
  major="$($py_cmd -c "import sys; print(sys.version_info.major)")"
  minor="$($py_cmd -c "import sys; print(sys.version_info.minor)")"
  if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 10 ]); then
    fail "Python 3.10+ required (found $($py_cmd --version 2>&1))"
  fi
}

DOCKER_COMPOSE=""
get_docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
  else
    return 1
  fi
}

if [ -z "${FLASK_SECRET_KEY:-}" ]; then
  fail "FLASK_SECRET_KEY is missing in .env"
fi

if [ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]; then
  warn "GRAFANA_ADMIN_PASSWORD not set; docker-compose defaults to 'braincapital2024'."
fi

if [ "$MODE" = "docker" ]; then
  require_cmd docker
  get_docker_compose || fail "docker compose not available"
  require_cmd node
  require_cmd npm

  PYTHON_BIN="$(get_python)" || fail "Python 3.10+ not found"
  ensure_python_version "$PYTHON_BIN"

  if [ ! -d "node_modules" ]; then
    info "Installing frontend dependencies..."
    npm install
  fi

  info "Building frontend assets..."
  npm run build > "$LOG_DIR/frontend_build.log" 2>&1

  info "Starting database and redis via Docker..."
  $DOCKER_COMPOSE up -d db redis >> "$LOG_DIR/docker.log" 2>&1

  if [ -n "${DATABASE_URL:-}" ] && [[ "${DATABASE_URL}" == *"postgres"* ]]; then
    info "Waiting for PostgreSQL..."
    for _ in {1..30}; do
      if $DOCKER_COMPOSE exec -T db pg_isready -U brain_capital -d brain_capital >/dev/null 2>&1; then
        break
      fi
      sleep 2
    done
  fi

  info "Running database migrations..."
  $DOCKER_COMPOSE run --rm web python migrations/migrate.py >> "$LOG_DIR/migrations.log" 2>&1

  info "Starting backend and worker..."
  $DOCKER_COMPOSE up -d web worker >> "$LOG_DIR/docker.log" 2>&1

  info "All services started (Docker mode). Logs: $LOG_DIR"
  exit 0
fi

PYTHON_BIN="$(get_python)" || fail "Python 3.10+ not found"
ensure_python_version "$PYTHON_BIN"
require_cmd node
require_cmd npm

if [ ! -d "venv" ]; then
  info "Creating virtual environment..."
  "$PYTHON_BIN" -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate
PYTHON_BIN="python"

if ! $PYTHON_BIN -c "import flask" >/dev/null 2>&1; then
  info "Installing Python dependencies..."
  $PYTHON_BIN -m pip install --upgrade pip
  $PYTHON_BIN -m pip install -r requirements.txt
fi

if [ ! -d "node_modules" ]; then
  info "Installing frontend dependencies..."
  npm install
fi

info "Running database migrations..."
$PYTHON_BIN migrations/migrate.py > "$LOG_DIR/migrations.log" 2>&1

info "Checking Redis connectivity for worker..."
if ! $PYTHON_BIN -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379, db=0); r.ping()" >/dev/null 2>&1; then
  fail "Redis not reachable at 127.0.0.1:6379. Start Redis or use Docker mode."
fi

info "Starting frontend watcher..."
nohup npm run watch:css > "$LOG_DIR/frontend.log" 2>&1 &
echo $! > "$LOG_DIR/frontend.pid"

info "Starting backend..."
nohup $PYTHON_BIN app.py > "$LOG_DIR/backend.log" 2>&1 &
echo $! > "$LOG_DIR/backend.pid"

info "Starting worker..."
nohup $PYTHON_BIN worker.py > "$LOG_DIR/worker.log" 2>&1 &
echo $! > "$LOG_DIR/worker.pid"

if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] || [ -n "${TG_TOKEN:-}" ]; then
  info "Starting Telegram bot..."
  nohup $PYTHON_BIN run_bot.py > "$LOG_DIR/telegram_bot.log" 2>&1 &
  echo $! > "$LOG_DIR/telegram_bot.pid"
else
  warn "Telegram bot token not found in env; skipping bot."
fi

info "All services started (local mode). Logs: $LOG_DIR"
