import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .api.router import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .api.logs import setup_log_buffer
setup_log_buffer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Mark any runs that were still "running" or "cancelling" at startup as failed
    # (they were killed by a container restart)
    from .database import SessionLocal
    from .models import ScanRun
    from .services.pipeline import utcnow
    db = SessionLocal()
    try:
        stale = db.query(ScanRun).filter(ScanRun.status.in_(["running", "cancelling"])).all()
        for run in stale:
            run.status = "failed"
            run.finished_at = utcnow()
            run.errors = {"error": "Process killed (server restart)"}
        if stale:
            db.commit()
            logger.info("Marked %d stale run(s) as failed on startup", len(stale))
    finally:
        db.close()
    yield


app = FastAPI(title="591 Rental Monitor", version="1.0.0", lifespan=lifespan)
app.include_router(router, prefix="/api")

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(
            str(static_dir / "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
