import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, exists
from ..database import get_db
from ..models import Listing, ListingEvent, CommuteAnchor, CommuteResult
from ..schemas import ListingOut, ListingAction, ListingEventOut, CommuteResultOut

router = APIRouter(prefix="/listings", tags=["listings"])

VALID_ACTIONS = {
    "save": "SAVED",
    "watch": "WATCHED",
    "reject": "REJECTED",
    "contacted": "CONTACTED",
    "visited": "VISITED",
}
SORT_FIELDS = {
    "score": Listing.score,
    "price": Listing.price,
    "first_seen_at": Listing.first_seen_at,
    "last_seen_at": Listing.last_seen_at,
}


def _serialize_listing(listing: Listing) -> dict:
    """Serialize listing with commute anchor names."""
    commute_out = [
        CommuteResultOut(
            anchor_id=cr.anchor_id,
            anchor_name=cr.anchor.name if cr.anchor else "Unknown",
            walk_minutes=cr.walk_minutes,
            transit_minutes=cr.transit_minutes,
            distance_meters=cr.distance_meters,
        ).model_dump()
        for cr in listing.commute_results
    ]
    data = ListingOut.model_validate(listing).model_dump()
    data["commute_results"] = commute_out
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
        q = q.filter(Listing.status == status)
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
    q = q.order_by(desc(sort_col) if sort_dir == "desc" else asc(sort_col))

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_listing(i) for i in items],
    }


@router.get("/{listing_id}")
def get_listing(listing_id: uuid.UUID, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _serialize_listing(listing)


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
    old_status = listing.status
    listing.status = VALID_ACTIONS[action.action]
    event = ListingEvent(
        listing_id=listing.id,
        event_type="status_change",
        old_value={"status": old_status},
        new_value={"status": listing.status},
    )
    db.add(event)
    db.commit()
    db.refresh(listing)
    return _serialize_listing(listing)


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
