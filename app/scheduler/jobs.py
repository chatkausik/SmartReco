"""Background jobs (APScheduler).

- daily_digest_job: for each user active today, refresh their recommendation via the SAME
  code path as the web route (recommendation_service.get_or_generate_recommendation — no
  duplicate generation), then email a persuasive digest. The "today's activity" recap is a
  cheap templated summary of events, not a second LLM call.
- reconcile_job: retries any product whose dual-write to the vector store failed.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.db import SessionLocal
from app.models.product import Product
from app.models.user import User
from app.services import email_service, event_service, recommendation_service

logger = logging.getLogger(__name__)


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _activity_recap(events: list, product_titles: dict[int, str] | None = None) -> str:
    """A short, cheap (non-LLM) recap of today's behavior for the email.

    product_titles maps product_id -> title so product_view events (whose payload doesn't
    carry a title) can still be named in the recap.
    """
    product_titles = product_titles or {}
    searches = [e.payload.get("query") for e in events if e.event_type == "search" and e.payload.get("query")]
    viewed = [
        (e.payload.get("title") or product_titles.get(e.product_id))
        for e in events
        if e.event_type == "product_view"
    ]
    viewed = [t for t in viewed if t]
    parts = []
    if searches:
        top = [q for q, _ in Counter(searches).most_common(3)]
        parts.append("searched for " + ", ".join(f"“{q}”" for q in top))
    if viewed:
        top = [t for t, _ in Counter(viewed).most_common(3)]
        parts.append("looked at " + ", ".join(top))
    if not parts:
        return "You explored the catalog today."
    return "Today you " + " and ".join(parts) + "."


def daily_digest_job() -> None:
    db = SessionLocal()
    sent, logged = 0, 0
    try:
        user_ids = event_service.user_ids_active_since(db, _today_start())
        logger.info("daily_digest_job: %d active users today", len(user_ids))
        for uid in user_ids:
            user = db.get(User, uid)
            if not user:
                continue
            rec = recommendation_service.get_or_generate_recommendation(db, user)
            if not rec:
                continue
            products = recommendation_service.get_recommended_products(db, rec)
            todays_events = [
                e for e in event_service.get_recent_events_for_user(db, uid, limit=200)
                if e.created_at and _aware(e.created_at) >= _today_start()
            ]
            viewed_ids = {e.product_id for e in todays_events if e.event_type == "product_view" and e.product_id}
            titles = (
                {p.id: p.title for p in db.query(Product).filter(Product.id.in_(viewed_ids)).all()}
                if viewed_ids
                else {}
            )
            recap = _activity_recap(todays_events, titles)
            if email_service.send_digest_email(user, rec, products, recap):
                sent += 1
            else:
                logged += 1
        logger.info("daily_digest_job done: %d emailed, %d console-logged", sent, logged)
    except Exception:
        logger.exception("daily_digest_job failed")
    finally:
        db.close()


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def reconcile_job() -> None:
    from scripts.reconcile_vector_store import reconcile

    summary = reconcile()
    if summary["checked"]:
        logger.info("reconcile_job: %s", summary)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")

    # Daily afternoon digest.
    scheduler.add_job(
        daily_digest_job,
        CronTrigger(hour=settings.digest_hour, minute=settings.digest_minute),
        id="daily_digest",
        misfire_grace_time=3600,
        replace_existing=True,
    )
    # Optional dev-mode interval so the digest can be demoed without waiting for the cron slot.
    if settings.digest_dev_interval_minutes:
        scheduler.add_job(
            daily_digest_job,
            IntervalTrigger(minutes=settings.digest_dev_interval_minutes),
            id="daily_digest_dev",
            replace_existing=True,
        )
        logger.info("Digest dev-interval enabled: every %s min", settings.digest_dev_interval_minutes)

    # Periodic vector-store reconciliation (self-healing dual-write).
    scheduler.add_job(
        reconcile_job, IntervalTrigger(minutes=30), id="reconcile", replace_existing=True
    )
    return scheduler
