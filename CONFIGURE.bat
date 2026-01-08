@echo off
REM =============================================================================
REM Brain Capital - Configuration Helper
REM =============================================================================
REM This script validates your settings and generates config files
REM =============================================================================

title Brain Capital - Configuration

echo.
echo  ============================================
echo   Brain Capital - Configuration Helper
echo  ============================================
echo.

REM Check if Python is available
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check if admin_settings.ini exists
if not exist "admin_settings.ini" (
    echo [INFO] Creating admin_settings.ini from template...
    echo [INFO] Please fill in your settings in admin_settings.ini
    echo.
    echo Opening admin_settings.ini in notepad...
    start notepad admin_settings.ini
    echo.
    echo After editing, run this script again to validate.
    pause
    exit /b 0
)

echo [INFO] Validating settings...
echo.

python validate_settings.py --generate

echo.
pause

