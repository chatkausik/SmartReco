from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)  # also used as the Chroma document id (str(id))
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. beginner/intermediate/advanced

    # Cosmetic catalog metadata shown on cards/detail (not used by the recommendation logic).
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    students: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # soft-delete flag

    # "synced" | "pending" | "failed" — drives the reconciliation script/job.
    vector_sync_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def embedding_text(self) -> str:
        """The text that gets embedded for semantic search — not the same as Chroma metadata."""
        return f"{self.title}\n\nCategory: {self.category}\n\n{self.description}"

    _STOPWORDS = {"with", "for", "and", "the", "to", "of", "a", "in", "on", "your", "you"}

    @property
    def monogram(self) -> str:
        """3-letter monogram from significant title words, e.g. 'Agentic Workflows with LangGraph' -> AWL."""
        words = [w for w in self.title.split() if w.lower() not in self._STOPWORDS]
        letters = "".join(w[0] for w in words if w[0].isalnum())[:3]
        return (letters or self.title[:3]).upper()

    @property
    def hue(self) -> int:
        """Deterministic hue (degrees) for the thumbnail gradient, derived from the id."""
        return (int(self.id) * 47) % 360

