import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, exists
from ..database import get_db
from ..models import Listing, ListingEvent, CommuteAnchor, CommuteResult, SearchProfile
from ..schemas import ListingOut, ListingAction, ListingEventOut, CommuteResultOut


class BulkAction(BaseModel):
    ids: List[uuid.UUID]
    action: str

router = APIRouter(prefix="/listings", tags=["listings"])

VALID_ACTIONS = {
    "save": "SAVED",
    "checking": "CHECKING",
    "reject": "REJECTED",
}
SORT_FIELDS = {
    "score": Listing.score,
    "price": Listing.price,
    "posted_at": Listing.posted_at,
    "size_ping": Listing.size_ping,
    "first_seen_at": Listing.first_seen_at,
    "last_seen_at": Listing.last_seen_at,
}


def _build_profile_map(db: Session) -> dict[str, str]:
    profiles = db.query(SearchProfile.id, SearchProfile.name).all()
    return {str(p.id): p.name for p in profiles}


def _serialize_listing(listing: Listing, profile_map: dict[str, str] | None = None) -> dict:
    commute_out = [
        CommuteResultOut(
            anchor_id=cr.anchor_id,
            anchor_name=cr.anchor.name if cr.anchor else "Unknown",
            walk_minutes=cr.walk_minutes,
            transit_minutes=cr.transit_minutes,
            distance_meters=cr.distance_meters,
            scooter_minutes=cr.scooter_minutes,
            scooter_distance_meters=cr.scooter_distance_meters,
        ).model_dump()
        for cr in listing.commute_results
    ]
    data = ListingOut.model_validate(listing).model_dump()
    data["commute_results"] = commute_out
    pm = profile_map or {}
    data["matched_profile_names"] = [pm[pid] for pid in (listing.matched_profiles or []) if pid in pm]
    data["filtered_by_profile_names"] = [pm[pid] for pid in (listing.filtered_by_profiles or []) if pid in pm]
    data["rejected_by_profile_names"] = [pm[pid] for pid in (listing.rejected_by_profiles or []) if pid in pm]
    # Expose original price for price-change indicator in the UI
    raw_price = (listing.raw_data or {}).get("price")
    data["price_original"] = int(raw_price) if raw_price and raw_price != listing.price else None
    return data


@router.get("")
def list_listings(
    status: str | None = None,
    district: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    score_min: float | None = None,
    transit_max: int | None = None,
    keyword: str | None = None,
    first_seen_after: str | None = None,
    first_seen_before: str | None = None,
    sort_by: str = "score",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone
    q = db.query(Listing)
    if status:
        statuses = [s.strip() for s in status.split(',') if s.strip()]
        if len(statuses) == 1:
            q = q.filter(Listing.status == statuses[0])
        else:
            q = q.filter(Listing.status.in_(statuses))
    if district:
        q = q.filter(Listing.district == district)
    if price_min is not None:
        q = q.filter(Listing.price >= price_min)
    if price_max is not None:
        q = q.filter(Listing.price <= price_max)
    if score_min is not None:
        q = q.filter(Listing.score >= score_min)
    if first_seen_after:
        try:
            q = q.filter(Listing.first_seen_at >= datetime.fromisoformat(first_seen_after))
        except ValueError:
            pass
    if first_seen_before:
        try:
            q = q.filter(Listing.first_seen_at <= datetime.fromisoformat(first_seen_before))
        except ValueError:
            pass
    if transit_max is not None:
        from sqlalchemy import select as sa_select
        subq = sa_select(CommuteResult.listing_id).where(
            CommuteResult.transit_minutes <= transit_max
        )
        q = q.filter(Listing.id.in_(subq))
    if keyword:
        q = q.filter(
            Listing.title.ilike(f"%{keyword}%") | Listing.address.ilike(f"%{keyword}%")
        )

    sort_col = SORT_FIELDS.get(sort_by, Listing.score)
    sort_expr = desc(sort_col).nulls_last() if sort_dir == "desc" else asc(sort_col).nulls_last()
    q = q.order_by(sort_expr)

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    profile_map = _build_profile_map(db)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_listing(i, profile_map) for i in items],
    }


@router.get("/{listing_id}")
def get_listing(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _serialize_listing(listing, _build_profile_map(db))


@router.post("/{listing_id}/viewed")
def mark_viewed(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    """Called when user opens a listing drawer. Transitions NEW/REAPPEARED → ACTIVE only."""
    from ..services.tagger import apply_tags
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status in ("NEW", "REAPPEARED"):
        old_status = listing.status
        listing.status = "ACTIVE"
        db.add(ListingEvent(
            listing_id=listing.id,
            event_type="status_change",
            old_value={"status": old_status},
            new_value={"status": "ACTIVE"},
        ))
        apply_tags(db, listing)
        db.commit()
        db.refresh(listing)
    return _serialize_listing(listing, _build_profile_map(db))


@router.patch("/{listing_id}/action")
def listing_action(listing_id: uuid.UUID, action: ListingAction, db: Session = Depends(get_db)):
    if action.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action. Valid: {list(VALID_ACTIONS)}",
        )
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    from ..services.tagger import apply_tags
    old_status = listing.status
    listing.status = VALID_ACTIONS[action.action]
    db.add(ListingEvent(
        listing_id=listing.id,
        event_type="status_change",
        old_value={"status": old_status},
        new_value={"status": listing.status},
    ))
    apply_tags(db, listing)
    db.commit()
    db.refresh(listing)
    return _serialize_listing(listing, _build_profile_map(db))


@router.delete("/{listing_id}")
def delete_listing(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    db.query(ListingEvent).filter(ListingEvent.listing_id == listing_id).delete()
    db.query(CommuteResult).filter(CommuteResult.listing_id == listing_id).delete()
    db.delete(listing)
    db.commit()
    return {"ok": True}


@router.post("/bulk-action")
def bulk_listing_action(body: BulkAction, db: Session = Depends(get_db)):
    if body.action == "delete":
        deleted = 0
        for listing_id in body.ids:
            listing = db.query(Listing).filter(Listing.id == listing_id).first()
            if not listing:
                continue
            db.query(ListingEvent).filter(ListingEvent.listing_id == listing_id).delete()
            db.query(CommuteResult).filter(CommuteResult.listing_id == listing_id).delete()
            db.delete(listing)
            deleted += 1
        db.commit()
        return {"updated": deleted}

    if body.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action. Valid: {list(VALID_ACTIONS)} or delete",
        )
    from ..services.tagger import apply_tags
    new_status = VALID_ACTIONS[body.action]
    updated = 0
    for listing_id in body.ids:
        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing:
            continue
        old_status = listing.status
        listing.status = new_status
        db.add(ListingEvent(
            listing_id=listing.id,
            event_type="status_change",
            old_value={"status": old_status},
            new_value={"status": new_status},
        ))
        apply_tags(db, listing)
        updated += 1
    db.commit()
    return {"updated": updated}


@router.post("/{listing_id}/rescrape-photos")
def rescrape_photos(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    """Re-fetch image URLs for a single listing from 591 using Playwright."""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    from ..scraper.scraper_591 import scrape_listing_detail
    detail = scrape_listing_detail(listing.listing_id)

    if not detail:
        raise HTTPException(status_code=502, detail="Scrape failed — listing may be unavailable")

    if "image_urls" in detail:
        listing.image_urls = detail["image_urls"]
        if detail["image_urls"]:
            listing.thumbnail_url = detail["image_urls"][0]
        db.add(ListingEvent(
            listing_id=listing.id,
            event_type="photos_rescraped",
            new_value={"count": len(detail["image_urls"])},
        ))
        db.commit()
        db.refresh(listing)

    return _serialize_listing(listing, _build_profile_map(db))


@router.get("/{listing_id}/events", response_model=list[ListingEventOut])
def get_listing_events(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return (
        db.query(ListingEvent)
        .filter(ListingEvent.listing_id == listing_id)
        .order_by(ListingEvent.created_at.desc())
        .all()
    )
