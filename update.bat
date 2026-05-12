@echo off
setlocal
cd /d "%~dp0"

echo.
echo  591 Monitor - Update
echo  ====================
echo.

git pull
if errorlevel 1 (
    echo [ERROR] Git pull failed. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo [*] Rebuilding containers with latest code...
echo.
docker compose up --build -d

if errorlevel 1 (
    echo [ERROR] Docker build failed. See output above.
    pause
    exit /b 1
)

echo.
echo [OK] Updated and running!
echo      Web UI: http://localhost:8000
echo.
pause
endlocal
