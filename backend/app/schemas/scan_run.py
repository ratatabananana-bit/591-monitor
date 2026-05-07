import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ScanRunOut(BaseModel):
    id: uuid.UUID
    profile_id: Optional[uuid.UUID] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    listings_found: int
    new_listings: int
    errors: Optional[dict] = None
    status: str

    model_config = {"from_attributes": True}
