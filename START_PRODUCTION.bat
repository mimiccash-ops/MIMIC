@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
REM =============================================================================
REM BRAIN CAPITAL - ONE-CLICK PRODUCTION START
REM https://mimic.cash
REM =============================================================================
REM Double-click this file to start the production server
REM =============================================================================

cd /d "%~dp0"

echo Starting Brain Capital Production Server...
echo Domain: https://mimic.cash
echo.

REM Set production environment variables
set FLASK_ENV=production
set PRODUCTION_DOMAIN=https://mimic.cash,https://www.mimic.cash

REM Check if .env exists, create if not
if not exist ".env" (
    echo Creating .env file with secure keys...
    
    REM Generate keys using Python to ensure proper encoding
    python -c "import secrets; from cryptography.fernet import Fernet; sk=secrets.token_hex(32); fk=Fernet.generate_key().decode(); f=open('.env','w',encoding='utf-8'); f.write(f'FLASK_ENV=production\nFLASK_SECRET_KEY={sk}\nBRAIN_CAPITAL_MASTER_KEY={fk}\nPRODUCTION_DOMAIN=https://mimic.cash,https://www.mimic.cash\n'); f.close(); print('.env created!')"
)

REM Load existing .env
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "%%a=%%b"
)

REM Ensure production mode
set FLASK_ENV=production
set PRODUCTION_DOMAIN=https://mimic.cash,https://www.mimic.cash

REM Install waitress if needed
python -c "import waitress" 2>nul || pip install waitress

echo.
echo ========================================
echo   PRODUCTION SERVER STARTING
echo   Domain: https://mimic.cash
echo   Port: 80
echo   Press Ctrl+C to stop
echo ========================================
echo.

REM Start production server
python run_server.py

pause

