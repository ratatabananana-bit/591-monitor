import uuid
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ScanRun, SearchProfile, TelegramAlertedListing
from ..schemas import ScanRunOut

router = APIRouter(prefix="/scan-runs", tags=["scan-runs"])


@router.get("", response_model=list[ScanRunOut])
def list_scan_runs(limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(ScanRun)
        .order_by(ScanRun.started_at.desc())
        .limit(limit)
        .all()
    )


@router.post("/trigger")
def trigger_scan(
    background_tasks: BackgroundTasks,
    profile_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    from ..services.pipeline import run_scan_for_profile

    q = db.query(SearchProfile).filter(SearchProfile.enabled == True)
    if profile_id:
        q = q.filter(SearchProfile.id == profile_id)
    profiles = q.all()
    for profile in profiles:
        background_tasks.add_task(run_scan_for_profile, profile.id)
    return {
        "triggered": len(profiles),
        "profile_ids": [str(p.id) for p in profiles],
    }


@router.post("/recalculate-commutes")
def recalculate_commutes(background_tasks: BackgroundTasks):
    from ..services.pipeline import recalculate_all_commutes

    background_tasks.add_task(recalculate_all_commutes)
    return {"status": "queued"}


@router.post("/backfill-dates")
def backfill_dates(background_tasks: BackgroundTasks):
    from ..services.pipeline import backfill_posted_dates

    background_tasks.add_task(backfill_posted_dates)
    return {"status": "queued"}


@router.post("/backfill-page-text")
def backfill_page_text(background_tasks: BackgroundTasks):
    from ..services.pipeline import backfill_page_text as _backfill_page_text

    background_tasks.add_task(_backfill_page_text)
    return {"status": "queued"}


@router.post("/rescore")
def rescore_all(background_tasks: BackgroundTasks):
    from ..services.pipeline import rescore_all_listings

    background_tasks.add_task(rescore_all_listings)
    return {"status": "queued"}


@router.delete("/done")
def delete_done_runs(db: Session = Depends(get_db)):
    """Delete all finished (success/failed/cancelled) scan runs."""
    deleted = (
        db.query(ScanRun)
        .filter(ScanRun.status.in_(["success", "partial", "failed", "cancelled"]))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deleted": deleted}


@router.delete("/alerted")
def clear_alerted(db: Session = Depends(get_db)):
    """Wipe all TelegramAlertedListing records so all eligible listings will re-alert."""
    deleted = db.query(TelegramAlertedListing).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


@router.post("/{run_id}/cancel")
def cancel_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    from ..services.pipeline import request_cancel

    run = db.query(ScanRun).filter(ScanRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in ("running", "cancelling"):
        request_cancel(str(run_id))
        # For scan jobs, request_cancel already wrote "cancelled" to DB.
        # For thread jobs, status stays "cancelling" until the thread checks the event.
        db.expire(run)
        db.refresh(run)
    return {"status": run.status}
