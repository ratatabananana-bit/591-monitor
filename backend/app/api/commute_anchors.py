import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import CommuteAnchor
from ..schemas import CommuteAnchorCreate, CommuteAnchorUpdate, CommuteAnchorOut

router = APIRouter(prefix="/commute-anchors", tags=["commute-anchors"])


@router.get("", response_model=list[CommuteAnchorOut])
def list_anchors(db: Session = Depends(get_db)):
    return db.query(CommuteAnchor).order_by(CommuteAnchor.created_at).all()


@router.post("", response_model=CommuteAnchorOut)
def create_anchor(data: CommuteAnchorCreate, db: Session = Depends(get_db)):
    anchor = CommuteAnchor(**data.model_dump())
    db.add(anchor)
    db.commit()
    db.refresh(anchor)
    return anchor


@router.get("/{anchor_id}", response_model=CommuteAnchorOut)
def get_anchor(anchor_id: uuid.UUID, db: Session = Depends(get_db)):
    anchor = db.query(CommuteAnchor).filter(CommuteAnchor.id == anchor_id).first()
    if not anchor:
        raise HTTPException(status_code=404, detail="Anchor not found")
    return anchor


@router.put("/{anchor_id}", response_model=CommuteAnchorOut)
def update_anchor(anchor_id: uuid.UUID, data: CommuteAnchorUpdate, db: Session = Depends(get_db)):
    anchor = db.query(CommuteAnchor).filter(CommuteAnchor.id == anchor_id).first()
    if not anchor:
        raise HTTPException(status_code=404, detail="Anchor not found")
    for key, value in data.model_dump().items():
        setattr(anchor, key, value)
    db.commit()
    db.refresh(anchor)
    return anchor


@router.delete("/{anchor_id}")
def delete_anchor(anchor_id: uuid.UUID, db: Session = Depends(get_db)):
    anchor = db.query(CommuteAnchor).filter(CommuteAnchor.id == anchor_id).first()
    if not anchor:
        raise HTTPException(status_code=404, detail="Anchor not found")
    db.delete(anchor)
    db.commit()
    return {"ok": True}
