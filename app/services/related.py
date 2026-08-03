"""'Students who explored this also looked at' — grounded related products.

Primary signal: collaborative co-views from the events table (users who viewed X also
viewed Y). Fallback: semantic similarity over the vector store when co-view data is sparse.
Both are real and catalog-grounded — nothing fabricated.
"""
from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.product import Product
from app.services import mesh_client, vector_store

logger = logging.getLogger(__name__)


def related_products(db: Session, product_id: int, limit: int = 4) -> list[Product]:
    ordered_ids = _coview_ids(db, product_id, limit)
    if len(ordered_ids) < limit:
        ordered_ids += _similar_ids(db, product_id, limit, exclude=set(ordered_ids) | {product_id})

    ordered_ids = ordered_ids[:limit]
    if not ordered_ids:
        return []
    rows = {
        p.id: p
        for p in db.query(Product).filter(Product.id.in_(ordered_ids), Product.is_active.is_(True)).all()
    }
    return [rows[i] for i in ordered_ids if i in rows]


def _coview_ids(db: Session, product_id: int, limit: int) -> list[int]:
    """Product ids co-viewed by users/sessions that viewed `product_id`, ranked by frequency."""
    viewer_sessions = db.execute(
        select(Event.session_id)
        .where(Event.event_type == "product_view", Event.product_id == product_id,
               Event.session_id.is_not(None))
        .distinct()
    ).scalars().all()
    if not viewer_sessions:
        return []
    rows = db.execute(
        select(Event.product_id)
        .where(Event.event_type == "product_view", Event.session_id.in_(viewer_sessions),
               Event.product_id.is_not(None), Event.product_id != product_id)
    ).scalars().all()
    counts = Counter(rows)
    return [pid for pid, _ in counts.most_common(limit)]


def _similar_ids(db: Session, product_id: int, limit: int, exclude: set[int]) -> list[int]:
    """Semantic nearest neighbours from the vector store (fallback when co-views are sparse)."""
    product = db.get(Product, product_id)
    if product is None:
        return []
    try:
        embedding = mesh_client.embed_text(product.embedding_text(), purpose="related (similarity)")
        hits = vector_store.query(embedding, n_results=limit + len(exclude) + 1, where={"is_active": True})
    except Exception:
        logger.exception("related _similar_ids failed for product %s", product_id)
        return []
    out = []
    for h in hits:
        pid = h["product_id"]
        if pid not in exclude:
            out.append(pid)
        if len(out) >= limit:
            break
    return out
