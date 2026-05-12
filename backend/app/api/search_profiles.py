import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SearchProfile, Listing
from ..schemas import SearchProfileCreate, SearchProfileUpdate, SearchProfileOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search-profiles", tags=["search-profiles"])


@router.get("", response_model=list[SearchProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    return db.query(SearchProfile).order_by(SearchProfile.created_at.desc()).all()


@router.post("", response_model=SearchProfileOut)
def create_profile(data: SearchProfileCreate, db: Session = Depends(get_db)):
    profile = SearchProfile(**data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=SearchProfileOut)
def get_profile(profile_id: uuid.UUID, db: Session = Depends(get_db)):
    profile = db.query(SearchProfile).filter(SearchProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/{profile_id}", response_model=SearchProfileOut)
def update_profile(profile_id: uuid.UUID, data: SearchProfileUpdate, db: Session = Depends(get_db)):
    profile = db.query(SearchProfile).filter(SearchProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    old_required = set(profile.required_keywords or [])
    old_rejected = set(profile.rejected_keywords or [])

    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.commit()

    new_required = set(profile.required_keywords or [])
    new_rejected = set(profile.rejected_keywords or [])
    keywords_changed = (old_required != new_required) or (old_rejected != new_rejected)

    if keywords_changed:
        # Keywords changed — strip this profile from matched_profiles AND filtered_by_profiles
        # so next scan re-evaluates listings with the new keywords.
        # Only REJECTED (manual) listings are left alone.
        profile_id_str = str(profile_id)
        all_non_rejected = db.query(Listing).filter(Listing.status != "REJECTED").all()

        reset_count = 0
        for listing in all_non_rejected:
            changed = False
            m_profiles = list(listing.matched_profiles or [])
            fbp = list(listing.filtered_by_profiles or [])
            rbp = list(listing.rejected_by_profiles or [])
            if profile_id_str in m_profiles:
                m_profiles.remove(profile_id_str)
                listing.matched_profiles = m_profiles
                changed = True
            if profile_id_str in fbp:
                fbp.remove(profile_id_str)
                listing.filtered_by_profiles = fbp
                changed = True
            if profile_id_str in rbp:
                rbp.remove(profile_id_str)
                listing.rejected_by_profiles = rbp
                changed = True
            if changed:
                reset_count += 1
        db.commit()
        logger.info(
            "Profile %s keywords changed — cleared %d listings for re-evaluation",
            profile.name, reset_count,
        )

    db.refresh(profile)
    return profile


@router.delete("/{profile_id}")
def delete_profile(profile_id: uuid.UUID, db: Session = Depends(get_db)):
    profile = db.query(SearchProfile).filter(SearchProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()
    return {"ok": True}
