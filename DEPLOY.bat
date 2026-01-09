@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM ============================================================================
REM MIMIC - One-Click VPS Deployment
REM ============================================================================
REM Double-click this file to deploy to your VPS
REM First time: Edit the configuration below
REM ============================================================================

cd /d "%~dp0"

REM ============================================================================
REM CONFIGURATION - Edit these values for your VPS
REM ============================================================================

set VPS_USER=root
set VPS_HOST=YOUR_VPS_IP
set VPS_PORT=22
set REMOTE_PATH=/var/www/mimic
set SERVICE_NAME=mimic

REM SSH key path (leave empty to use default)
set SSH_KEY=

REM ============================================================================
REM SCRIPT LOGIC
REM ============================================================================

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           MIMIC - VPS Deployment                             ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM Check if configured
if "%VPS_HOST%"=="YOUR_VPS_IP" (
    echo [ERROR] VPS_HOST not configured!
    echo.
    echo Please edit DEPLOY.bat and set your VPS details:
    echo     set VPS_HOST=your-vps-ip-address
    echo.
    pause
    exit /b 1
)

echo [INFO] Target: %VPS_USER%@%VPS_HOST%:%REMOTE_PATH%
echo.

REM Check for rsync in Git Bash
set RSYNC_PATH=C:\Program Files\Git\usr\bin\rsync.exe
if exist "%RSYNC_PATH%" (
    echo [INFO] Using rsync from Git for Windows
    goto :use_rsync
)

REM Check for WSL and rsync in WSL
wsl --list >nul 2>&1
if %ERRORLEVEL%==0 (
    wsl which rsync >nul 2>&1
    if %ERRORLEVEL%==0 (
        echo [INFO] Using rsync via WSL
        goto :use_wsl
    ) else (
        echo [INFO] WSL found but rsync not installed. Installing rsync...
        wsl sudo apt-get update -qq && wsl sudo apt-get install -y rsync >nul 2>&1
        if %ERRORLEVEL%==0 (
            echo [INFO] rsync installed successfully
            goto :use_wsl
        ) else (
            echo [WARNING] Could not install rsync in WSL, using scp instead
            goto :use_scp
        )
    )
)

REM Fall back to scp (available with OpenSSH on Windows 10+)
:use_scp
where scp >nul 2>&1
if %ERRORLEVEL%==0 (
    echo [INFO] Using scp for file transfer
    goto :do_scp
) else (
    echo [ERROR] No transfer method available!
    echo Please install one of:
    echo   - Git for Windows (includes rsync)
    echo   - WSL with rsync
    echo   - OpenSSH client
    pause
    exit /b 1
)

:do_scp
echo [INFO] Creating remote directory...
ssh -o StrictHostKeyChecking=no -p %VPS_PORT% %VPS_USER%@%VPS_HOST% "mkdir -p %REMOTE_PATH%"

echo [INFO] Uploading files via scp (this may take a while)...
echo [INFO] Excluding: .git, .env, *.db, __pycache__, venv, logs, secrets

REM Create a temporary directory with files to upload
set TEMP_DIR=%TEMP%\mimic_deploy_%RANDOM%
mkdir "%TEMP_DIR%" 2>nul

REM Use robocopy to copy files excluding unwanted ones
robocopy . "%TEMP_DIR%" /E /XD .git __pycache__ venv .venv logs secrets .pytest_cache node_modules .idea .vscode /XF .env *.db *.pyc *.log *.tmp *.bak deploy.ps1 DEPLOY.bat /NFL /NDL /NJH /NJS /NC /NS >nul

REM Upload via scp
scp -r -o StrictHostKeyChecking=no -P %VPS_PORT% "%TEMP_DIR%\*" %VPS_USER%@%VPS_HOST%:%REMOTE_PATH%/

set SCP_RESULT=%ERRORLEVEL%

REM Cleanup temp directory
rmdir /S /Q "%TEMP_DIR%" 2>nul

if %SCP_RESULT%==0 (
    echo.
    echo [SUCCESS] Files uploaded!
) else (
    echo.
    echo [ERROR] Upload failed!
    pause
    exit /b 1
)
goto :ask_restart

:use_rsync
set SSH_OPTS=-o StrictHostKeyChecking=no -o BatchMode=yes -p %VPS_PORT%
if not "%SSH_KEY%"=="" set SSH_OPTS=%SSH_OPTS% -i %SSH_KEY%

echo [INFO] Syncing files...
"%RSYNC_PATH%" -avz --progress --delete ^
    --exclude=".git" ^
    --exclude=".env" ^
    --exclude="*.db" ^
    --exclude="__pycache__" ^
    --exclude="*.pyc" ^
    --exclude="venv" ^
    --exclude=".venv" ^
    --exclude="logs/" ^
    --exclude="secrets/" ^
    --exclude="*.log" ^
    --exclude="deploy.ps1" ^
    --exclude="DEPLOY.bat" ^
    --exclude="static/avatars/*" ^
    -e "ssh %SSH_OPTS%" ^
    ./ %VPS_USER%@%VPS_HOST%:%REMOTE_PATH%/

if %ERRORLEVEL%==0 (
    echo.
    echo [SUCCESS] Files synchronized!
) else (
    echo.
    echo [ERROR] Sync failed!
    pause
    exit /b 1
)
goto :ask_restart

:use_wsl
echo [INFO] Syncing files via WSL...

REM Convert Windows path to WSL path
REM Get current directory
set "WIN_PATH=%cd%"
REM Extract drive letter and convert to lowercase
set "DRIVE_LETTER=%WIN_PATH:~0,1%"
REM Convert to lowercase using a simple trick
for %%a in (a b c d e f g h i j k l m n o p q r s t u v w x y z) do (
    if /i "%DRIVE_LETTER%"=="%%a" set "DRIVE_LOWER=%%a"
)
REM Build WSL path: /mnt/c/Users/...
set "WSL_PATH=/mnt/%DRIVE_LOWER%/%WIN_PATH:~3%"
set "WSL_PATH=%WSL_PATH:\=/%"

echo [INFO] WSL Path: %WSL_PATH%

wsl rsync -avz --progress --delete ^
    --exclude=".git" ^
    --exclude=".env" ^
    --exclude="*.db" ^
    --exclude="__pycache__" ^
    --exclude="*.pyc" ^
    --exclude="venv" ^
    --exclude=".venv" ^
    --exclude="logs/" ^
    --exclude="secrets/" ^
    --exclude="*.log" ^
    --exclude="deploy.ps1" ^
    --exclude="DEPLOY.bat" ^
    -e "ssh -o StrictHostKeyChecking=no -p %VPS_PORT%" ^
    "%WSL_PATH%/" "%VPS_USER%@%VPS_HOST%:%REMOTE_PATH%/"

if %ERRORLEVEL%==0 (
    echo.
    echo [SUCCESS] Files synchronized!
) else (
    echo.
    echo [ERROR] Sync failed!
    pause
    exit /b 1
)

:ask_restart
echo.
set /p RESTART="Restart service on VPS? (y/N): "
if /i "%RESTART%"=="y" (
    echo [INFO] Restarting %SERVICE_NAME% service...
    ssh -o StrictHostKeyChecking=no -p %VPS_PORT% %VPS_USER%@%VPS_HOST% "sudo systemctl restart %SERVICE_NAME% && sudo systemctl status %SERVICE_NAME% --no-pager"
    if %ERRORLEVEL%==0 (
        echo [SUCCESS] Service restarted!
    ) else (
        echo [WARNING] Service restart may have issues
    )
)

:done
echo.
echo ══════════════════════════════════════════════════════════════
echo   DEPLOYMENT COMPLETE
echo   Target: %VPS_USER%@%VPS_HOST%:%REMOTE_PATH%
echo ══════════════════════════════════════════════════════════════
echo.
pause
