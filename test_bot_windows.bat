@echo off
REM Windows Test Script for Telegram Bot
REM ======================================
REM
REM This script helps you test the standalone bot on Windows
REM before deploying to Linux production server.
REM
REM Usage: test_bot_windows.bat

echo ========================================
echo MIMIC Telegram Bot - Windows Test
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [OK] Python found
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo [OK] Virtual environment ready
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

echo [OK] Virtual environment activated
echo.

REM Check if dependencies are installed
echo [INFO] Checking dependencies...
pip show python-telegram-bot >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

echo [OK] Dependencies installed
echo.

REM Check if .env file exists
if not exist ".env" (
    echo [WARNING] No .env file found!
    echo.
    echo Create .env file with:
    echo   TG_TOKEN=your_bot_token_here
    echo   TG_CHAT_ID=your_chat_id_here
    echo.
    pause
    exit /b 1
)

echo [OK] .env file found
echo.

REM Check if logs directory exists
if not exist "logs" (
    echo [INFO] Creating logs directory...
    mkdir logs
)

echo [OK] Logs directory ready
echo.

REM Clear any existing lock file
if exist "%TEMP%\mimic_telegram_bot.lock" (
    echo [INFO] Clearing old lock file...
    del /f "%TEMP%\mimic_telegram_bot.lock"
)

echo ========================================
echo Starting Telegram Bot...
echo ========================================
echo.
echo Press Ctrl+C to stop the bot
echo.

REM Run the bot
python run_bot.py

pause
