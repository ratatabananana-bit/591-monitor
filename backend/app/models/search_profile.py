import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .listing import Base, utcnow


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    city: Mapped[str] = mapped_column(String(50), default="taipei")
    districts: Mapped[list] = mapped_column(JSON, default=list)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    room_types: Mapped[list] = mapped_column(JSON, default=list)
    required_keywords: Mapped[list] = mapped_column(JSON, default=list)
    rejected_keywords: Mapped[list] = mapped_column(JSON, default=list)
    scan_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
