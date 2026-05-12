from fastapi import APIRouter
from .search_profiles import router as profiles_router
from .commute_anchors import router as anchors_router
from .listings import router as listings_router
from .scan_runs import router as scan_runs_router
from .logs import router as logs_router
from .tag_rules import router as tag_rules_router

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


router.include_router(profiles_router)
router.include_router(anchors_router)
router.include_router(listings_router)
router.include_router(scan_runs_router)
router.include_router(logs_router)
router.include_router(tag_rules_router)
