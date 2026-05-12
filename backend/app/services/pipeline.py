import logging
import multiprocessing
import threading
import uuid
from logging.handlers import QueueHandler
from datetime import datetime, timezone

# Scan jobs run as subprocesses for hard-kill support.
_scan_processes: dict[str, multiprocessing.Process] = {}

# Cooperative cancel tokens for non-scan background jobs (commute recalc etc.)
_cancel_tokens: dict[str, threading.Event] = {}


def register_cancel_token(run_id: str) -> threading.Event:
    ev = threading.Event()
    _cancel_tokens[run_id] = ev
    return ev


def _release_cancel_token(run_id: str) -> None:
    _cancel_tokens.pop(run_id, None)


def request_cancel(run_id: str) -> bool:
    # Hard-kill scan subprocess if present
    p = _scan_processes.pop(run_id, None)
    if p is not None:
        if p.is_alive():
            p.terminate()
            p.join(timeout=3)
            if p.is_alive():
                p.kill()
                p.join(timeout=2)
        _mark_run_cancelled(run_id)
        return True
    # Cooperative cancel for thread-based jobs
    ev = _cancel_tokens.get(run_id)
    if ev:
        ev.set()
        return True
    return False


def _mark_run_cancelled(run_id: str) -> None:
    from ..database import SessionLocal as _SL
    db = _SL()
    try:
        run = db.query(ScanRun).filter(ScanRun.id == uuid.UUID(run_id)).first()
        if run and run.status not in ("success", "failed", "cancelled"):
            run.status = "cancelled"
            run.finished_at = utcnow()
            db.commit()
    except Exception:
        pass
    finally:
        db.close()
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Listing, ListingEvent, SearchProfile, CommuteAnchor, CommuteResult, ScanRun
from ..services.geocoding import geocode_address
from ..services.commute import get_commute
from ..services.scoring import score_listing, ScoreInput, CommuteData
from ..services.archiver import determine_new_status
from ..scraper.scraper_591 import scrape_profile, check_listing_exists, scrape_listing_detail
from ..services.tagger import apply_tags, retag_all_listings  # noqa: F401 (retag_all re-exported)

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_scan_for_profile(profile_id: uuid.UUID) -> None:
    """Create ScanRun record then spawn subprocess for hard-kill support."""
    from ..api.logs import get_log_queue
    db = SessionLocal()
    scan_run = ScanRun(profile_id=profile_id, started_at=utcnow(), status="running")
    db.add(scan_run)
    db.commit()
    run_id = str(scan_run.id)
    db.close()  # close before fork — child gets its own pool

    p = multiprocessing.Process(
        target=_scan_body,
        args=(str(profile_id), run_id, get_log_queue()),
        daemon=True,
        name=f"scan-{run_id[:8]}",
    )
    _scan_processes[run_id] = p
    p.start()

    # Watcher thread: runs in main process, waits for subprocess, then triggers alerts
    def _watcher():
        p.join()
        _scan_processes.pop(run_id, None)
        try:
            from .subscription_alerts import trigger_subscription_alerts_sync
            trigger_subscription_alerts_sync()
        except Exception as exc:
            logger.error("Post-scan alert trigger failed: %s", exc, exc_info=True)

    threading.Thread(target=_watcher, daemon=True, name=f"alert-{run_id[:8]}").start()


def _scan_body(profile_id_str: str, run_id_str: str, log_queue=None) -> None:
    """Subprocess entry for a profile scan. Runs to completion; parent kills via SIGTERM if stopped."""
    if log_queue is not None:
        # Route all logs back to the parent process buffer via queue
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(QueueHandler(log_queue))
        root.setLevel(logging.INFO)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            handlers=[logging.StreamHandler()],
            force=True,
        )
    from ..database import engine as _engine
    _engine.dispose()  # close connections inherited from parent process via fork

    profile_id = uuid.UUID(profile_id_str)
    db = SessionLocal()
    try:
        scan_run = db.query(ScanRun).filter(ScanRun.id == uuid.UUID(run_id_str)).first()
        if not scan_run:
            logger.error("ScanRun %s not found in subprocess", run_id_str)
            return

        profile = db.query(SearchProfile).filter(SearchProfile.id == profile_id).first()
        if not profile:
            logger.error("Profile %s not found", profile_id)
            scan_run.status = "failed"
            scan_run.errors = {"error": "Profile not found"}
            scan_run.finished_at = utcnow()
            db.commit()
            return

        scan_run.profile_name = profile.name
        db.commit()

        logger.info("Starting scan for profile: %s", profile.name)
        profile_dict = {
            "city": profile.city,
            "districts": profile.districts,
            "price_min": profile.price_min,
            "price_max": profile.price_max,
            "room_types": profile.room_types,
            "required_keywords": profile.required_keywords,
            "rejected_keywords": profile.rejected_keywords,
            "min_ping": profile.min_ping,
        }

        raw_listings = scrape_profile(profile_dict)
        scraped_ids = {l["listing_id"] for l in raw_listings}
        new_count = 0
        updated_count = 0

        stats = _compute_listing_stats(db)

        from ..models import TagRule as TagRuleModel
        tag_rules = db.query(TagRuleModel).filter(TagRuleModel.enabled == True).all()
        for _rule in tag_rules:
            db.expunge(_rule)
        _profiles_for_tags = db.query(SearchProfile).all()
        profile_names_map = {str(p.id): p.name for p in _profiles_for_tags}

        profile_id_str_local = str(profile_id)
        for raw in raw_listings:
            listing, is_new, was_updated, is_new_to_profile = _upsert_listing(db, raw, profile_id)
            if is_new:
                reject_reason = _fetch_listing_detail(
                    db, listing,
                    rejected_keywords=profile.rejected_keywords or [],
                    required_keywords=profile.required_keywords or [],
                )
                if reject_reason:
                    m_profiles = [p for p in (listing.matched_profiles or []) if p != profile_id_str_local]
                    listing.matched_profiles = m_profiles
                    fbp = list(listing.filtered_by_profiles or [])
                    if profile_id_str_local not in fbp:
                        fbp.append(profile_id_str_local)
                    listing.filtered_by_profiles = fbp
                    if reject_reason == "rejected_keyword":
                        rbp = list(listing.rejected_by_profiles or [])
                        if profile_id_str_local not in rbp:
                            rbp.append(profile_id_str_local)
                        listing.rejected_by_profiles = rbp
                    listing.status = "FILTERED"
                    event = ListingEvent(
                        listing_id=listing.id,
                        event_type="auto_rejected",
                        new_value={"status": "FILTERED", "reason": reject_reason,
                                   "profile_id": profile_id_str_local},
                    )
                    db.add(event)
                    db.commit()
                    continue
                new_count += 1
                _geocode_listing(db, listing)
                _calculate_commutes(db, listing)
                _score_listing(db, listing, stats=stats)
                apply_tags(db, listing, rules=tag_rules, profile_names=profile_names_map)
                db.commit()
                db.refresh(listing)
            elif is_new_to_profile:
                if listing.status == "REJECTED":
                    pass
                elif profile.required_keywords or profile.rejected_keywords:
                    reject_reason = _fetch_listing_detail(
                        db, listing,
                        rejected_keywords=profile.rejected_keywords or [],
                        required_keywords=profile.required_keywords or [],
                    )
                    if reject_reason:
                        m_profiles = [p for p in (listing.matched_profiles or []) if p != profile_id_str_local]
                        listing.matched_profiles = m_profiles
                        fbp = list(listing.filtered_by_profiles or [])
                        if profile_id_str_local not in fbp:
                            fbp.append(profile_id_str_local)
                        listing.filtered_by_profiles = fbp
                        if reject_reason == "rejected_keyword":
                            rbp = list(listing.rejected_by_profiles or [])
                            if profile_id_str_local not in rbp:
                                rbp.append(profile_id_str_local)
                            listing.rejected_by_profiles = rbp
                        if not m_profiles:
                            listing.status = "FILTERED"
                        db.commit()
                        logger.info("Profile %s filtered listing %s — %s",
                                    profile.name, listing.listing_id, reject_reason)
                    else:
                        if listing.status == "FILTERED":
                            listing.status = "NEW"
                            event = ListingEvent(
                                listing_id=listing.id,
                                event_type="status_change",
                                old_value={"status": "FILTERED"},
                                new_value={"status": "NEW"},
                            )
                            db.add(event)
                            new_count += 1
                            logger.info("Listing %s passed keywords for profile %s — restored to NEW",
                                        listing.listing_id, profile.name)
                        db.commit()
                        _ensure_commute_and_rescore(db, listing, stats)
                        apply_tags(db, listing, rules=tag_rules, profile_names=profile_names_map)
                        db.commit()
                else:
                    if listing.status == "FILTERED":
                        listing.status = "NEW"
                        new_count += 1
                        db.commit()
                    _ensure_commute_and_rescore(db, listing, stats)
                    apply_tags(db, listing, rules=tag_rules, profile_names=profile_names_map)
                    db.commit()
            elif was_updated:
                apply_tags(db, listing, rules=tag_rules, profile_names=profile_names_map)
                db.commit()
                updated_count += 1

        gone_count = _process_missing_listings(db, scraped_ids, profile_id)

        scan_run.listings_found = len(raw_listings)
        scan_run.new_listings = new_count
        scan_run.updated_listings = updated_count
        scan_run.gone_listings = gone_count
        scan_run.status = "success"
        scan_run.finished_at = utcnow()
        profile.last_scanned_at = utcnow()
        db.commit()

        logger.info("Scan complete for '%s': %d new / %d updated / %d gone / %d total",
                    profile.name, new_count, updated_count, gone_count, len(raw_listings))

    except Exception as exc:
        logger.error("Scan failed for profile %s: %s", profile_id, exc, exc_info=True)
        try:
            scan_run.status = "failed"
            scan_run.errors = {"error": str(exc)}
            scan_run.finished_at = utcnow()
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _upsert_listing(db: Session, raw: dict, profile_id: uuid.UUID) -> tuple[Listing, bool, bool, bool]:
    """Returns (listing, is_new, was_updated, is_new_to_profile).
    is_new_to_profile=True when an existing listing is matched by this profile for the first time.
    """
    profile_id_str = str(profile_id)
    existing = db.query(Listing).filter(Listing.listing_id == raw["listing_id"]).first()

    if not existing:
        lu = raw.get("listing_updated_at")
        listing = Listing(
            listing_id=raw["listing_id"],
            url=raw["url"],
            title=raw.get("title"),
            price=raw.get("price"),
            district=raw.get("district"),
            address=raw.get("address"),
            size_ping=raw.get("size_ping"),
            room_type=raw.get("room_type"),
            floor=raw.get("floor"),
            thumbnail_url=raw.get("thumbnail_url"),
            listing_updated_at=datetime.fromisoformat(lu) if lu else None,
            status="NEW",
            first_seen_at=utcnow(),
            last_seen_at=utcnow(),
            matched_profiles=[profile_id_str],
            raw_data=raw,
        )
        db.add(listing)
        db.flush()
        event = ListingEvent(
            listing_id=listing.id,
            event_type="new",
            new_value={"price": raw.get("price"), "status": "NEW"},
        )
        db.add(event)
        db.commit()
        db.refresh(listing)
        return listing, True, False, False

    was_updated = False

    # Check price change
    if raw.get("price") and existing.price and raw["price"] != existing.price:
        old_price = existing.price
        existing.price = raw["price"]
        event = ListingEvent(
            listing_id=existing.id,
            event_type="price_change",
            old_value={"price": old_price},
            new_value={"price": raw["price"]},
        )
        db.add(event)
        was_updated = True
        if raw["price"] < old_price:
            pass  # price drop noted in listing events

    # Fill in nulls with richer data
    for field in ("title", "district", "size_ping", "room_type", "floor", "thumbnail_url", "price"):
        val = raw.get(field)
        if val and not getattr(existing, field):
            setattr(existing, field, val)
            was_updated = True
    lu = raw.get("listing_updated_at")
    if lu:
        existing.listing_updated_at = datetime.fromisoformat(lu)

    existing.last_seen_at = utcnow()
    existing.missing_count = 0
    already_matched = profile_id_str in (existing.matched_profiles or [])
    already_filtered = profile_id_str in (existing.filtered_by_profiles or [])
    is_new_to_profile = not already_matched and not already_filtered
    if is_new_to_profile:
        existing.matched_profiles = list(existing.matched_profiles or []) + [profile_id_str]

    if existing.status in ("MISSING_ON_SEARCH", "UNAVAILABLE"):
        existing.status = "REAPPEARED"
        event = ListingEvent(
            listing_id=existing.id,
            event_type="reappeared",
            new_value={"status": "REAPPEARED"},
        )
        db.add(event)
    # NEW → ACTIVE only happens when user views the listing (via /viewed endpoint),
    # not automatically on scan — so the NEW badge stays until user opens it.

    db.commit()
    db.refresh(existing)
    return existing, False, was_updated, is_new_to_profile


def _process_missing_listings(
    db: Session,
    scraped_ids: set[str],
    profile_id: uuid.UUID,
) -> int:
    """Returns count of listings that transitioned to a gone status."""
    profile_id_str = str(profile_id)
    gone_statuses = {"MISSING_ON_SEARCH", "UNAVAILABLE", "ARCHIVED"}
    active_listings = db.query(Listing).filter(
        Listing.status.in_(["NEW", "ACTIVE", "CHECKING", "SAVED", "REAPPEARED", "MISSING_ON_SEARCH"])
        # FILTERED and REJECTED excluded — not tracked for gone detection
    ).all()

    gone_count = 0
    for listing in active_listings:
        if listing.listing_id in scraped_ids:
            continue
        # Only process listings this profile has previously found
        if profile_id_str not in (listing.matched_profiles or []):
            continue

        listing.missing_count = (listing.missing_count or 0) + 1
        detail_exists = check_listing_exists(listing.listing_id)
        new_status = determine_new_status(
            listing.status,
            found_in_search=False,
            detail_exists=detail_exists,
            missing_count=listing.missing_count,
        )

        if new_status != listing.status:
            old_status = listing.status
            listing.status = new_status
            event = ListingEvent(
                listing_id=listing.id,
                event_type="status_change",
                old_value={"status": old_status},
                new_value={"status": new_status},
            )
            db.add(event)
            logger.info("Listing %s: %s → %s", listing.listing_id, old_status, new_status)
            if new_status in gone_statuses:
                gone_count += 1
                # Notify subscribers if a SAVED listing got delisted
                if old_status == "SAVED":
                    try:
                        from .subscription_alerts import trigger_delisted_alert
                        trigger_delisted_alert(listing, db)
                    except Exception as exc:
                        logger.warning("Delisted alert failed for %s: %s", listing.listing_id, exc)

    db.commit()
    return gone_count


def _fetch_listing_detail(
    db: Session,
    listing: Listing,
    rejected_keywords: list[str] | None = None,
    required_keywords: list[str] | None = None,
) -> str:
    """
    Scrape detail page for posted_at + image_urls + facilities.
    Also checks full page text against rejected/required keywords.
    Returns rejection reason:
      ""                  – passes (no rejection)
      "rejected_keyword"  – listing contains a profile's blacklisted keyword
      "missing_required"  – listing lacks a required keyword
    """
    try:
        detail = scrape_listing_detail(listing.listing_id)
        changed = False
        if detail.get("posted_at"):
            listing.posted_at = detail["posted_at"]
            changed = True
        if detail.get("address") and not listing.address:
            listing.address = detail["address"]
            changed = True
        if detail.get("image_urls"):
            listing.image_urls = detail["image_urls"]
            changed = True
        if "facilities" in detail:
            listing.facilities = detail["facilities"]
            changed = True
        # Store page_text so tagger can match keywords against full description
        if detail.get("page_text"):
            rd = dict(listing.raw_data or {})
            rd["page_text"] = detail["page_text"]
            listing.raw_data = rd
            changed = True
        if changed:
            db.commit()

        # Keyword check against full article text
        page_text = (detail.get("page_text") or "").lower()
        if page_text:
            for kw in (rejected_keywords or []):
                if kw.lower() in page_text:
                    logger.info(
                        "Auto-reject listing %s: rejected keyword '%s' in article",
                        listing.listing_id, kw,
                    )
                    return "rejected_keyword"
            if required_keywords:
                if not any(kw.lower() in page_text for kw in required_keywords):
                    logger.info(
                        "Auto-reject listing %s: no required keyword found in article",
                        listing.listing_id,
                    )
                    return "missing_required"

    except Exception as exc:
        logger.warning("Could not fetch detail for %s: %s", listing.listing_id, exc)
    return ""


def _geocode_listing(db: Session, listing: Listing) -> None:
    if listing.lat and listing.lng:
        return
    raw = listing.address or listing.district or ''
    if not raw:
        return
    # Always append 台灣 so geocoder doesn't match other countries
    address = raw if '台灣' in raw else f"{raw} 台灣"
    coords = geocode_address(address)
    if coords:
        listing.lat, listing.lng = coords
        db.commit()


def _calculate_commutes(db: Session, listing: Listing, cancel_ev=None) -> int:
    """Returns count of anchors successfully calculated (got at least transit or scooter minutes)."""
    origin_addr = listing.address or listing.district
    if not origin_addr and not (listing.lat and listing.lng):
        return 0
    if not origin_addr:
        origin_addr = f"{listing.lat},{listing.lng}"

    anchors = db.query(CommuteAnchor).filter(CommuteAnchor.enabled == True).all()
    success = 0
    for anchor in anchors:
        if cancel_ev and cancel_ev.is_set():
            return success

        if not anchor.address:
            continue

        result = get_commute(origin_addr, anchor.address, cancel_ev=cancel_ev)
        if not result:
            logger.warning("Commute failed: %s → %s", origin_addr[:40], anchor.address[:40])
            continue

        got_data = result.get("transit_minutes") is not None
        if got_data:
            success += 1

        existing = db.query(CommuteResult).filter(
            CommuteResult.listing_id == listing.id,
            CommuteResult.anchor_id == anchor.id,
        ).first()

        if existing:
            existing.walk_minutes = result.get("walk_minutes")
            existing.transit_minutes = result.get("transit_minutes")
            existing.distance_meters = result.get("distance_meters")
            existing.scooter_minutes = result.get("scooter_minutes")
            existing.scooter_distance_meters = result.get("scooter_distance_meters")
            existing.calculated_at = utcnow()
        else:
            cr = CommuteResult(
                listing_id=listing.id,
                anchor_id=anchor.id,
                walk_minutes=result.get("walk_minutes"),
                transit_minutes=result.get("transit_minutes"),
                distance_meters=result.get("distance_meters"),
                scooter_minutes=result.get("scooter_minutes"),
                scooter_distance_meters=result.get("scooter_distance_meters"),
            )
            db.add(cr)
    db.commit()
    return success


def _compute_listing_stats(db: Session) -> dict:
    """
    Compute corpus-relative percentiles for all listings with data.
    price_percentile[id] = 0-100, 100 = cheapest listing in corpus.
    size_percentile[id]  = 0-100, 100 = biggest listing in corpus.
    """
    _ACTIVE = ["NEW", "ACTIVE", "CHECKING", "SAVED", "REAPPEARED",
               "MISSING_ON_SEARCH", "WATCHED", "CONTACTED", "VISITED"]
    rows = db.query(Listing.id, Listing.price, Listing.size_ping).filter(
        Listing.status.in_(_ACTIVE)
    ).all()

    priced = sorted([(r.price, r.id) for r in rows if r.price], key=lambda x: x[0])
    sized = sorted([(r.size_ping, r.id) for r in rows if r.size_ping], key=lambda x: x[0])

    n_price = len(priced)
    n_size = len(sized)

    price_percentile: dict = {}
    for rank, (_, lid) in enumerate(priced):
        price_percentile[lid] = round((1.0 - rank / n_price) * 100.0, 1) if n_price > 1 else 50.0

    size_percentile: dict = {}
    for rank, (_, lid) in enumerate(sized):
        size_percentile[lid] = round((rank / n_size) * 100.0, 1) if n_size > 1 else 50.0

    return {"price_percentile": price_percentile, "size_percentile": size_percentile}


def _score_listing(db: Session, listing: Listing, stats: dict | None = None) -> None:
    anchors = db.query(CommuteAnchor).filter(CommuteAnchor.enabled == True).all()
    anchor_weights = {a.id: a.weight for a in anchors}

    commute_data = [
        CommuteData(anchor_weight=anchor_weights.get(cr.anchor_id, 1.0), transit_minutes=cr.transit_minutes)
        for cr in listing.commute_results
    ]

    ref_date = listing.posted_at or listing.first_seen_at
    days_old = max(0, (utcnow() - ref_date).days)

    # Pull keywords and price range from all matched profiles
    required_kws: list[str] = []
    rejected_kws: list[str] = []
    price_mins: list[int] = []
    price_maxs: list[int] = []
    if listing.matched_profiles:
        try:
            profile_uuids = [uuid.UUID(pid) for pid in listing.matched_profiles]
            profiles = db.query(SearchProfile).filter(SearchProfile.id.in_(profile_uuids)).all()
            for p in profiles:
                required_kws.extend(p.required_keywords or [])
                rejected_kws.extend(p.rejected_keywords or [])
                if p.price_min is not None:
                    price_mins.append(p.price_min)
                if p.price_max is not None:
                    price_maxs.append(p.price_max)
            required_kws = list(set(required_kws))
            rejected_kws = list(set(rejected_kws))
        except Exception as exc:
            logger.debug("Could not load profile keywords for listing %s: %s", listing.listing_id, exc)

    inp = ScoreInput(
        price=listing.price,
        price_min=min(price_mins) if price_mins else None,
        price_max=max(price_maxs) if price_maxs else None,
        size_ping=listing.size_ping,
        listing_age_days=days_old,
        commute_data=commute_data,
        room_type=listing.room_type,
        required_keywords=required_kws,
        rejected_keywords=rejected_kws,
        title=listing.title or "",
    )
    listing.score, listing.score_breakdown = score_listing(inp)
    db.commit()


def _ensure_commute_and_rescore(db: Session, listing: Listing, stats: dict | None = None) -> None:
    """
    Called when an existing listing passes keyword check for a new profile.
    If commute results are missing (e.g. parallel scan race), geocode + recalculate.
    Always rescores so the score reflects the updated matched_profiles list.
    """
    # Expire commute_results from session cache so we get fresh DB data (parallel scan safety)
    db.expire(listing, ['commute_results'])
    if not listing.commute_results:
        logger.info("Computing commutes for listing %s (new to this profile)", listing.listing_id)
        _geocode_listing(db, listing)
        _calculate_commutes(db, listing)
    _score_listing(db, listing, stats=stats)


def backfill_posted_dates() -> None:
    """Fetch posted_at for all listings where it is currently null."""
    db = SessionLocal()
    run = ScanRun(started_at=utcnow(), status="running", job_type="backfill_dates",
                  listings_found=0, new_listings=0, updated_listings=0, gone_listings=0)
    db.add(run)
    db.commit()
    try:
        listings = db.query(Listing).filter(Listing.posted_at.is_(None)).all()
        run.listings_found = len(listings)
        db.commit()
        filled = 0
        failed = 0
        for listing in listings:
            try:
                detail = scrape_listing_detail(listing.listing_id)
                if detail.get("posted_at"):
                    listing.posted_at = detail["posted_at"]
                    db.commit()
                    filled += 1
                    logger.info("Backfilled posted_at for %s: %s", listing.listing_id, detail["posted_at"])
                else:
                    failed += 1
                    logger.debug("No posted_at found for %s", listing.listing_id)
            except Exception as exc:
                failed += 1
                logger.warning("Backfill failed for %s: %s", listing.listing_id, exc)
        run.new_listings = filled
        run.updated_listings = failed
        if failed == 0:
            run.status = "success"
        elif filled == 0:
            run.status = "failed"
            run.errors = {"no_date_found": failed, "total": len(listings)}
        else:
            run.status = "partial"
            run.errors = {"no_date_found": failed, "filled": filled, "total": len(listings)}
        run.finished_at = utcnow()
        db.commit()
        logger.info("Backfill posted_at: %d filled / %d not found / %d total", filled, failed, len(listings))
    except Exception as exc:
        run.status = "failed"
        run.errors = {"error": str(exc)}
        run.finished_at = utcnow()
        db.commit()
        logger.error("Backfill posted_at failed: %s", exc, exc_info=True)
    finally:
        db.close()


def backfill_page_text() -> None:
    """Scrape detail page for all listings missing page_text, store it for tagging."""
    db = SessionLocal()
    run = ScanRun(started_at=utcnow(), status="running", job_type="backfill_page_text",
                  listings_found=0, new_listings=0, updated_listings=0, gone_listings=0)
    db.add(run)
    db.commit()
    try:
        ACTIVE_STATUSES = ["NEW", "ACTIVE", "REAPPEARED", "CHECKING", "SAVED",
                           "MISSING_ON_SEARCH", "FILTERED", "REJECTED"]
        # Only listings missing page_text in raw_data
        all_listings = db.query(Listing).filter(Listing.status.in_(ACTIVE_STATUSES)).all()
        missing = [l for l in all_listings
                   if not (l.raw_data or {}).get("page_text")]
        run.listings_found = len(missing)
        db.commit()

        filled = 0
        failed = 0
        for listing in missing:
            try:
                detail = scrape_listing_detail(listing.listing_id)
                rd = dict(listing.raw_data or {})
                changed = False
                if detail.get("page_text"):
                    rd["page_text"] = detail["page_text"]
                    changed = True
                if detail.get("posted_at") and not listing.posted_at:
                    listing.posted_at = detail["posted_at"]
                    changed = True
                if detail.get("image_urls") and not listing.image_urls:
                    listing.image_urls = detail["image_urls"]
                    changed = True
                if detail.get("facilities") and not listing.facilities:
                    listing.facilities = detail["facilities"]
                    changed = True
                if changed:
                    listing.raw_data = rd
                    db.commit()
                if detail.get("page_text"):
                    filled += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning("backfill_page_text: listing %s failed: %s", listing.listing_id, e)
                failed += 1

        run.new_listings = filled
        run.updated_listings = failed
        run.status = "success"
        run.finished_at = utcnow()
        db.commit()
        logger.info("backfill_page_text: %d filled / %d failed / %d total", filled, failed, len(missing))
    except Exception as exc:
        run.status = "failed"
        run.errors = {"error": str(exc)}
        run.finished_at = utcnow()
        db.commit()
        logger.error("backfill_page_text failed: %s", exc, exc_info=True)
    finally:
        db.close()


def rescore_all_listings() -> None:
    """Recompute score + breakdown for every listing using current posted_at data."""
    db = SessionLocal()
    run = ScanRun(started_at=utcnow(), status="running", job_type="rescore",
                  listings_found=0, new_listings=0, updated_listings=0, gone_listings=0)
    db.add(run)
    db.commit()
    try:
        listings = db.query(Listing).all()
        run.listings_found = len(listings)
        db.commit()
        stats = _compute_listing_stats(db)
        for listing in listings:
            _score_listing(db, listing, stats=stats)
        run.new_listings = len(listings)
        run.status = "success"
        run.finished_at = utcnow()
        db.commit()
        logger.info("Rescore complete: %d listings", len(listings))
    except Exception as exc:
        run.status = "failed"
        run.errors = {"error": str(exc)}
        run.finished_at = utcnow()
        db.commit()
        logger.error("Rescore failed: %s", exc, exc_info=True)
    finally:
        db.close()


def recalculate_all_commutes() -> None:
    db = SessionLocal()
    run = ScanRun(started_at=utcnow(), status="running", job_type="commute_recalc",
                  listings_found=0, new_listings=0, updated_listings=0, gone_listings=0)
    db.add(run)
    db.commit()
    cancel_ev = register_cancel_token(str(run.id))
    try:
        # Geocode any listings missing coords first
        ACTIVE_STATUSES = ["NEW", "ACTIVE", "CHECKING", "SAVED", "REAPPEARED",
                           "MISSING_ON_SEARCH", "WATCHED", "CONTACTED", "VISITED"]

        missing_coords = db.query(Listing).filter(
            Listing.status.in_(ACTIVE_STATUSES),
            (Listing.lat.is_(None)) | (Listing.lng.is_(None))
        ).all()
        for listing in missing_coords:
            _geocode_listing(db, listing)

        all_listings = db.query(Listing).filter(Listing.status.in_(ACTIVE_STATUSES)).all()
        run.listings_found = len(all_listings)
        db.commit()

        # Compute corpus-relative stats once for the whole batch
        stats = _compute_listing_stats(db)

        ok = 0
        fail = 0
        skipped = 0
        for listing in all_listings:
            if cancel_ev.is_set():
                run.status = "cancelled"
                run.finished_at = utcnow()
                run.errors = {"cancelled": True}
                db.commit()
                logger.info("Commute recalc cancelled after %d/%d listings", ok + fail + skipped, len(all_listings))
                return

            has_origin = listing.address or listing.district or (listing.lat and listing.lng)
            if not has_origin:
                skipped += 1
                logger.debug("Skipped listing %s — no address or coords", listing.listing_id)
                continue

            anchors_ok = _calculate_commutes(db, listing, cancel_ev=cancel_ev)
            if anchors_ok > 0:
                ok += 1
            else:
                fail += 1
            _score_listing(db, listing, stats=stats)

        run.new_listings = ok
        run.updated_listings = fail
        run.status = "success"
        run.finished_at = utcnow()
        db.commit()
        logger.info("Commute recalc: %d ok / %d failed / %d skipped / %d total",
                    ok, fail, skipped, len(all_listings))
    except Exception as exc:
        run.status = "failed"
        run.errors = {"error": str(exc)}
        run.finished_at = utcnow()
        db.commit()
        logger.error("Commute recalculation failed: %s", exc, exc_info=True)
    finally:
        _release_cancel_token(str(run.id))
        db.close()
