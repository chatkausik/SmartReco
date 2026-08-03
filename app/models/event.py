from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_user_created", "user_id", "created_at"),
        Index("ix_events_user_type", "user_id", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # nullable = anonymous
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # event-type-specific extras
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    client_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="events")
