@echo off
setlocal
cd /d "%~dp0"

echo.
echo  591 Monitor - Import Config
echo  ============================
echo.
echo  This will import your search profiles, commute anchors, and tag rules.
echo  Run AFTER install.bat has completed and containers are running.
echo.

docker exec -i 591-monitor-postgres-1 psql -U postgres -d monitor < config-export.sql

if errorlevel 1 (
    echo.
    echo [ERROR] Import failed. Make sure containers are running first:
    echo   docker compose up -d
    echo.
) else (
    echo.
    echo [OK] Config imported successfully!
    echo      Refresh the web UI to see your profiles and tag rules.
    echo.
)

pause
endlocal
