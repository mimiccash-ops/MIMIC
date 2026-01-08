@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
TITLE Brain Capital - Unified Startup

REM =============================================================================
REM ██████╗ ██████╗  █████╗ ██╗███╗   ██╗     ██████╗ █████╗ ██████╗ ██╗████████╗ █████╗ ██╗     
REM ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║    ██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝██╔══██║██║     
REM ██████╔╝██████╔╝███████║██║██╔██╗ ██║    ██║     ███████║██████╔╝██║   ██║   ███████║██║     
REM ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║    ██║     ██╔══██║██╔═══╝ ██║   ██║   ██╔══██║██║     
REM ██████╔╝██║  ██║██║  ██║██║██║ ╚████║    ╚██████╗██║  ██║██║     ██║   ██║   ██║  ██║███████╗
REM ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝     ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝
REM =============================================================================
REM                    UNIFIED STARTUP SCRIPT v1.0
REM                        https://mimic.cash
REM =============================================================================
REM
REM This script handles everything:
REM   1. Validates admin_settings.ini configuration
REM   2. Generates .env and config.ini files
REM   3. Checks Python and installs dependencies
REM   4. Sets up database and runs migrations
REM   5. Starts the application (Docker or Direct)
REM
REM Usage:
REM   START.bat              - Interactive menu
REM   START.bat docker       - Start with Docker
REM   START.bat direct       - Start directly (no Docker)
REM   START.bat dev          - Development mode
REM   START.bat validate     - Only validate settings
REM =============================================================================

cd /d "%~dp0"

REM =============================================================================
REM PARSE ARGUMENTS
REM =============================================================================
set MODE=menu
if /i "%1"=="docker" set MODE=docker
if /i "%1"=="direct" set MODE=direct
if /i "%1"=="dev" set MODE=dev
if /i "%1"=="validate" set MODE=validate
if /i "%1"=="help" goto :show_help
if /i "%1"=="-h" goto :show_help
if /i "%1"=="--help" goto :show_help

REM =============================================================================
REM SHOW BANNER
REM =============================================================================
cls
echo.
echo  ╔═══════════════════════════════════════════════════════════════════╗
echo  ║                                                                   ║
echo  ║   ██████╗ ██████╗  █████╗ ██╗███╗   ██╗                          ║
echo  ║   ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║                          ║
echo  ║   ██████╔╝██████╔╝███████║██║██╔██╗ ██║                          ║
echo  ║   ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║                          ║
echo  ║   ██████╔╝██║  ██║██║  ██║██║██║ ╚████║                          ║
echo  ║   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   CAPITAL               ║
echo  ║                                                                   ║
echo  ║                   Unified Startup Script v1.0                     ║
echo  ║                      https://mimic.cash                           ║
echo  ║                                                                   ║
echo  ╚═══════════════════════════════════════════════════════════════════╝
echo.

REM =============================================================================
REM STEP 1: CHECK PYTHON
REM =============================================================================
echo  [1/6] Checking Python installation...

set PYTHON_CMD=

REM Try 'python' command
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
    echo        ✓ Found Python !PYTHON_VER!
    goto :python_found
)

REM Try 'py' launcher
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do set PYTHON_VER=%%v
    echo        ✓ Found Python !PYTHON_VER! via py launcher
    goto :python_found
)

echo        ✗ Python not found!
echo.
echo        Please install Python 3.10+ from:
echo        https://www.python.org/downloads/
echo.
echo        Make sure to check "Add Python to PATH"
echo.
pause
exit /b 1

:python_found

REM =============================================================================
REM STEP 2: CHECK/VALIDATE ADMIN SETTINGS
REM =============================================================================
echo.
echo  [2/6] Checking configuration...

REM Check if admin_settings.ini exists
if not exist "admin_settings.ini" (
    echo        ✗ admin_settings.ini not found
    echo        Creating from template...
    call :create_admin_settings
    echo        ✓ Created admin_settings.ini
    echo.
    echo  ╔═══════════════════════════════════════════════════════════════════╗
    echo  ║  ⚠ FIRST TIME SETUP REQUIRED                                      ║
    echo  ║                                                                   ║
    echo  ║  admin_settings.ini has been created.                             ║
    echo  ║  Please fill in your API keys and settings:                       ║
    echo  ║                                                                   ║
    echo  ║  Required:                                                        ║
    echo  ║   • [Security] flask_secret_key, master_encryption_key            ║
    echo  ║   • [Binance]  api_key, api_secret                                ║
    echo  ║   • [Database] password                                           ║
    echo  ║                                                                   ║
    echo  ║  Opening file now...                                              ║
    echo  ╚═══════════════════════════════════════════════════════════════════╝
    echo.
    start notepad admin_settings.ini
    pause
    exit /b 1
)

REM Check if file is actually a valid config (not corrupted/binary)
%PYTHON_CMD% -c "open('admin_settings.ini','rb').read(16).startswith(b'SQLite') and exit(1)" >nul 2>&1
if errorlevel 1 (
    echo        ✗ admin_settings.ini is corrupted (SQLite database detected^)
    echo        Backing up and creating new file...
    move admin_settings.ini admin_settings.ini.corrupted >nul 2>&1
    call :create_admin_settings
    echo        ✓ Fresh admin_settings.ini created
    echo.
    echo  ╔═══════════════════════════════════════════════════════════════════╗
    echo  ║  ⚠ CONFIGURATION FILE WAS CORRUPTED                               ║
    echo  ║                                                                   ║
    echo  ║  The old file was a SQLite database, not a config file.           ║
    echo  ║  A fresh admin_settings.ini has been created.                     ║
    echo  ║                                                                   ║
    echo  ║  Please fill in your settings.                                    ║
    echo  ╚═══════════════════════════════════════════════════════════════════╝
    echo.
    start notepad admin_settings.ini
    pause
    exit /b 1
)

echo        ✓ admin_settings.ini found

REM Check if .env exists (skip validation if first run)
if not exist ".env" (
    echo        Generating security keys...
    %PYTHON_CMD% setup_env.py >nul 2>&1
    if exist ".env" (
        echo        ✓ Security keys generated
    )
)

REM Check if validate_settings.py exists
if not exist "validate_settings.py" (
    echo        ⚠ validate_settings.py not found, skipping validation
    goto :skip_validation
)

echo        Validating settings...
echo.

REM Run validation script
%PYTHON_CMD% validate_settings.py --generate
if errorlevel 1 (
    echo.
    echo  ╔═══════════════════════════════════════════════════════════════════╗
    echo  ║  ✗ CONFIGURATION ERROR                                            ║
    echo  ║                                                                   ║
    echo  ║  Please fix the errors in admin_settings.ini and try again.      ║
    echo  ║  Open the file with: notepad admin_settings.ini                  ║
    echo  ╚═══════════════════════════════════════════════════════════════════╝
    echo.
    pause
    exit /b 1
)

:skip_validation

if "%MODE%"=="validate" (
    echo.
    echo  Validation complete. Run START.bat again to start the application.
    pause
    exit /b 0
)

REM =============================================================================
REM STEP 3: INSTALL DEPENDENCIES
REM =============================================================================
echo.
echo  [3/6] Installing dependencies...

REM Check if requirements already installed
%PYTHON_CMD% -c "import flask; import flask_socketio; import waitress" >nul 2>&1
if errorlevel 1 (
    echo        Installing packages from requirements.txt...
    %PYTHON_CMD% -m pip install --upgrade pip >nul 2>&1
    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo        ✗ Failed to install dependencies!
        pause
        exit /b 1
    )
)
echo        ✓ Dependencies ready

REM =============================================================================
REM STEP 4: DATABASE SETUP
REM =============================================================================
echo.
echo  [4/6] Setting up database...

if exist "brain_capital.db" (
    echo        ✓ SQLite database exists
    echo        Running migrations...
    %PYTHON_CMD% migrate_all.py >nul 2>&1
    echo        ✓ Migrations complete
) else (
    echo        Creating new database...
    %PYTHON_CMD% -c "from app import app, db; app.app_context().push(); db.create_all(); print('        ✓ Database created')"
)

REM =============================================================================
REM STEP 5: SHOW MENU OR START BASED ON MODE
REM =============================================================================
echo.
echo  [5/6] Ready to start!
echo.

if "%MODE%"=="docker" goto :start_docker
if "%MODE%"=="direct" goto :start_direct
if "%MODE%"=="dev" goto :start_dev

REM =============================================================================
REM INTERACTIVE MENU
REM =============================================================================
:show_menu
echo  ╔═══════════════════════════════════════════════════════════════════╗
echo  ║                     SELECT STARTUP MODE                           ║
echo  ╠═══════════════════════════════════════════════════════════════════╣
echo  ║                                                                   ║
echo  ║   [1] Docker Mode (Recommended for Production)                    ║
echo  ║       - Starts PostgreSQL, Redis, Web, Worker, Monitoring         ║
echo  ║       - Best for production deployment                            ║
echo  ║                                                                   ║
echo  ║   [2] Direct Mode (Local Development)                             ║
echo  ║       - Runs Python directly with SQLite                          ║
echo  ║       - Good for testing and development                          ║
echo  ║                                                                   ║
echo  ║   [3] Development Mode (Debug Enabled)                            ║
echo  ║       - Flask debug mode with auto-reload                         ║
echo  ║       - Best for active development                               ║
echo  ║                                                                   ║
echo  ║   [4] Start Worker Only                                           ║
echo  ║       - Starts background task processor                          ║
echo  ║                                                                   ║
echo  ║   [5] Open Admin Settings                                         ║
echo  ║       - Edit configuration file                                   ║
echo  ║                                                                   ║
echo  ║   [0] Exit                                                        ║
echo  ║                                                                   ║
echo  ╚═══════════════════════════════════════════════════════════════════╝
echo.
set /p choice="  Enter choice [1-5, 0 to exit]: "

if "%choice%"=="1" goto :start_docker
if "%choice%"=="2" goto :start_direct
if "%choice%"=="3" goto :start_dev
if "%choice%"=="4" goto :start_worker
if "%choice%"=="5" goto :open_settings
if "%choice%"=="0" exit /b 0

echo  Invalid choice. Please try again.
goto :show_menu

REM =============================================================================
REM DOCKER MODE
REM =============================================================================
:start_docker
echo.
echo  [6/6] Starting with Docker...
echo.

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo        ✗ Docker not found!
    echo        Please install Docker Desktop from:
    echo        https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo        ⚠ Docker is not running. Attempting to start...
    echo.
    
    set DOCKER_STARTED=0
    
    REM ===========================================
    REM METHOD 1: Try Windows Service (VPS/Server)
    REM ===========================================
    echo        Trying to start Docker service...
    
    REM Check if Docker service exists
    sc query docker >nul 2>&1
    if not errorlevel 1 (
        echo        Found Docker service. Starting...
        net start docker >nul 2>&1
        if not errorlevel 1 (
            set DOCKER_STARTED=1
            echo        ✓ Docker service start command sent
        ) else (
            REM Try with sc command
            sc start docker >nul 2>&1
            if not errorlevel 1 (
                set DOCKER_STARTED=1
                echo        ✓ Docker service start command sent
            )
        )
    )
    
    REM Also try com.docker.service (Docker Desktop service name)
    if "!DOCKER_STARTED!"=="0" (
        sc query com.docker.service >nul 2>&1
        if not errorlevel 1 (
            echo        Found Docker Desktop service. Starting...
            net start com.docker.service >nul 2>&1
            if not errorlevel 1 (
                set DOCKER_STARTED=1
                echo        ✓ Docker Desktop service start command sent
            )
        )
    )
    
    REM ===========================================
    REM METHOD 2: Try Docker Desktop (Desktop PC)
    REM ===========================================
    if "!DOCKER_STARTED!"=="0" (
        echo        Trying Docker Desktop application...
        
        if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
            echo        Starting from: Program Files\Docker\Docker
            start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
            set DOCKER_STARTED=1
        ) else if exist "%LOCALAPPDATA%\Docker\Docker Desktop.exe" (
            echo        Starting from: AppData\Local\Docker
            start "" "%LOCALAPPDATA%\Docker\Docker Desktop.exe"
            set DOCKER_STARTED=1
        ) else if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" (
            echo        Starting from: Program Files ^(x86^)\Docker\Docker
            start "" "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
            set DOCKER_STARTED=1
        )
    )
    
    if "!DOCKER_STARTED!"=="0" (
        echo.
        echo        ✗ Could not start Docker!
        echo.
        echo        For Windows Server/VPS:
        echo          1. Open PowerShell as Administrator
        echo          2. Run: Start-Service docker
        echo          3. Or install Docker: 
        echo             https://docs.docker.com/engine/install/
        echo.
        echo        For Windows Desktop:
        echo          Install Docker Desktop from:
        echo          https://www.docker.com/products/docker-desktop/
        echo.
        pause
        exit /b 1
    )
    
    echo.
    echo        Waiting for Docker to be ready...
    echo        ╔═══════════════════════════════════════════════════════════════╗
    echo        ║  Docker is starting. This may take 30-60 seconds...          ║
    echo        ╚═══════════════════════════════════════════════════════════════╝
    echo.
    
    REM Wait for Docker to be ready (max 120 seconds)
    set DOCKER_WAIT=0
    set DOCKER_MAX_WAIT=120
    
    :docker_wait_loop
    if !DOCKER_WAIT! geq !DOCKER_MAX_WAIT! (
        echo.
        echo        ✗ Docker failed to start within 2 minutes!
        echo.
        echo        Try manually:
        echo          1. Open PowerShell as Administrator
        echo          2. Run: Start-Service docker
        echo          3. Check status: docker info
        echo.
        pause
        exit /b 1
    )
    
    docker info >nul 2>&1
    if errorlevel 1 (
        REM Show progress every 10 seconds
        set /a MOD=!DOCKER_WAIT! %% 10
        if !MOD!==0 (
            if !DOCKER_WAIT! gtr 0 echo        ... waiting ^(!DOCKER_WAIT!s^)
        )
        timeout /t 5 /nobreak >nul
        set /a DOCKER_WAIT+=5
        goto :docker_wait_loop
    )
    
    echo.
    echo        ✓ Docker started successfully!
    echo.
)

echo        ✓ Docker is ready
echo.
echo  ╔═══════════════════════════════════════════════════════════════════╗
echo  ║                    STARTING DOCKER CONTAINERS                     ║
echo  ╠═══════════════════════════════════════════════════════════════════╣
echo  ║                                                                   ║
echo  ║  Services starting:                                               ║
echo  ║   • PostgreSQL Database                                           ║
echo  ║   • Redis Cache/Queue                                             ║
echo  ║   • Web Application (port 5000)                                   ║
echo  ║   • Background Worker                                             ║
echo  ║   • Prometheus Metrics (port 9090)                                ║
echo  ║   • Grafana Dashboard (port 3000)                                 ║
echo  ║                                                                   ║
echo  ║  Press Ctrl+C to stop all containers                              ║
echo  ║                                                                   ║
echo  ╚═══════════════════════════════════════════════════════════════════╝
echo.

REM Stop any existing containers
docker-compose down >nul 2>&1

REM Start containers
docker-compose up -d --build

if errorlevel 1 (
    echo        ✗ Failed to start Docker containers!
    pause
    exit /b 1
)

echo.
echo  ╔═══════════════════════════════════════════════════════════════════╗
echo  ║                       ✓ STARTUP COMPLETE!                         ║
echo  ╠═══════════════════════════════════════════════════════════════════╣
echo  ║                                                                   ║
echo  ║  Access URLs:                                                     ║
echo  ║   • Web App:    http://localhost:5000                             ║
echo  ║   • Grafana:    http://localhost:3000                             ║
echo  ║   • Prometheus: http://localhost:9090                             ║
echo  ║                                                                   ║
echo  ║  Default Login: admin / admin                                     ║
echo  ║  (Change the password immediately!)                               ║
echo  ║                                                                   ║
echo  ║  Commands:                                                        ║
echo  ║   • View logs:    docker-compose logs -f                          ║
echo  ║   • Stop:         docker-compose down                             ║
echo  ║   • Restart:      docker-compose restart                          ║
echo  ║                                                                   ║
echo  ╚═══════════════════════════════════════════════════════════════════╝
echo.

echo  Press any key to view logs, or Ctrl+C to exit...
pause >nul
docker-compose logs -f
goto :end

REM =============================================================================
REM DIRECT MODE (Production)
REM =============================================================================
:start_direct
echo.
echo  [6/6] Starting in Direct Mode (Production)...
echo.

REM Set production environment
set FLASK_ENV=production

REM Load .env variables
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if not "%%a"=="" set "%%a=%%b"
    )
)

echo  ╔═══════════════════════════════════════════════════════════════════╗
echo  ║                    PRODUCTION SERVER STARTING                     ║
echo  ╠═══════════════════════════════════════════════════════════════════╣
echo  ║                                                                   ║
echo  ║  Mode: Production (Waitress WSGI Server)                          ║
echo  ║  Port: 5000                                                       ║
echo  ║  URL:  http://localhost:5000                                      ║
echo  ║                                                                   ║
echo  ║  Default Login: admin / admin                                     ║
echo  ║  (Change the password immediately!)                               ║
echo  ║                                                                   ║
echo  ║  Press Ctrl+C to stop                                             ║
echo  ║                                                                   ║
echo  ╚═══════════════════════════════════════════════════════════════════╝
echo.

REM Check/install waitress
%PYTHON_CMD% -c "import waitress" >nul 2>&1
if errorlevel 1 (
    echo  Installing waitress server...
    %PYTHON_CMD% -m pip install waitress >nul 2>&1
)

REM Start with waitress
%PYTHON_CMD% -c "from waitress import serve; from app import app; print('  Server running on http://0.0.0.0:5000'); serve(app, host='0.0.0.0', port=5000, threads=8)"
goto :end

REM =============================================================================
REM DEVELOPMENT MODE
REM =============================================================================
:start_dev
echo.
echo  [6/6] Starting in Development Mode...
echo.

set FLASK_ENV=development

REM Load .env variables
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if not "%%a"=="" set "%%a=%%b"
    )
)

echo  ╔═══════════════════════════════════════════════════════════════════╗
echo  ║                   DEVELOPMENT SERVER STARTING                     ║
echo  ╠═══════════════════════════════════════════════════════════════════╣
echo  ║                                                                   ║
echo  ║  Mode: Development (Flask Debug Server)                           ║
echo  ║  Port: 5000                                                       ║
echo  ║  URL:  http://localhost:5000                                      ║
echo  ║                                                                   ║
echo  ║  Features:                                                        ║
echo  ║   • Auto-reload on code changes                                   ║
echo  ║   • Debug error pages                                             ║
echo  ║   • Interactive debugger                                          ║
echo  ║                                                                   ║
echo  ║  Default Login: admin / admin                                     ║
echo  ║                                                                   ║
echo  ║  Press Ctrl+C to stop                                             ║
echo  ║                                                                   ║
echo  ╚═══════════════════════════════════════════════════════════════════╝
echo.

%PYTHON_CMD% app.py
goto :end

REM =============================================================================
REM START WORKER ONLY
REM =============================================================================
:start_worker
echo.
echo  Starting Background Worker...
echo.

REM Check Redis
%PYTHON_CMD% -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379, db=0); r.ping()" >nul 2>&1
if errorlevel 1 (
    echo        ✗ Redis not accessible at 127.0.0.1:6379
    echo        Please start Redis first, or use Docker mode.
    echo.
    pause
    goto :show_menu
)

echo        ✓ Redis connected
echo.
echo  ╔═══════════════════════════════════════════════════════════════════╗
echo  ║                     BACKGROUND WORKER STARTING                    ║
echo  ╠═══════════════════════════════════════════════════════════════════╣
echo  ║                                                                   ║
echo  ║  Processing background tasks (trade execution, notifications)     ║
echo  ║  Press Ctrl+C to stop                                             ║
echo  ║                                                                   ║
echo  ╚═══════════════════════════════════════════════════════════════════╝
echo.

if not defined REDIS_URL set REDIS_URL=redis://127.0.0.1:6379/0
%PYTHON_CMD% worker.py
goto :end

REM =============================================================================
REM OPEN SETTINGS
REM =============================================================================
:open_settings
start notepad admin_settings.ini
goto :show_menu

REM =============================================================================
REM SHOW HELP
REM =============================================================================
:show_help
echo.
echo  Brain Capital - Unified Startup Script
echo  ======================================
echo.
echo  Usage: START.bat [mode]
echo.
echo  Modes:
echo    (none)     Show interactive menu
echo    docker     Start with Docker Compose (recommended)
echo    direct     Start Python directly (production mode)
echo    dev        Start in development mode (debug enabled)
echo    validate   Only validate settings, don't start
echo    help       Show this help message
echo.
echo  Examples:
echo    START.bat              # Interactive menu
echo    START.bat docker       # Start Docker containers
echo    START.bat direct       # Start production server
echo    START.bat dev          # Start development server
echo.
pause
exit /b 0

REM =============================================================================
REM END
REM =============================================================================
:end
echo.
echo  ════════════════════════════════════════════════════════════════════
echo                         APPLICATION STOPPED
echo  ════════════════════════════════════════════════════════════════════
pause
goto :eof

REM =============================================================================
REM CREATE ADMIN SETTINGS (embedded template)
REM =============================================================================
:create_admin_settings
(
echo # =============================================================================
echo #                    BRAIN CAPITAL - ADMIN SETTINGS
echo # =============================================================================
echo # Fill in your settings below. Lines starting with # are comments.
echo # After editing, run START.bat again.
echo # =============================================================================
echo.
echo [Security]
echo # Flask secret key ^(REQUIRED^) - Generate: python -c "import secrets; print^(secrets.token_hex^(32^)^)"
echo flask_secret_key = 
echo.
echo # Master encryption key ^(REQUIRED^) - Generate: python -c "from cryptography.fernet import Fernet; print^(Fernet.generate_key^(^).decode^(^)^)"
echo master_encryption_key = 
echo.
echo # Webhook passphrase ^(REQUIRED^) - Generate: python -c "import secrets; print^(secrets.token_urlsafe^(32^)^)"
echo webhook_passphrase = 
echo.
echo [Binance]
echo # Your Binance Futures API credentials
echo api_key = 
echo api_secret = 
echo use_testnet = False
echo max_open_positions = 10
echo.
echo [Database]
echo host = db
echo port = 5432
echo name = brain_capital
echo username = brain_capital
echo # Database password ^(REQUIRED^)
echo password = 
echo.
echo [Telegram]
echo # Telegram bot settings ^(optional but recommended^)
echo bot_token = 
echo chat_id = 
echo enabled = False
echo panic_otp_secret = 
echo panic_authorized_users = 
echo.
echo [Payments]
echo enabled = False
echo plisio_api_key = 
echo plisio_webhook_secret = 
echo.
echo [Email]
echo enabled = False
echo smtp_server = smtp.gmail.com
echo smtp_port = 587
echo email_address = 
echo email_password = 
echo from_name = Brain Capital
echo.
echo [Domain]
echo production_url = 
echo https_enabled = False
echo.
echo [Redis]
echo host = redis
echo port = 6379
echo database = 0
echo.
echo [Proxy]
echo enabled = False
echo proxies = 
echo.
echo [Monitoring]
echo enabled = True
echo grafana_user = admin
echo grafana_password = braincapital2024
) > admin_settings.ini
goto :eof

