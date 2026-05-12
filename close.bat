@echo off
setlocal
cd /d "%~dp0"

echo.
echo  591 Monitor - Stop
echo  ==================
echo.

docker compose down

echo.
echo [OK] Stopped.
echo.
pause
endlocal
