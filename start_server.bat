@echo off
setlocal enabledelayedexpansion

set ROOT_DIR=%~dp0
pushd "%ROOT_DIR%"

set LOG_DIR=%ROOT_DIR%logs\startup
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist ".env" (
  echo [ERROR] .env not found. Copy production.env.example to .env and configure it.
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
  echo %%a | findstr /r "^#" >nul
  if errorlevel 1 (
    if not "%%a"=="" (
      set "%%a=%%b"
    )
  )
)

if not exist "config.ini" (
  echo [ERROR] config.ini not found. Create it from config.ini.example and configure it.
  exit /b 1
)

set MODE=%START_MODE%
if "%MODE%"=="" (
  echo "%DATABASE_URL%" | findstr /I "@db:" >nul
  if not errorlevel 1 set MODE=docker
)
if "%MODE%"=="" set MODE=local

echo [INFO] Start mode: %MODE%

if "%FLASK_SECRET_KEY%"=="" (
  echo [ERROR] FLASK_SECRET_KEY is missing in .env
  exit /b 1
)

if "%GRAFANA_ADMIN_PASSWORD%"=="" (
  echo [WARN] GRAFANA_ADMIN_PASSWORD not set; docker-compose defaults to 'braincapital2024'.
)

if /I "%MODE%"=="docker" (
  call :require_cmd node
  if errorlevel 1 exit /b 1
  call :require_cmd npm
  if errorlevel 1 exit /b 1
  call :require_cmd docker
  if errorlevel 1 exit /b 1
  call :set_docker_compose
  if errorlevel 1 exit /b 1
  call :require_cmd python
  if errorlevel 1 exit /b 1

  if not exist "node_modules" (
    echo [INFO] Installing frontend dependencies...
    npm install
  )

  echo [INFO] Building frontend assets...
  npm run build > "%LOG_DIR%\frontend_build.log" 2>&1

  echo [INFO] Starting database and redis via Docker...
  %DOCKER_COMPOSE_CMD% up -d db redis >> "%LOG_DIR%\docker.log" 2>&1

  echo "%DATABASE_URL%" | findstr /I "postgres" >nul
  if not errorlevel 1 (
    echo [INFO] Waiting for PostgreSQL...
    for /l %%i in (1,1,30) do (
      %DOCKER_COMPOSE_CMD% exec -T db pg_isready -U brain_capital -d brain_capital >nul 2>&1
      if not errorlevel 1 goto pgready
      timeout /t 2 >nul
    )
    :pgready
  )

  echo [INFO] Running database migrations...
  %DOCKER_COMPOSE_CMD% run --rm web python migrations/migrate.py >> "%LOG_DIR%\migrations.log" 2>&1
  if errorlevel 1 (
    echo [ERROR] Migrations failed. See "%LOG_DIR%\migrations.log"
    exit /b 1
  )

  echo [INFO] Starting backend and worker...
  %DOCKER_COMPOSE_CMD% up -d web worker >> "%LOG_DIR%\docker.log" 2>&1

  echo [INFO] All services started (Docker mode). Logs: %LOG_DIR%
  popd
  exit /b 0
)

call :require_cmd node
if errorlevel 1 exit /b 1
call :require_cmd npm
if errorlevel 1 exit /b 1
call :require_cmd python
if errorlevel 1 exit /b 1

if not exist "venv\Scripts\python.exe" (
  echo [INFO] Creating virtual environment...
  python -m venv venv
)

set PYTHON_BIN=%ROOT_DIR%venv\Scripts\python.exe

"%PYTHON_BIN%" -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Installing Python dependencies...
  "%PYTHON_BIN%" -m pip install --upgrade pip
  "%PYTHON_BIN%" -m pip install -r requirements.txt
)

if not exist "node_modules" (
  echo [INFO] Installing frontend dependencies...
  npm install
)

echo [INFO] Running database migrations...
"%PYTHON_BIN%" migrations\migrate.py > "%LOG_DIR%\migrations.log" 2>&1
if errorlevel 1 (
  echo [ERROR] Migrations failed. See "%LOG_DIR%\migrations.log"
  exit /b 1
)

echo [INFO] Checking Redis connectivity for worker...
"%PYTHON_BIN%" -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379, db=0); r.ping()" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Redis not reachable at 127.0.0.1:6379. Start Redis or use Docker mode.
  exit /b 1
)

echo [INFO] Starting frontend watcher...
start "MIMIC Frontend" cmd /c "npm run watch:css >> \"%LOG_DIR%\frontend.log\" 2>&1"

echo [INFO] Starting backend...
start "MIMIC Backend" cmd /c "\"%PYTHON_BIN%\" app.py >> \"%LOG_DIR%\backend.log\" 2>&1"

echo [INFO] Starting worker...
start "MIMIC Worker" cmd /c "\"%PYTHON_BIN%\" worker.py >> \"%LOG_DIR%\worker.log\" 2>&1"

if not "%TELEGRAM_BOT_TOKEN%"=="" (
  echo [INFO] Starting Telegram bot...
  start "MIMIC Bot" cmd /c "\"%PYTHON_BIN%\" run_bot.py >> \"%LOG_DIR%\telegram_bot.log\" 2>&1"
) else if not "%TG_TOKEN%"=="" (
  echo [INFO] Starting Telegram bot...
  start "MIMIC Bot" cmd /c "\"%PYTHON_BIN%\" run_bot.py >> \"%LOG_DIR%\telegram_bot.log\" 2>&1"
) else (
  echo [WARN] Telegram bot token not found in env; skipping bot.
)

echo [INFO] All services started (local mode). Logs: %LOG_DIR%
popd
exit /b 0

:require_cmd
where %1 >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Missing dependency: %1
  exit /b 1
)
exit /b 0

:set_docker_compose
docker compose version >nul 2>&1
if not errorlevel 1 (
  set DOCKER_COMPOSE_CMD=docker compose
  exit /b 0
)
where docker-compose >nul 2>&1
if not errorlevel 1 (
  set DOCKER_COMPOSE_CMD=docker-compose
  exit /b 0
)
echo [ERROR] docker compose not found
exit /b 1
