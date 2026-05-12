import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CommuteAnchorCreate(BaseModel):
    name: str
    address: str
    weight: float = 1.0
    enabled: bool = True


class CommuteAnchorUpdate(CommuteAnchorCreate):
    pass


class CommuteAnchorOut(CommuteAnchorCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
