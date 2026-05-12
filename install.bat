@echo off
setlocal
cd /d "%~dp0"

echo.
echo  591 Rental Monitor - Setup
echo  ==========================
echo.

:: Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running.
    echo Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)

:: Create .env if missing
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [!] Created .env from template.
        echo.
        echo     Open .env in a text editor and fill in:
        echo       TELEGRAM_BOT_TOKEN  - from @BotFather on Telegram
        echo       TELEGRAM_CHAT_ID    - your Telegram user/chat ID
        echo       GOOGLE_MAPS_API_KEY - from Google Cloud Console
        echo.
        echo     Then run install.bat again.
        echo.
        start notepad ".env"
        pause
        exit /b 0
    ) else (
        echo [ERROR] .env.example not found. Cannot create .env.
        pause
        exit /b 1
    )
)

:: Check TELEGRAM_BOT_TOKEN is not empty
for /f "tokens=2 delims==" %%A in ('findstr "TELEGRAM_BOT_TOKEN" .env 2^>nul') do set TG_TOKEN=%%A
if "%TG_TOKEN%"=="" (
    echo [!] TELEGRAM_BOT_TOKEN is empty in .env
    echo     Edit .env and fill in your token, then run install.bat again.
    echo.
    start notepad ".env"
    pause
    exit /b 1
)

echo [*] Building and starting containers...
echo     (First run takes 3-5 minutes to download and build)
echo.
docker compose up --build -d

if errorlevel 1 (
    echo.
    echo [ERROR] Docker Compose failed. See output above.
    pause
    exit /b 1
)

echo.
echo  =============================================
echo   591 Rental Monitor is running!
echo  =============================================
echo.
echo   Web UI:  http://localhost:8000
echo.
echo   To stop:   docker compose down
echo   To start:  docker compose up -d
echo   Logs:      docker compose logs -f
echo.
pause
endlocal
