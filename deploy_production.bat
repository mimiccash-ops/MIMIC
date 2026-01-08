@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║        BRAIN CAPITAL - PRODUCTION DEPLOYMENT                 ║
echo ║               https://mimic.cash                             ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM ==================== CHECK PYTHON ====================
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

REM ==================== GENERATE KEYS IF NEEDED ====================
echo [1/5] Checking security keys...

REM Check if .env exists, if not create from template
if not exist ".env" (
    echo [INFO] Creating .env file...
    
    REM Generate FLASK_SECRET_KEY
    for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "GENERATED_SECRET=%%i"
    
    REM Generate BRAIN_CAPITAL_MASTER_KEY
    for /f "delims=" %%i in ('python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"') do set "GENERATED_FERNET=%%i"
    
    (
        echo # BRAIN CAPITAL - PRODUCTION ENVIRONMENT
        echo # Generated on %date% %time%
        echo.
        echo # Flask environment - PRODUCTION MODE
        echo FLASK_ENV=production
        echo.
        echo # Secret key for sessions ^(auto-generated^)
        echo FLASK_SECRET_KEY=!GENERATED_SECRET!
        echo.
        echo # Master encryption key ^(auto-generated^)
        echo BRAIN_CAPITAL_MASTER_KEY=!GENERATED_FERNET!
        echo.
        echo # Production domain
        echo PRODUCTION_DOMAIN=https://mimic.cash,https://www.mimic.cash
        echo.
        echo # Database ^(leave empty for SQLite^)
        echo DATABASE_URL=
        echo.
        echo # Redis ^(optional^)
        echo REDIS_URL=
    ) > .env
    
    echo [OK] .env file created with auto-generated keys
) else (
    echo [OK] .env file exists
)

REM ==================== LOAD ENVIRONMENT ====================
echo [2/5] Loading environment variables...

for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if not "%%a"=="" (
            set "%%a=%%b"
        )
    )
)

REM Force production mode
set FLASK_ENV=production
set PRODUCTION_DOMAIN=https://mimic.cash,https://www.mimic.cash

echo [OK] FLASK_ENV=%FLASK_ENV%
echo [OK] PRODUCTION_DOMAIN=%PRODUCTION_DOMAIN%

REM ==================== INSTALL DEPENDENCIES ====================
echo [3/5] Checking dependencies...

python -c "import waitress" 2>nul
if errorlevel 1 (
    echo [INFO] Installing waitress ^(production server^)...
    pip install waitress >nul 2>&1
)

python -c "import flask_socketio" 2>nul
if errorlevel 1 (
    echo [INFO] Installing required packages...
    pip install -r requirements.txt >nul 2>&1
)

echo [OK] Dependencies ready

REM ==================== DATABASE SETUP ====================
echo [4/5] Checking database...

if not exist "brain_capital.db" (
    echo [INFO] Initializing database...
    python -c "from app import app, db; app.app_context().push(); db.create_all(); print('[OK] Database created')"
) else (
    echo [OK] Database exists
)

REM ==================== START SERVER ====================
echo [5/5] Starting production server...
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  Server starting on port 80                                  ║
echo ║  Access: http://localhost or https://mimic.cash              ║
echo ║  Press Ctrl+C to stop                                        ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM Export environment variables for the Python process
set FLASK_ENV=production
set PRODUCTION_DOMAIN=https://mimic.cash,https://www.mimic.cash

REM Start with waitress (production WSGI server)
python -c "import os; os.environ['FLASK_ENV']='production'; os.environ['PRODUCTION_DOMAIN']='https://mimic.cash,https://www.mimic.cash'; from waitress import serve; from app import app; print('[OK] Production server running on http://0.0.0.0:80'); serve(app, host='0.0.0.0', port=80, threads=8, url_scheme='https')"

pause

