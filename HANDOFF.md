# 591 Monitor — Handoff

## User Preferences
- Milestones with testing checkpoints — user confirms before next milestone
- Fix bugs at root cause, no shortcuts/workarounds
- Scrape 591 DOM only — never use their API (even if interceptable via Playwright)
- Keep code light
- Perfect GUI before working on Telegram/bot features

## Stack
- Frontend: React 18 + Vite + TypeScript + custom CSS (workbench.css, Inter + JetBrains Mono)
- Backend: FastAPI + SQLAlchemy sync + Alembic migrations
- Scraper: Playwright sync API, thread-local BrowserManager
- DB: PostgreSQL
- Deploy: Docker Compose (postgres + api + worker containers)
- Dev: `dev.bat` launches venv uvicorn + npm dev in separate windows

## What's Done

### Core (Tasks 1–28, M4)
- Full Docker stack operational
- Playwright scraper: selector `.list-wrapper .item`, extracts all card fields
- DB models: Listing, ListingEvent, SearchProfile, CommuteAnchor, CommuteResult, ScanRun
- Pipeline: upsert, price-change detection, status archiving, commute calc, scoring
- Bulk actions: mass-select checkboxes + save/checking/reject/delete
- Scan History redesigned: stats row per run (profile, +new, updated, gone, duration)
- District selector in Search Profiles (Taipei + New Taipei codes — unverified)

### Post-M4 (previous session)
- **Actions redesign**: save / checking / reject / delete (removed watch/contacted/visited)
- **Archiver fix**: REJECTED = frozen forever; SAVED/CHECKING still archive if detail page gone
- **Multi-profile bug fix**: `matched_profiles` JSON column — each profile tags its listings; `_process_missing_listings` is profile-scoped
- **Profile tags UI**: detail drawer shows which profiles matched (blue pills)
- **posted_at column**: scraped once per new listing from detail page (發佈 date)
- **Listed date bug fix**: "新上架" now captured as today
- **Migrations**: `e5f6a7b8c9d0` (matched_profiles), `f6a7b8c9d0e1` (posted_at)

### This Session (UI redesign + image carousel)
- **image_urls column**: JSON array on Listing, migration `g7b8c9d0e1f2`
- **scrape_listing_detail()**: single detail page open gets posted_at + all images (up to 20); old `scrape_posted_date` kept as shim
- **Pipeline**: `_fetch_listing_detail` replaces `_fetch_posted_date`, stores both posted_at + image_urls
- **Full UI redesign** following designer mockup:
  - `workbench.css`: new CSS design system (oklch dark theme, Inter + JetBrains Mono)
  - `App.tsx`: shell grid (220px sidebar + main + 460px drawer), topbar with scan pill, `AppContext` for shared state
  - Sidebar: Views (New/Active/Saved/Rejected/Delisted), Config (Profiles/Anchors), Scan History
  - `DetailDrawer.tsx`: right-side panel with photo carousel, KV grid, commute table, history, actions
  - `ListingTable.tsx`: complete rewrite — status rail stripe, score bar+number, title+profile pills+badges, price, $/ping, type chip, size, floor parsed, area, commute best-anchor, stacked posted/checked cells
  - `Listings.tsx`: filter chips with add-filter panel, bulk bar, pagination, no tabs
  - `ImageCarousel.tsx`: hover arrows, image counter (used in drawer)
- **Data gaps** (not yet scraped, placeholders):
  - No price delta (prevPrice not in API yet)
  - No facility tags (elevator/AC/wifi etc. not scraped)
  - No score breakdown (scoreParts not in API)

## Known Bugs
1. **Pagination**: Only page 1 scraped (~30 listings). `.pageNext` selector broken. HIGH IMPACT.
2. **Score always ~60**: Google Maps API key not configured → no commute data → scores meaningless.
3. **District codes unverified**: SearchProfiles district selector uses assumed codes — verify against 591 URLs.
4. **Old null-metadata listings**: Short numeric IDs from old broken scans — DB noise, purge manually.
5. **Image selectors**: `scrape_listing_detail()` tries 5 DOM selectors + regex fallback — may need tuning once tested. Existing listings have no images until re-scanned.

## Key File Locations
- Scraper: `backend/app/scraper/scraper_591.py`
- Pipeline: `backend/app/services/pipeline.py`
- Archiver: `backend/app/services/archiver.py`
- Scoring: `backend/app/services/scoring.py`
- Commute: `backend/app/services/commute.py`
- Listings API: `backend/app/api/listings.py`
- DB models: `backend/app/models/listing.py`
- Migrations: `backend/alembic/versions/`
- Frontend shell: `frontend/src/App.tsx` — AppContext, shell, sidebar, topbar
- Listing page: `frontend/src/pages/Listings.tsx` — filter chips, bulk bar
- Table: `frontend/src/components/ListingTable.tsx`
- Drawer: `frontend/src/components/DetailDrawer.tsx`
- CSS: `frontend/src/workbench.css`

## AppContext (shared state)
Defined in `App.tsx`, consumed via `useApp()`:
- `activeView` — current sidebar view (v_new / v_active / v_saved / v_rejected / v_delisted)
- `setActiveView`
- `openListing` — listing shown in right drawer (null = drawer closed)
- `setOpenListing`
- `refreshToken` — increment to trigger listings reload
- `triggerRefresh`

## Recent Sessions

### TagRule System + Bug Fixes (2026-05-11)
- **Commute bug fix**: `db.expire(listing, ['commute_results'])` in `_ensure_commute_and_rescore` — SQLAlchemy session cache held stale empty commute list for listings already processed by profile 1; forced re-fetch from DB
- **NEW badge fix**: confirmed NEW→ACTIVE transition only via `/viewed` endpoint (not during scan); no code change needed
- **TagRule system** — full implementation:
  - `TagRule` model (`backend/app/models/tag_rule.py`) + migration `p6k7l8m9n0o1`
  - `Listing.tags` JSON column (e.g. `["+pet-ok", "-near-mrt"]`)
  - `backend/app/services/tagger.py`: `apply_tags()`, `retag_all_listings()`, `retag_all_tracked()`
  - `apply_tags` called in pipeline at 3 points (new listing, is_new_to_profile, was_updated)
  - `apply_tags` writes `ListingEvent(event_type="tags_updated")` on tag change
  - `retag_all_tracked()` creates ScanRun (job_type="retag_all") → visible in Activity
  - CRUD API: `GET/POST/PUT/DELETE /tag-rules` + `POST /tag-rules/retag-all`
  - Tag pills in ListingTable + DetailDrawer: purple dashed = `+tag`, orange dashed = `-tag`
  - Tag Rules config page at `/tags` sidebar
- **backfill_page_text job**: scrapes full description for existing listings, stores in `raw_data.page_text`; Activity button "📄 Backfill Text"; `_fetch_listing_detail` now stores page_text for all future listings
- **ScanHistory.tsx**: labels/icons for `retag_all`, `backfill_page_text`, `backfill_dates`, `commute_recalc`

### TagRule Design Notes
- Text corpus: `title + address + facilities + raw_data.page_text` (lowercase substring match)
- Tags are cosmetic only — do NOT affect listing status or filtering
- Negative overrides positive if both match same rule
- English keywords risk false positives ("pet" matches "carpet"); Chinese keywords safe
- **Workflow after new TagRule**: Activity → "📄 Backfill Text" → Tag Rules → "↻ Retag all"

## Next Milestones

### M5: GUI Completeness

#### M5a — Posted Date Filter (backend)
- Add `posted_after` / `posted_before` params to `GET /listings` API (currently only `first_seen_after`)
- Backend needs to filter on `posted_at` column

#### M5b — Commute Anchors: MRT Picker + Scooter Mode
- **MRT picker**: searchable dropdown of all Taipei Metro stations (hardcoded lat/lng list)
  - Plus "Custom location" option (address input → geocode)
- **Scooter mode**: add `scooter_minutes` / `scooter_distance_meters` to CommuteResult
  - Google Maps Directions API with `mode=driving`
  - Display alongside transit in table + drawer
- Migration needed: add `scooter_minutes`, `scooter_distance_meters` to `commute_results`

#### M5c — Score System Fix + Weights UI
- Fix scoring: Google Maps API key required, currently no commute data
- Weights editor page: adjust price/commute/freshness/room-type weights
- Persist weights in DB or config table
- `POST /listings/recalculate-scores` endpoint
- Score breakdown in drawer (scoreParts per listing)

#### M5d — Filter Presets + Alert Tab
**Filter Presets**:
- `filter_presets` table: id, name, filter_json
- Sidebar "Views" section shows saved presets with count badges
- Save current filters as named preset

**Alert Tab**:
- Listings matching any preset that arrived since last visit → inbox
- Actions: Save / Reject / Dismiss per item
- `listing_alert_dismissals` table or `alert_dismissed` bool on Listing
- Alert count badge on sidebar

#### M5e — Facility Tags
- Scrape elevator/AC/wifi/parking/furnished/balcony/pets from 591 detail page
- Add `facilities` JSON column to Listing
- Show facility chips in table row + drawer
- Filter by facility in filter panel

### M6: Pagination Fix
- Inspect 591 DOM for next-page button selector
- Fix scraper to paginate all pages
- HIGH IMPACT

### M7: Telegram Alerts (after GUI complete)
- Bot token + chat ID in .env
- Alerts: new listing, price drop, reappeared, matches preset
- Worker scheduler: auto-scan every N minutes per profile

---

## Polish / Bug List

### 🎨 Polish
1. **Tag filter chips** — filter by tag in Listings page not wired yet (biggest gap)
2. **Keyboard shortcuts** — J/K/S/R shown in UI but no `keydown` handler exists
3. **All images fail** → drawer shows nothing, needs fallback placeholder
4. **Score bar null** → displays as 0% bar, should show grey empty state
5. **Retag done feedback** → shows "✓ Done" but no count (e.g. "✓ 4 tagged")
6. **Commute mode** (transit/scooter/distance) not persisted to localStorage, resets on refresh
7. **Empty tag rule** — can save rule with no keywords; should require ≥1 keyword
8. **Empty state** — "No listings" same message whether filtered or genuinely empty

### 🔍 Check / Verify
1. Substring matching — English keywords risky; Chinese fine
2. FILTERED listings not re-evaluated when profile `rejected_keywords` edited; need full rescan
3. `required_keywords` uses AND logic (all must match) — confirm intended
4. Backfill Text → Retag all order required; retag before backfill = 0 matches
5. Tags applied during scan only for new/updated listings; new rule requires manual Retag all
6. `selectedIds` not cleared on sort change — may confuse users
7. Tag rule duplicate names — no backend uniqueness check
8. Lightbox ‹ › nav buttons — test don't accidentally close lightbox
9. 2 listings missing page_text after backfill (38/40) — check if active or archived

### 🧹 Refactor / Dead Code

**Frontend — extract to `src/utils.ts`:**
- `fmtNT()` — defined in `DetailDrawer.tsx` + `ListingTable.tsx` (different behavior, reconcile first)
- `fmtDate()` — defined in both (different outputs: one includes time)
- `scoreColor()` — identical in both files
- `STATUS_DOT` — identical object in both files
- `mapsUrl()` — in `DetailDrawer.tsx`; `ListingTable.tsx` has inline IIFE doing same thing

**Frontend — dead code delete:**
- `bulkDelete()` in `client.ts` — never called (uses `bulkAction` with `action='delete'`)
- `useApp()` in `TagRules.tsx` — destructures nothing
- Settings button in `App.tsx` — `onClick={() => {}}`, does nothing

**Backend — dead code delete:**
- `retag_all_listings` import in `pipeline.py` line 41 — `noqa F401`, not re-exported; remove
- `rescore_all_listings()` — endpoint exists, no UI button; wire Activity button or delete

**Backend — refactor:**
- Profile filtering logic duplicated at `pipeline.py` ~lines 104-115 and ~150-161 → extract `_remove_from_profile(listing, profile_id)` helper
- `ScanHistory.tsx` job-type stats block (~lines 282-334) — repetitive conditionals → extract `<JobStats run={r} />` component
