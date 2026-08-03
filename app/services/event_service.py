"""Event storage + read helpers. Writes are bulk (single INSERT), reads are indexed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import Event

# Only these types are accepted from the client; anything else is dropped defensively.
ALLOWED_EVENT_TYPES = {
    "page_view",
    "product_view",
    "search",
    "click",
    "time_spent",
    "add_to_cart",
    "recommendation_view",
}


def bulk_insert_events(db: Session, user_id: int | None, events: list[dict]) -> int:
    """Insert a batch of events in a single statement. Returns number stored."""
    rows = []
    for e in events:
        etype = e.get("event_type")
        if etype not in ALLOWED_EVENT_TYPES:
            continue
        rows.append(
            {
                "user_id": user_id,
                "event_type": etype,
                "product_id": e.get("product_id"),
                "payload": e.get("payload") or {},
                "session_id": e.get("session_id"),
                "client_ts": e.get("client_ts"),
            }
        )
    if not rows:
        return 0
    db.execute(Event.__table__.insert(), rows)
    db.commit()
    return len(rows)


def count_events_for_user(db: Session, user_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Event).where(Event.user_id == user_id)) or 0


def get_recent_events_for_user(db: Session, user_id: int, limit: int = 50, days: int | None = None) -> list[Event]:
    stmt = select(Event).where(Event.user_id == user_id)
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(Event.created_at >= cutoff)
    stmt = stmt.order_by(Event.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def user_ids_active_since(db: Session, since: datetime) -> list[int]:
    """Distinct non-anonymous user ids with at least one event since `since` (for the digest job)."""
    rows = db.execute(
        select(Event.user_id)
        .where(Event.user_id.is_not(None), Event.created_at >= since)
        .distinct()
    ).all()
    return [r[0] for r in rows]
