"""
Tagger service: applies TagRules + system tags to listings, writing all tags to listing.tags.

Tag format:
  "+pet-ok"          — keyword-matched rule tag (positive)
  "-pet-ok"          — reject-keyword-matched rule tag (negative)
  "badge:new"        — listing.status == NEW
  "badge:reappeared" — listing.status == REAPPEARED
  "badge:fresh"      — posted/first_seen within 3 days
  "badge:stale"      — posted/first_seen older than 14 days
  "profile:NAME"     — listing matched by that search profile
"""
import logging
import re
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from ..models import Listing, TagRule, ScanRun, SearchProfile
from ..models.listing import ListingEvent

logger = logging.getLogger(__name__)


_NEGATION_PREFIXES = ('不', '無', '非')


def _keyword_matches(keyword: str, text: str) -> bool:
    """Check if keyword appears in text.

    If the keyword starts with a negation character (不/無/非) it is matched
    literally — e.g. '不走路' finds exactly '不走路'.

    Otherwise a negative lookbehind is automatically applied so that the
    keyword is NOT matched when immediately preceded by 不/無/非 — e.g.
    '可寵' will match '可寵' but not '不可寵' or '無可寵'.
    """
    if keyword.startswith(_NEGATION_PREFIXES):
        return keyword in text
    pattern = r'(?<!不)(?<!無)(?<!非)' + re.escape(keyword)
    return bool(re.search(pattern, text))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _text_for_listing(listing: Listing) -> str:
    """Concatenate all searchable text fields into one lowercase string."""
    parts = []
    if listing.title:
        parts.append(listing.title)
    if listing.address:
        parts.append(listing.address)
    if listing.facilities:
        parts.extend(listing.facilities)
    # page_text stored in raw_data if present
    if listing.raw_data and isinstance(listing.raw_data, dict):
        pt = listing.raw_data.get("page_text") or ""
        if pt:
            parts.append(pt)
    return " ".join(parts).lower()


def _badge_tags(listing: Listing) -> list[str]:
    badges: list[str] = []
    if listing.status == "NEW":
        badges.append("badge:new")
    elif listing.status == "REAPPEARED":
        badges.append("badge:reappeared")
    elif listing.status in ("MISSING_ON_SEARCH", "UNAVAILABLE"):
        badges.append("badge:missing")
    ref = listing.posted_at or listing.first_seen_at
    age_days = max(0.0, (datetime.now(timezone.utc) - ref).total_seconds() / 86400)
    if age_days <= 3:
        badges.append("badge:fresh")
    elif age_days > 14:
        badges.append("badge:stale")
    return badges


def _profile_tags(listing: Listing, profile_names: dict[str, str]) -> list[str]:
    return [
        f"profile:{profile_names[pid]}"
        for pid in (listing.matched_profiles or [])
        if pid in profile_names
    ]


def apply_tags(
    db: Session,
    listing: Listing,
    rules: list[TagRule] | None = None,
    profile_names: dict[str, str] | None = None,
) -> bool:
    """
    Run all enabled TagRules + system tags against listing. Updates listing.tags.
    Returns True if tags changed.
    Pass rules/profile_names to avoid re-querying DB per listing when bulk-tagging.
    """
    if rules is None:
        rules = db.query(TagRule).filter(TagRule.enabled == True).all()
    if profile_names is None:
        profiles = db.query(SearchProfile).all()
        profile_names = {str(p.id): p.name for p in profiles}

    text = _text_for_listing(listing)
    new_tags: list[str] = []

    for rule in rules:
        tag = rule.name
        kws = [k.lower() for k in (rule.keywords or [])]
        rkws = [k.lower() for k in (rule.reject_keywords or [])]

        positive = any(_keyword_matches(k, text) for k in kws) if kws else False
        negative = any(_keyword_matches(k, text) for k in rkws) if rkws else False

        if negative:
            new_tags.append(f"-{tag}")
        elif positive:
            new_tags.append(f"+{tag}")

    # System tags — always recomputed and stored
    new_tags.extend(_badge_tags(listing))
    new_tags.extend(_profile_tags(listing, profile_names))

    current = list(listing.tags or [])
    if sorted(new_tags) != sorted(current):
        db.add(ListingEvent(
            listing_id=listing.id,
            event_type="tags_updated",
            old_value={"tags": current},
            new_value={"tags": new_tags},
        ))
        listing.tags = new_tags
        flag_modified(listing, "tags")
        return True
    return False


def retag_all_listings(db: Session) -> int:
    """Re-apply all TagRules to every non-archived listing. Returns count updated."""
    rules = db.query(TagRule).filter(TagRule.enabled == True).all()
    for rule in rules:
        db.expunge(rule)
    profiles = db.query(SearchProfile).all()
    profile_names = {str(p.id): p.name for p in profiles}
    statuses = ["NEW", "ACTIVE", "REAPPEARED", "CHECKING", "SAVED", "MISSING_ON_SEARCH"]
    listings = db.query(Listing).filter(Listing.status.in_(statuses)).all()
    updated = 0
    for listing in listings:
        if apply_tags(db, listing, rules=rules, profile_names=profile_names):
            updated += 1
    db.commit()
    logger.info("retag_all: updated %d / %d listings", updated, len(listings))
    return updated


def retag_all_tracked() -> None:
    """Re-apply all TagRules and track progress as a ScanRun in Activity."""
    from ..database import SessionLocal
    db = SessionLocal()
    run = ScanRun(
        started_at=_utcnow(), status="running", job_type="retag_all",
        listings_found=0, new_listings=0, updated_listings=0, gone_listings=0,
    )
    db.add(run)
    db.commit()
    try:
        rules = db.query(TagRule).filter(TagRule.enabled == True).all()
        for rule in rules:
            db.expunge(rule)
        profiles = db.query(SearchProfile).all()
        profile_names = {str(p.id): p.name for p in profiles}
        statuses = ["NEW", "ACTIVE", "REAPPEARED", "CHECKING", "SAVED", "MISSING_ON_SEARCH"]
        listings = db.query(Listing).filter(Listing.status.in_(statuses)).all()
        run.listings_found = len(listings)
        db.commit()  # safe: rules are expunged, won't be expired

        updated = 0
        for listing in listings:
            if apply_tags(db, listing, rules=rules, profile_names=profile_names):
                updated += 1
        db.commit()

        run.new_listings = updated       # reuse new_listings field as "tags updated"
        run.status = "success"
        run.finished_at = _utcnow()
        db.commit()
        logger.info("retag_all: updated %d / %d listings", updated, len(listings))
    except Exception as exc:
        run.status = "failed"
        run.finished_at = _utcnow()
        run.errors = {"error": str(exc)}
        db.commit()
        logger.exception("retag_all failed: %s", exc)
    finally:
        db.close()
