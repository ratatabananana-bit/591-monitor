import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CommuteResultOut(BaseModel):
    anchor_id: uuid.UUID
    anchor_name: str = ""
    walk_minutes: Optional[int] = None
    transit_minutes: Optional[int] = None
    distance_meters: Optional[int] = None

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: uuid.UUID
    listing_id: str
    url: str
    title: Optional[str] = None
    price: Optional[int] = None
    district: Optional[str] = None
    address: Optional[str] = None
    size_ping: Optional[float] = None
    room_type: Optional[str] = None
    floor: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    status: str
    score: Optional[float] = None
    first_seen_at: datetime
    last_seen_at: datetime
    commute_results: list[CommuteResultOut] = []

    model_config = {"from_attributes": True}


class ListingAction(BaseModel):
    action: str


class ListingEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}
