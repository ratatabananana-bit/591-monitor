# 591 Rental Monitor

Automated 591.com.tw rental scraper with scoring, commute calculation, Telegram alerts, and web dashboard. Runs on a single machine via Docker.

## Quick Start

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Google Maps API key (Geocoding API + Directions API — free tier covers this)
- Telegram bot token + chat ID

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Start

```bash
docker compose up -d
```

Dashboard: **http://localhost:8000**

First build takes ~5 minutes (downloads images, installs deps). Subsequent starts are instant.

### 4. Stop

```bash
docker compose down
```

Data persists in Docker volumes across restarts. To wipe data:

```bash
docker compose down -v
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Required |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Google Maps API key | Yes |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather | Yes |
| `TELEGRAM_CHAT_ID` | Your Telegram chat/group ID | Yes |
| `LOG_LEVEL` | `INFO` or `DEBUG` | No (default: INFO) |

### Google Maps API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Geocoding API** and **Directions API**
3. Create an API key → restrict to those two APIs
4. You get $200 free credit/month — more than enough for personal use

### Telegram Bot Setup

1. Message **@BotFather** on Telegram → `/newbot`
2. Copy the token → `TELEGRAM_BOT_TOKEN`
3. Add the bot to your group or start a chat with it
4. Get your chat ID: send any message to the bot, then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
5. Find `"chat":{"id":XXXXXXX}` — that number is `TELEGRAM_CHAT_ID`

After editing `.env`, restart for changes to take effect:

```bash
docker compose restart
```

---

## Usage

### Web Dashboard

Open **http://localhost:8000**

| Page | What it does |
|---|---|
| **Listings** | All scraped rentals — filter by status, price, score, transit time |
| **Search Profiles** | Configure what to scrape (city, districts, price range, keywords) |
| **Commute Anchors** | Add your workplace/locations — used to calculate commute scores |
| **Scan History** | View past scan runs and results |

### First-Time Setup (in the dashboard)

1. Go to **Commute Anchors** → add your workplace address
2. Go to **Search Profiles** → create a profile (set city, price range, scan interval)
3. Go to **Listings** → click **⟳ Scan Now** to trigger the first scan immediately

### 591 Login Bootstrap (first time only)

591 may require a logged-in session for full results. To log in once and save the session:

```bash
docker compose run --rm worker python -c "
from playwright.sync_api import sync_playwright
from pathlib import Path
import os

profile = os.environ.get('PLAYWRIGHT_PROFILE_PATH', '/data/playwright-profile')
Path(profile).mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(profile, headless=False)
    page = ctx.new_page()
    page.goto('https://rent.591.com.tw')
    input('Log in on 591, then press Enter here...')
    ctx.close()
"
```

After logging in, restart the worker:

```bash
docker compose restart worker
```

### Telegram Commands

```
/scan_now   — trigger an immediate scan across all profiles
/recent     — show last 10 new listings
/saved      — show your saved listings
/watched    — show your watched listings
```

### Listing Actions

From the dashboard, each listing can be marked:

| Action | Meaning |
|---|---|
| **save** | Interested, keep highlighted |
| **watch** | Monitor for changes |
| **reject** | Not interested, hide from main view |
| **contacted** | You messaged the landlord |
| **visited** | You visited in person |

---

## Architecture

```
docker compose
├── postgres        — PostgreSQL 16 database
├── api             — FastAPI + React SPA (port 8000)
│                     Runs: alembic migrations → uvicorn
└── worker          — Scanner + Telegram bot
                      Runs: APScheduler + Playwright + python-telegram-bot
```

All three share the same Docker image (built from `backend/Dockerfile` with React frontend embedded).

---

## Development (local, no Docker)

### Backend

```bash
cd backend
C:\Python314\python.exe -m venv venv
.\venv\Scripts\pip.exe install -e .[dev]
.\venv\Scripts\uvicorn.exe app.main:app --reload --log-level debug
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api to localhost:8000)
```

### Both at once

Double-click `dev.bat` in the project root.

### Run tests

```bash
cd backend
.\venv\Scripts\pytest.exe ../tests/ -v
```

---

## Database Migrations

Migrations run automatically on `api` container startup.

To run manually:

```bash
docker compose exec api alembic upgrade head
```

To create a new migration after changing models:

```bash
docker compose exec api alembic revision --autogenerate -m "description"
```

---

## Troubleshooting

**No listings appearing after scan:**
- Check logs: `docker compose logs worker`
- 591 login may be needed — see Login Bootstrap above
- 591 may have changed their HTML — check selectors in `backend/app/scraper/scraper_591.py`

**Commute data missing (all —):**
- Check `GOOGLE_MAPS_API_KEY` is set correctly
- Verify Geocoding API and Directions API are enabled in Google Cloud Console
- Check billing is active (even with free tier, billing must be enabled)

**Telegram alerts not sending:**
- Verify bot token and chat ID are correct
- Make sure the bot is in the chat / has been messaged first
- Check: `docker compose logs worker | grep telegram`

**API returns 500:**
- Usually database connection issue
- Check: `docker compose logs api`
- Verify postgres container is healthy: `docker compose ps`

**Rebuild after code changes:**

```bash
docker compose build && docker compose up -d
```
