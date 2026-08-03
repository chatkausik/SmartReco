"""Shared "Your Signal" chip mapping — turns behavioral events into {k, v} display chips.

Used by BOTH the per-user Your Signal panel (pages._recent_signals, scoped to the logged-in
user) and the admin live-signals dashboard (admin_signals, all users). Keeping the mapping in
one place means both views label identical events identically.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.product import Product


def titles_for(db: Session, events: list[Event]) -> dict[int, str]:
    """Batch-load {product_id: title} for the product-scoped events in the list."""
    ids = {e.product_id for e in events if e.product_id}
    if not ids:
        return {}
    return {p.id: p.title for p in db.query(Product).filter(Product.id.in_(ids)).all()}


def event_to_chip(event: Event, titles: dict[int, str]) -> dict | None:
    """Map one event to a Your-Signal chip, or None if it isn't a surfaced interaction."""
    p = event.payload or {}
    title = titles.get(event.product_id)
    if event.event_type == "product_view":
        return {"k": "Viewed", "v": p.get("title") or title or f"course #{event.product_id}"}
    if event.event_type == "click" and p.get("label") == "add_to_cart":
        return {"k": "Added to cart", "v": p.get("title") or title or "a course"}
    if event.event_type == "click" and p.get("label") == "remove_from_cart":
        return {"k": "Removed from cart", "v": p.get("title") or title or "a course"}
    if event.event_type == "search" and p.get("query") and not p.get("partial"):
        return {"k": "Searched", "v": f"“{p['query']}”"}
    return None


def events_to_chips(events: list[Event], titles: dict[int, str], limit: int = 10) -> list[dict]:
    """Newest-first events -> chips, dropping noise and consecutive duplicates."""
    chips: list[dict] = []
    for e in events:
        chip = event_to_chip(e, titles)
        if not chip:
            continue
        if chips and chips[-1] == chip:  # skip consecutive duplicates
            continue
        chips.append(chip)
        if len(chips) >= limit:
            break
    return chips
