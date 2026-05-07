import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SearchProfile
from ..schemas import SearchProfileCreate, SearchProfileUpdate, SearchProfileOut

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
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.commit()
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
