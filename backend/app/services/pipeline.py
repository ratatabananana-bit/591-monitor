import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Listing, ListingEvent, SearchProfile, CommuteAnchor, CommuteResult, ScanRun
from ..services.geocoding import geocode_address
from ..services.commute import get_commute
from ..services.scoring import score_listing, ScoreInput, CommuteData
from ..services.archiver import determine_new_status
from ..services.alerts import (
    send_alert,
    format_new_listing_alert,
    format_price_change_alert,
    format_reappeared_alert,
    format_scan_complete_alert,
)
from ..scraper.scraper_591 import scrape_profile, check_listing_exists

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_scan_for_profile(profile_id: uuid.UUID) -> None:
    db = SessionLocal()
    scan_run = ScanRun(profile_id=profile_id, started_at=utcnow(), status="running")
    db.add(scan_run)
    db.commit()

    try:
        profile = db.query(SearchProfile).filter(SearchProfile.id == profile_id).first()
        if not profile:
            logger.error("Profile %s not found", profile_id)
            scan_run.status = "failed"
            scan_run.errors = {"error": "Profile not found"}
            scan_run.finished_at = utcnow()
            db.commit()
            return

        logger.info("Starting scan for profile: %s", profile.name)
        profile_dict = {
            "city": profile.city,
            "districts": profile.districts,
            "price_min": profile.price_min,
            "price_max": profile.price_max,
            "room_types": profile.room_types,
            "required_keywords": profile.required_keywords,
            "rejected_keywords": profile.rejected_keywords,
        }

        raw_listings = scrape_profile(profile_dict)
        scraped_ids = {l["listing_id"] for l in raw_listings}
        new_count = 0

        for raw in raw_listings:
            listing, is_new = _upsert_listing(db, raw)
            if is_new:
                new_count += 1
                _geocode_listing(db, listing)
                _calculate_commutes(db, listing)
                _score_listing(db, listing)
                db.refresh(listing)
                try:
                    send_alert(format_new_listing_alert(listing))
                except Exception as exc:
                    logger.warning("Alert send failed: %s", exc)

        _process_missing_listings(db, scraped_ids)

        scan_run.listings_found = len(raw_listings)
        scan_run.new_listings = new_count
        scan_run.status = "success"
        scan_run.finished_at = utcnow()
        profile.last_scanned_at = utcnow()
        db.commit()

        try:
            send_alert(format_scan_complete_alert(profile.name, new_count, len(raw_listings)))
        except Exception as exc:
            logger.warning("Scan complete alert failed: %s", exc)

        logger.info("Scan complete for '%s': %d new / %d total", profile.name, new_count, len(raw_listings))

    except Exception as exc:
        logger.error("Scan failed for profile %s: %s", profile_id, exc, exc_info=True)
        scan_run.status = "failed"
        scan_run.errors = {"error": str(exc)}
        scan_run.finished_at = utcnow()
        db.commit()
    finally:
        db.close()


def _upsert_listing(db: Session, raw: dict) -> tuple[Listing, bool]:
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
        return listing, True

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
        if raw["price"] < old_price:
            try:
                send_alert(format_price_change_alert(existing, old_price, raw["price"]))
            except Exception as exc:
                logger.warning("Price change alert failed: %s", exc)

    # Update metadata if we got richer data (fill in nulls)
    for field in ("title", "district", "size_ping", "room_type", "floor", "thumbnail_url", "price"):
        val = raw.get(field)
        if val and not getattr(existing, field):
            setattr(existing, field, val)
    lu = raw.get("listing_updated_at")
    if lu:
        existing.listing_updated_at = datetime.fromisoformat(lu)

    existing.last_seen_at = utcnow()
    existing.missing_count = 0

    if existing.status in ("MISSING_ON_SEARCH", "UNAVAILABLE"):
        existing.status = "REAPPEARED"
        event = ListingEvent(
            listing_id=existing.id,
            event_type="reappeared",
            new_value={"status": "REAPPEARED"},
        )
        db.add(event)
        try:
            send_alert(format_reappeared_alert(existing))
        except Exception as exc:
            logger.warning("Reappeared alert failed: %s", exc)
    elif existing.status == "NEW":
        existing.status = "ACTIVE"

    db.commit()
    db.refresh(existing)
    return existing, False


def _process_missing_listings(db: Session, scraped_ids: set[str]) -> None:
    # Skip REJECTED/ARCHIVED/UNAVAILABLE — they don't need refresh checks
    active_listings = db.query(Listing).filter(
        Listing.status.in_(["NEW", "ACTIVE", "WATCHED", "SAVED", "REAPPEARED", "MISSING_ON_SEARCH"])
    ).all()

    for listing in active_listings:
        if listing.listing_id in scraped_ids:
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

    db.commit()


def _geocode_listing(db: Session, listing: Listing) -> None:
    if listing.lat and listing.lng:
        return
    address = listing.address or f"{listing.district or ''} 台灣"
    coords = geocode_address(address)
    if coords:
        listing.lat, listing.lng = coords
        db.commit()


def _calculate_commutes(db: Session, listing: Listing) -> None:
    if not (listing.lat and listing.lng):
        return

    anchors = db.query(CommuteAnchor).filter(CommuteAnchor.enabled == True).all()
    for anchor in anchors:
        if not (anchor.lat and anchor.lng):
            coords = geocode_address(anchor.address)
            if coords:
                anchor.lat, anchor.lng = coords
                db.commit()

        if not (anchor.lat and anchor.lng):
            continue

        result = get_commute(listing.lat, listing.lng, anchor.lat, anchor.lng)
        if not result:
            continue

        existing = db.query(CommuteResult).filter(
            CommuteResult.listing_id == listing.id,
            CommuteResult.anchor_id == anchor.id,
        ).first()

        if existing:
            existing.walk_minutes = result.get("walk_minutes")
            existing.transit_minutes = result.get("transit_minutes")
            existing.distance_meters = result.get("distance_meters")
            existing.calculated_at = utcnow()
        else:
            cr = CommuteResult(
                listing_id=listing.id,
                anchor_id=anchor.id,
                walk_minutes=result.get("walk_minutes"),
                transit_minutes=result.get("transit_minutes"),
                distance_meters=result.get("distance_meters"),
            )
            db.add(cr)
    db.commit()


def _score_listing(db: Session, listing: Listing) -> None:
    anchors = db.query(CommuteAnchor).filter(CommuteAnchor.enabled == True).all()
    anchor_weights = {a.id: a.weight for a in anchors}

    commute_data = [
        CommuteData(anchor_weight=anchor_weights.get(cr.anchor_id, 1.0), transit_minutes=cr.transit_minutes)
        for cr in listing.commute_results
    ]

    days_old = (utcnow() - listing.first_seen_at).days

    inp = ScoreInput(
        price=listing.price,
        price_min=None,
        price_max=None,
        days_since_first_seen=days_old,
        commute_data=commute_data,
        room_type=listing.room_type,
        required_keywords=[],
        rejected_keywords=[],
        title=listing.title or "",
    )
    listing.score = score_listing(inp)
    db.commit()


def recalculate_all_commutes() -> None:
    db = SessionLocal()
    try:
        listings = db.query(Listing).filter(
            Listing.lat.isnot(None),
            Listing.lng.isnot(None),
        ).all()
        for listing in listings:
            _calculate_commutes(db, listing)
            _score_listing(db, listing)
        logger.info("Recalculated commutes for %d listings", len(listings))
    finally:
        db.close()
