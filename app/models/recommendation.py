from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Recommendation(Base):
    """One row per user, updated in place — a deliberate simplification over a history table."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True, nullable=False)

    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    product_ids: Mapped[list] = mapped_column(JSON, default=list)  # grounded ids only, never free-text names
    retrieval_debug: Mapped[dict] = mapped_column(JSON, default=dict)  # query/filters/scores audit trail

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    event_count_at_generation: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ready")  # "ready" | "generating" | "stale"

    user = relationship("User", back_populates="recommendation")
