@echo off
TITLE Звільнення Порту 80
color 0b

echo.
echo ==================================================
echo   STOPPING WINDOWS SERVICES (IIS / HTTP)
echo ==================================================
echo.

:: Зупинка IIS та HTTP служб (потрібні права адміра)
net stop w3svc /y
net stop http /y
net stop iisadmin /y
iisreset /stop

echo.
echo ==================================================
echo   KILLING PROCESSES ON PORT 80
echo ==================================================
echo.

:: Примусове завершення процесів, що сидять на порту 80
for /f "tokens=5" %%a in ('netstat -aon ^| find ":80" ^| find "LISTENING"') do (
    echo Killing PID %%a...
    taskkill /f /pid %%a
)

echo.
echo ==================================================
echo   DONE! TRY RUNNING THE BOT NOW.
echo ==================================================
echo.
pause