import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ScanRunOut(BaseModel):
    id: uuid.UUID
    profile_id: Optional[uuid.UUID] = None
    profile_name: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    listings_found: int
    new_listings: int
    updated_listings: int = 0
    gone_listings: int = 0
    errors: Optional[dict] = None
    status: str
    job_type: Optional[str] = "scan"

    model_config = {"from_attributes": True}
