@echo off
REM Brain Capital - ARQ Worker Launcher
REM Runs the background task processor for trading signals

echo ===================================================
echo    MIMIC ARQ Worker - Brain Capital v9.0
echo ===================================================
echo.

REM Check if Redis is accessible (use 127.0.0.1 for Windows compatibility)
echo [*] Checking Redis connection...
python -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379, db=0); r.ping(); print('    Redis: OK')" 2>nul
if errorlevel 1 (
    echo [!] WARNING: Redis not accessible at 127.0.0.1:6379
    echo [!] Make sure Redis is running before starting the worker
    echo [!] Try: redis-server --bind 127.0.0.1
    echo.
    pause
    exit /b 1
)

REM Set environment variables - use 127.0.0.1 instead of localhost for Windows
if not defined REDIS_URL set REDIS_URL=redis://127.0.0.1:6379/0

echo [*] Redis URL: %REDIS_URL%
echo [*] Press Ctrl+C to stop
echo.

REM Run the worker directly with Python (more compatible with Python 3.10+)
python worker.py

pause

