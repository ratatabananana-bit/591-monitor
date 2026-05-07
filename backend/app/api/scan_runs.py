import uuid
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ScanRun, SearchProfile
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
