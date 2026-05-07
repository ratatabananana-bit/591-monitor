@echo off
setlocal
cd /d "%~dp0"

:: ─── Check venv exists ───────────────────────────────────────────────────────
if not exist "backend\venv\Scripts\uvicorn.exe" (
    echo [ERROR] Backend venv not found.
    echo.
    echo Run these commands once to set it up:
    echo   cd /d "%~dp0backend"
    echo   C:\Python314\python.exe -m venv venv
    echo   .\venv\Scripts\pip.exe install -e .[dev]
    echo.
    pause
    exit /b 1
)

:: ─── Check node_modules exists ───────────────────────────────────────────────
if not exist "frontend\node_modules" (
    echo [ERROR] Frontend node_modules not found.
    echo.
    echo Run this once:
    echo   cd /d "%~dp0frontend"
    echo   npm install
    echo.
    pause
    exit /b 1
)

:: ─── Create logs dir ─────────────────────────────────────────────────────────
if not exist "logs" mkdir logs

:: ─── Clear old logs ──────────────────────────────────────────────────────────
type nul > "logs\backend.log"
type nul > "logs\frontend.log"

:: ─── Launch Backend (PowerShell window with Tee — shows AND saves logs) ──────
echo Starting backend...
start "591 Backend" powershell -NoExit -Command ^
  "Set-Location '%~dp0backend'; " ^
  "Write-Host '[BACKEND] Starting uvicorn...' -ForegroundColor Cyan; " ^
  "Write-Host '[BACKEND] Log file: %~dp0logs\backend.log' -ForegroundColor Gray; " ^
  "Write-Host ''; " ^
  "$ErrorActionPreference = 'Continue'; .\venv\Scripts\uvicorn.exe app.main:app --reload --log-level debug 2>&1 | Tee-Object -FilePath '%~dp0logs\backend.log'"

:: ─── Brief pause so backend starts first ─────────────────────────────────────
timeout /t 2 /nobreak >nul

:: ─── Launch Frontend (PowerShell window with Tee) ────────────────────────────
echo Starting frontend...
start "591 Frontend" powershell -NoExit -Command ^
  "Set-Location '%~dp0frontend'; " ^
  "Write-Host '[FRONTEND] Starting Vite dev server...' -ForegroundColor Cyan; " ^
  "Write-Host '[FRONTEND] Log file: %~dp0logs\frontend.log' -ForegroundColor Gray; " ^
  "Write-Host ''; " ^
  "npm run dev 2>&1 | Tee-Object -FilePath '%~dp0logs\frontend.log'"

:: ─── Summary ─────────────────────────────────────────────────────────────────
echo.
echo  591 Monitor starting in two windows
echo.
echo  Backend:   http://localhost:8000
echo  Frontend:  http://localhost:5173
echo.
echo  Logs saved to:
echo    %~dp0logs\backend.log
echo    %~dp0logs\frontend.log
echo.
echo  If something fails, paste the contents of the log file here.
echo  This window can be closed.
echo.
pause
endlocal
