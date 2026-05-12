import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .listing import Base, utcnow


class TelegramSubscription(Base):
    __tablename__ = "telegram_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chat_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    chat_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subscribed_tags: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    alerted_listings: Mapped[list["TelegramAlertedListing"]] = relationship(
        "TelegramAlertedListing", back_populates="subscription", cascade="all, delete-orphan"
    )


class TelegramAlertedListing(Base):
    __tablename__ = "telegram_alerted_listings"
    __table_args__ = (UniqueConstraint("subscription_id", "listing_id", name="uq_sub_listing"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("telegram_subscriptions.id", ondelete="CASCADE"))
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    alerted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    alert_type: Mapped[str] = mapped_column(String(30), default="new")

    subscription: Mapped["TelegramSubscription"] = relationship("TelegramSubscription", back_populates="alerted_listings")
