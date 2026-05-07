import uuid
from datetime import datetime
from sqlalchemy import Integer, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .listing import Base, utcnow, Listing


class CommuteAnchor(Base):
    __tablename__ = "commute_anchors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    commute_results: Mapped[list["CommuteResult"]] = relationship("CommuteResult", back_populates="anchor")


class CommuteResult(Base):
    __tablename__ = "commute_results"
    __table_args__ = (UniqueConstraint("listing_id", "anchor_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id"), index=True)
    anchor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commute_anchors.id"), index=True)
    walk_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    listing: Mapped["Listing"] = relationship("Listing", back_populates="commute_results")
    anchor: Mapped["CommuteAnchor"] = relationship("CommuteAnchor", back_populates="commute_results")
