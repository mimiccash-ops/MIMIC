@echo off
chcp 65001 >nul 2>&1
TITLE Brain Capital Bot v8

cd /d "%~dp0"

echo.
echo ==================================================
echo   BRAIN CAPITAL TRADING SYSTEM
echo ==================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH!
    echo Trying py launcher...
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python is not installed!
        pause
        exit /b 1
    )
    echo [OK] Using py launcher
    py app.py
) else (
    echo [OK] Python found
    python app.py
)

echo.
echo --------------------------------------------------
echo   BOT STOPPED
echo --------------------------------------------------
pause
