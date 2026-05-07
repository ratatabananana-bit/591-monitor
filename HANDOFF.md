# 591 Monitor — Handoff

## User Preferences
- Milestones with testing checkpoints — user confirms before next milestone
- Fix bugs at root cause, no shortcuts/workarounds
- Scrape 591 DOM only — never use their API (even if interceptable via Playwright)
- Keep code light

## Stack
- Frontend: React 18 + Vite + TypeScript + TanStack Table v8 + Tailwind CSS 3
- Backend: FastAPI + SQLAlchemy sync + Alembic migrations
- Scraper: Playwright sync API, thread-local BrowserManager
- DB: PostgreSQL
- Deploy: Docker Compose (postgres + api + worker containers)
- Dev: `dev.bat` launches venv uvicorn + npm dev in separate windows

## What's Done (Tasks 1–28+)
- Full Docker stack operational (`docker compose up -d`, api on :8000, frontend on :8000/static)
- Playwright scraper: selector `.list-wrapper .item` (591 current DOM), extracts title/price/size/floor/room_type/district/thumbnail/listing_updated_at
- DB models: Listing, ListingEvent, SearchProfile, CommuteAnchor, CommuteResult, ScanRun
- Listing columns: thumbnail_url, listing_updated_at added (migration c4d8e9f1a023)
- Pipeline: upsert listings, price-change detection, status archiving, commute calc, scoring
- Archiver skips REJECTED/ARCHIVED/UNAVAILABLE (no refresh checks)
- Telegram alerts (thread-isolated event loop)
- Frontend: Listings page with 3 tabs (Active / Saved+Watched / Rejected+Archived)
- Listing table: thumbnail, status, score, title, price, district, size, Listed date, Checked date, commute
- Click row → expand detail panel: large thumbnail, all fields, event history, action buttons
- Scan History page: clickable scan runs showing listings found in each scan window
- Search Profiles CRUD, Commute Anchors CRUD

## Known Bugs
1. **Watch tab**: Marking listing as "watch" doesn't move it to Saved/Watched tab — tab filter logic issue in Listings.tsx (TAB_STATUSES has WATCHED in active, not saved)
2. **Listed date**: Shows 591's last-update date ("N天前更新"), not actual posting date. Posting date requires scraping detail page per listing (slow). Label is approximate.
3. **Scan finds 30 listings**: Pagination next-button selector may not match 591's current DOM — only page 1 scraped. Need to verify `.pageNext` selector.
4. **Old null-metadata listings**: Listings from early broken scans (API interception era) have short numeric IDs (e.g. 105186) and null metadata — DB noise, can be purged manually.
5. **Score always 60**: No commute data (Google Maps API key not set), so all scores default to base 60.

## Next Milestones

### M4: UX Polish (next)
- [ ] Picture carousel: arrows to scroll images on listing cards (591 cards have `image-list` slider)
- [ ] Mass-select checkboxes: bulk reject / delete / status change
- [ ] Search Profiles: add district selector (591 district codes per city)
- [ ] Listing detail: show which profile matched and why (profile name, matched keywords)
- [ ] Scan History: rewrite to show per-profile technical summary (see below)

### M5: Data Quality
- [ ] Scrape listing detail page for actual 上架 date (posted_at) — do lazily on new listings only
- [ ] Fix pagination: verify next-page button selector on 591, scrape multiple pages
- [ ] Purge/hide junk listings (short IDs from old broken scans)
- [ ] Add `posted_at` DB column + migration

### M6: Alerts & Automation
- [ ] Configure Telegram bot token + chat ID in .env
- [ ] Test Telegram alerts end-to-end
- [ ] Worker scheduler: auto-scan every N minutes per profile
- [ ] Price drop alert threshold setting

## Key File Locations
- Scraper: `backend/app/scraper/scraper_591.py` — card selector `.list-wrapper .item`
- Pipeline: `backend/app/services/pipeline.py` — upsert + archiver
- Listings API: `backend/app/api/listings.py` — filters including comma-separated status
- Frontend tabs: `frontend/src/pages/Listings.tsx` — TAB_STATUSES map
- Listing table: `frontend/src/components/ListingTable.tsx`
- Scan History: `frontend/src/pages/ScanHistory.tsx`
- DB models: `backend/app/models/listing.py`
- Migrations: `backend/alembic/versions/`

## Scan History Redesign (M4)

Current scan history shows listing thumbnails per scan — user doesn't want that.

**Wanted**: per-scan technical summary:
- Which profile ran
- How many new listings added
- How many listings updated (price change, metadata fill)
- How many listings gone (→ MISSING_ON_SEARCH or UNAVAILABLE/ARCHIVED)

**Implementation**:
- Add columns to `scan_runs` table: `updated_listings int`, `gone_listings int`, `profile_name varchar` (or join on profile_id)
- Pipeline already knows these counts — track them in `run_scan_for_profile`:
  - `new_count` already tracked
  - add `updated_count` (price changes + metadata fills on existing listings)
  - add `gone_count` (listings that transition to MISSING_ON_SEARCH/UNAVAILABLE/ARCHIVED this run)
- ScanHistory page: replace thumbnail grid with a simple stats row per run:
  ```
  ✓  Profile: "Test"  |  +20 new  |  3 updated  |  5 gone  |  30s  |  2026-05-07 15:00
  ```
- Expand row → show gone listing IDs/titles (no pictures), updated listing IDs with what changed

**Migration needed**: add `updated_listings`, `gone_listings` int columns to `scan_runs`.

## Fix for Watch Tab Bug (quick)
In `frontend/src/pages/Listings.tsx`, change TAB_STATUSES:
```typescript
const TAB_STATUSES: Record<Tab, string[]> = {
  active: ['NEW', 'ACTIVE', 'REAPPEARED', 'MISSING_ON_SEARCH'],  // remove WATCHED
  saved: ['SAVED', 'WATCHED', 'CONTACTED', 'VISITED'],            // add WATCHED here
  rejected: ['REJECTED', 'ARCHIVED', 'UNAVAILABLE'],
}
```
