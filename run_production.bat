@echo off
REM =============================================================================
REM BRAIN CAPITAL - PRODUCTION STARTUP SCRIPT (Windows)
REM =============================================================================
REM This script starts the application in production mode
REM Make sure to configure your .env file before running!
REM =============================================================================

echo ============================================
echo   BRAIN CAPITAL - Production Deployment
echo ============================================
echo.

REM Check if .env file exists
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please copy production.env.example to .env and configure it.
    echo.
    echo   copy production.env.example .env
    echo.
    pause
    exit /b 1
)

REM Load environment variables from .env file
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    REM Skip comments and empty lines
    echo %%a | findstr /r "^#" >nul
    if errorlevel 1 (
        if not "%%a"=="" (
            set "%%a=%%b"
        )
    )
)

REM Verify required environment variables
if "%FLASK_ENV%"=="" (
    echo [ERROR] FLASK_ENV is not set in .env file
    pause
    exit /b 1
)

if not "%FLASK_ENV%"=="production" (
    echo [WARNING] FLASK_ENV is set to '%FLASK_ENV%', not 'production'
    echo For production deployment, set FLASK_ENV=production in .env
    echo.
)

if "%FLASK_SECRET_KEY%"=="" (
    echo [ERROR] FLASK_SECRET_KEY is not set in .env file
    pause
    exit /b 1
)

if "%BRAIN_CAPITAL_MASTER_KEY%"=="" (
    echo [ERROR] BRAIN_CAPITAL_MASTER_KEY is not set in .env file
    pause
    exit /b 1
)

if "%PRODUCTION_DOMAIN%"=="" (
    echo [WARNING] PRODUCTION_DOMAIN is not set. CORS may not work correctly.
    echo.
)

echo [INFO] Environment: %FLASK_ENV%
echo [INFO] Domain: %PRODUCTION_DOMAIN%
echo.

REM Check if waitress is installed (production WSGI server for Windows)
python -c "import waitress" 2>nul
if errorlevel 1 (
    echo [INFO] Installing waitress (production WSGI server)...
    pip install waitress
)

echo [INFO] Starting Brain Capital in PRODUCTION mode...
echo [INFO] Press Ctrl+C to stop the server
echo.

REM Start with waitress (production-ready WSGI server)
python -c "from waitress import serve; from app import app, socketio; print('[OK] Starting on port 5000...'); serve(app, host='0.0.0.0', port=5000, threads=8)"

pause

