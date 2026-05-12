import uuid
from datetime import datetime
from pydantic import BaseModel


class TagRuleOut(BaseModel):
    id: uuid.UUID
    name: str
    keywords: list[str] = []
    reject_keywords: list[str] = []
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TagRuleIn(BaseModel):
    name: str
    keywords: list[str] = []
    reject_keywords: list[str] = []
    enabled: bool = True
