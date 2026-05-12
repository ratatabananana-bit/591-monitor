@echo off
setlocal
cd /d "%~dp0"

echo.
echo  591 Monitor - Start
echo  ===================
echo.

docker compose up -d

if errorlevel 1 (
    echo [ERROR] Failed to start. Is Docker Desktop running?
    pause
    exit /b 1
)

echo.
echo [OK] Running!
echo      Web UI: http://localhost:8000
echo.
pause
endlocal
