import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import TagRule
from ..schemas.tag_rule import TagRuleOut, TagRuleIn

router = APIRouter(prefix="/tag-rules", tags=["tag-rules"])


@router.get("", response_model=list[TagRuleOut])
def list_tag_rules(db: Session = Depends(get_db)):
    return db.query(TagRule).order_by(TagRule.created_at).all()


@router.post("", response_model=TagRuleOut)
def create_tag_rule(body: TagRuleIn, db: Session = Depends(get_db)):
    rule = TagRule(
        name=body.name,
        keywords=body.keywords,
        reject_keywords=body.reject_keywords,
        enabled=body.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=TagRuleOut)
def update_tag_rule(rule_id: uuid.UUID, body: TagRuleIn, db: Session = Depends(get_db)):
    rule = db.query(TagRule).filter(TagRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Tag rule not found")
    rule.name = body.name
    rule.keywords = body.keywords
    rule.reject_keywords = body.reject_keywords
    rule.enabled = body.enabled
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_tag_rule(rule_id: uuid.UUID, db: Session = Depends(get_db)):
    rule = db.query(TagRule).filter(TagRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Tag rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}


@router.post("/retag-all")
def retag_all(background_tasks: BackgroundTasks):
    """Re-apply all enabled TagRules to every listing in the background."""
    from ..services.tagger import retag_all_tracked
    background_tasks.add_task(retag_all_tracked)
    return {"status": "queued"}
