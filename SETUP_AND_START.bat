@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
REM =============================================================================
REM MIMIC (BRAIN CAPITAL) - COMPLETE SETUP AND STARTUP SCRIPT
REM =============================================================================
REM This script performs a complete setup and starts the application:
REM   1. Checks Python installation
REM   2. Installs/upgrades dependencies
REM   3. Generates security keys (.env file)
REM   4. Copies config.ini if missing
REM   5. Runs database migrations
REM   6. Starts the application
REM =============================================================================
REM Usage: Double-click this file or run from command prompt
REM        For production: Run as Administrator
REM =============================================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   MIMIC (Brain Capital) - Setup and Startup
echo   https://mimic.cash
echo ============================================================
echo.

REM =============================================================================
REM STEP 1: Check Python Installation
REM =============================================================================
echo [1/6] Checking Python installation...

set PYTHON_CMD=

REM Try 'python' command
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
    echo       [OK] Found Python !PYTHON_VER!
    goto :python_found
)

REM Try 'py' launcher
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do set PYTHON_VER=%%v
    echo       [OK] Found Python !PYTHON_VER! via py launcher
    goto :python_found
)

REM Python not found
echo       [ERROR] Python is not installed or not in PATH!
echo.
echo       Please install Python 3.10 or higher from:
echo       https://www.python.org/downloads/
echo.
echo       Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:python_found

REM =============================================================================
REM STEP 2: Install/Upgrade Dependencies
REM =============================================================================
echo.
echo [2/6] Installing dependencies...

REM Upgrade pip first
%PYTHON_CMD% -m pip install --upgrade pip >nul 2>&1

REM Install requirements
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo       [ERROR] Failed to install dependencies!
    echo       Please check your internet connection and try again.
    pause
    exit /b 1
)
echo       [OK] Dependencies installed

REM =============================================================================
REM STEP 3: Generate Security Keys (.env file)
REM =============================================================================
echo.
echo [3/6] Setting up security keys...

if exist ".env" (
    echo       [OK] .env file already exists
) else (
    echo       Generating new security keys...
    %PYTHON_CMD% setup_env.py
    if errorlevel 1 (
        echo       [ERROR] Failed to generate security keys!
        pause
        exit /b 1
    )
    echo       [OK] Security keys generated
)

REM =============================================================================
REM STEP 4: Copy config.ini if missing
REM =============================================================================
echo.
echo [4/6] Checking configuration file...

if exist "config.ini" (
    echo       [OK] config.ini already exists
) else (
    if exist "config.ini.example" (
        copy "config.ini.example" "config.ini" >nul
        echo       [OK] Created config.ini from example
        echo.
        echo       ================================================
        echo       IMPORTANT: Edit config.ini with your API keys!
        echo       ================================================
        echo.
    ) else (
        echo       [WARNING] config.ini.example not found!
    )
)

REM =============================================================================
REM STEP 5: Run Database Migrations
REM =============================================================================
echo.
echo [5/6] Running database migrations...

if exist "brain_capital.db" (
    echo       Database found, checking for migrations...
    %PYTHON_CMD% migrate_all.py
    if errorlevel 1 (
        echo       [WARNING] Migration had issues, but continuing...
    ) else (
        echo       [OK] Database migrations complete
    )
) else (
    echo       [OK] No existing database - will be created on first run
)

REM =============================================================================
REM STEP 6: Start the Application
REM =============================================================================
echo.
echo [6/6] Starting application...
echo.
echo ============================================================
echo   SETUP COMPLETE! Starting MIMIC...
echo ============================================================
echo.
echo   Access the application at:
echo   - Local:   http://localhost
echo   - Network: http://YOUR_IP_ADDRESS
echo.
echo   Default login: admin / admin
echo   (Change the password immediately!)
echo.
echo   Press Ctrl+C to stop the server
echo ============================================================
echo.

REM Check if running as Administrator (for port 80)
net session >nul 2>&1
if errorlevel 1 (
    echo [INFO] Running in development mode (port 5000)
    echo        Run as Administrator for production (port 80)
    echo.
    %PYTHON_CMD% app.py
) else (
    echo [INFO] Running in production mode (port 80)
    echo.
    set FLASK_ENV=production
    %PYTHON_CMD% run_server.py
)

echo.
echo ============================================================
echo   APPLICATION STOPPED
echo ============================================================
pause

