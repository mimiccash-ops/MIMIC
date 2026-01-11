@echo off
REM =============================================================================
REM TradingView Webhook Test Script (Windows)
REM =============================================================================

echo ============================================
echo   TRADINGVIEW WEBHOOK TEST
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed!
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

REM Install dependencies if needed
echo [INFO] Checking dependencies...
pip install requests python-dotenv >nul 2>&1

REM Prompt for VPS URL/IP
set /p VPS_URL="Enter your VPS domain or IP address: "

if "%VPS_URL%"=="" (
    echo [ERROR] VPS URL/IP is required!
    pause
    exit /b 1
)

echo.
echo Testing webhook at: %VPS_URL%
echo.

REM Ask if using HTTPS
set /p USE_HTTPS="Are you using HTTPS? (y/n) [default: y]: "
if "%USE_HTTPS%"=="" set USE_HTTPS=y

if /i "%USE_HTTPS%"=="y" (
    python test_webhook.py --url %VPS_URL%
) else (
    python test_webhook.py --url %VPS_URL% --no-https
)

echo.
echo ============================================
echo.

pause
