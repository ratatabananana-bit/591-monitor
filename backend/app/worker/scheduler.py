import logging
import uuid
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from ..database import SessionLocal
from ..models import SearchProfile
from ..services.pipeline import run_scan_for_profile

logger = logging.getLogger(__name__)


def _scan_profile(profile_id_str: str) -> None:
    run_scan_for_profile(uuid.UUID(profile_id_str))


def reload_scheduler_jobs(scheduler: BackgroundScheduler) -> None:
    for job in scheduler.get_jobs():
        if job.id.startswith("profile_"):
            scheduler.remove_job(job.id)

    db = SessionLocal()
    try:
        profiles = db.query(SearchProfile).filter(SearchProfile.enabled == True).all()
        for profile in profiles:
            job_id = f"profile_{profile.id}"
            scheduler.add_job(
                _scan_profile,
                trigger=IntervalTrigger(minutes=profile.scan_interval_minutes),
                id=job_id,
                args=[str(profile.id)],
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info("Scheduled '%s' every %d min", profile.name, profile.scan_interval_minutes)
    finally:
        db.close()


def setup_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: reload_scheduler_jobs(scheduler),
        trigger=IntervalTrigger(minutes=5),
        id="reload_jobs",
        replace_existing=True,
    )
    reload_scheduler_jobs(scheduler)
    return scheduler
