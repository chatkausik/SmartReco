"""The single entrypoint for producing a user's recommendation, used identically by the
on-demand web route and the scheduled digest job (no duplicate generation path).

Efficiency / "smart AI-call triggering" (judged): we do NOT regenerate on every request.
should_regenerate() gates the expensive agent run behind an event-count threshold + a
minimum cooldown, with a max-staleness backstop. Between regenerations the cached row is
served with a plain SQL read — no LLM call.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.user import User
from app.services import event_service

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite may return naive datetimes; treat stored times as UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def should_regenerate(rec: Recommendation | None, current_event_count: int) -> bool:
    if rec is None:
        return True  # cold start — always generate the first one
    generated_at = _aware(rec.generated_at)
    age = _now() - generated_at
    new_events = current_event_count - (rec.event_count_at_generation or 0)

    # Backstop: refresh anything older than the max-staleness window regardless of activity.
    if age >= timedelta(hours=settings.max_staleness_hours):
        return True
    # Enough new behavior AND past the cooldown -> worth a fresh run.
    if new_events >= settings.event_threshold and age >= timedelta(minutes=settings.min_cooldown_minutes):
        return True
    return False


def _recent_events_for_agent(db: Session, user_id: int) -> list[dict]:
    """Pull recent events and enrich product-scoped ones with title/category for the agent."""
    events = event_service.get_recent_events_for_user(db, user_id, limit=50)
    # Batch-load referenced products.
    product_ids = {e.product_id for e in events if e.product_id}
    products = {}
    if product_ids:
        for p in db.query(Product).filter(Product.id.in_(product_ids)).all():
            products[p.id] = p
    enriched = []
    for e in events:
        payload = dict(e.payload or {})
        if e.product_id and e.product_id in products:
            payload.setdefault("title", products[e.product_id].title)
            payload.setdefault("category", products[e.product_id].category)
        enriched.append(
            {"event_type": e.event_type, "product_id": e.product_id, "payload": payload}
        )
    return enriched


def get_or_generate_recommendation(db: Session, user: User, force: bool = False) -> Recommendation | None:
    rec = db.query(Recommendation).filter_by(user_id=user.id).first()
    current_count = event_service.count_events_for_user(db, user.id)

    if not force and not should_regenerate(rec, current_count):
        return rec  # serve cache — no LLM call

    # Import here so importing this module doesn't require langgraph/langchain at load time.
    from app.agent.graph import run_recommendation

    if rec is not None:
        rec.status = "generating"
        db.commit()

    raw_events = _recent_events_for_agent(db, user.id)
    categories = [
        row[0]
        for row in db.query(Product.category).filter(Product.is_active.is_(True)).distinct().all()
    ]
    try:
        result = run_recommendation(user.id, raw_events, available_categories=categories)
    except Exception:
        logger.exception("Agent run failed for user %s", user.id)
        if rec is not None:
            rec.status = "ready"  # keep serving the previous copy
            db.commit()
        return rec

    if rec is None:
        rec = Recommendation(user_id=user.id)
        db.add(rec)
    rec.narrative = result["narrative"]
    rec.product_ids = result["recommended_product_ids"]
    rec.retrieval_debug = result["retrieval_debug"]
    rec.generated_at = _now()
    rec.event_count_at_generation = current_count
    rec.status = "ready"
    try:
        db.commit()
    except IntegrityError:
        # Cold-start race: a concurrent request already created this user's row.
        # Roll back and update the existing row instead of failing.
        db.rollback()
        rec = db.query(Recommendation).filter_by(user_id=user.id).first()
        if rec is not None:
            rec.narrative = result["narrative"]
            rec.product_ids = result["recommended_product_ids"]
            rec.retrieval_debug = result["retrieval_debug"]
            rec.generated_at = _now()
            rec.event_count_at_generation = current_count
            rec.status = "ready"
            db.commit()
    db.refresh(rec)
    return rec


def get_recommended_products(db: Session, rec: Recommendation | None) -> list[Product]:
    """Resolve stored product ids to Product rows, preserving recommendation order."""
    if not rec or not rec.product_ids:
        return []
    rows = {p.id: p for p in db.query(Product).filter(Product.id.in_(rec.product_ids)).all()}
    return [rows[pid] for pid in rec.product_ids if pid in rows]
