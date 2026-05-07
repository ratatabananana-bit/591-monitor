import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SearchProfileCreate(BaseModel):
    name: str
    enabled: bool = True
    city: str = "taipei"
    districts: list[str] = []
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    room_types: list[str] = []
    required_keywords: list[str] = []
    rejected_keywords: list[str] = []
    scan_interval_minutes: int = 30


class SearchProfileUpdate(SearchProfileCreate):
    pass


class SearchProfileOut(SearchProfileCreate):
    id: uuid.UUID
    last_scanned_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
