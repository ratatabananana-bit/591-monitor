import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .listing import Base, utcnow


class TagRule(Base):
    __tablename__ = "tag_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))          # tag label, e.g. "pet-ok"
    keywords: Mapped[list] = mapped_column(JSON, default=list)          # any match → +name
    reject_keywords: Mapped[list] = mapped_column(JSON, default=list)   # any match → -name
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
