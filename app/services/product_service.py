"""Product write path with dual-write to SQL (source of truth) + Chroma (derived index).

Consistency model (hackathon-pragmatic, documented tradeoff):
  1. Write SQL first and commit.
  2. Then attempt the Chroma write. On failure, log it and mark the row
     vector_sync_status="failed" instead of rolling back the SQL write — SQL is the
     source of truth; the vector index is derived and can be reconciled later.
  3. scripts/reconcile_vector_store.py (and a periodic scheduler job) retries anything
     left "failed"/"pending".

Admin routes must call these functions and never touch the Product model or Chroma directly.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.services import vector_store

logger = logging.getLogger(__name__)


def list_products(db: Session, include_inactive: bool = False) -> list[Product]:
    stmt = select(Product).order_by(Product.created_at.desc())
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    return list(db.scalars(stmt).all())


def get_product(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def create_product(db: Session, data: dict) -> Product:
    product = Product(
        title=data["title"],
        description=data.get("description", ""),
        category=data["category"],
        price=data.get("price", 0),
        level=data.get("level"),
        is_active=data.get("is_active", True),
        vector_sync_status="pending",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    _sync_to_vector_store(db, product, delete=False)
    return product


def update_product(db: Session, product_id: int, data: dict) -> Product | None:
    product = db.get(Product, product_id)
    if product is None:
        return None
    for field in ("title", "description", "category", "price", "level", "is_active"):
        if field in data and data[field] is not None:
            setattr(product, field, data[field])
    product.vector_sync_status = "pending"
    db.commit()
    db.refresh(product)
    # If it became inactive, _sync deletes it from the vector store; otherwise upserts.
    _sync_to_vector_store(db, product, delete=not product.is_active)
    return product


def delete_product(db: Session, product_id: int) -> bool:
    """Soft delete: keeps FKs from events/recommendations valid, removes from vector store."""
    product = db.get(Product, product_id)
    if product is None:
        return False
    product.is_active = False
    product.vector_sync_status = "pending"
    db.commit()
    _sync_to_vector_store(db, product, delete=True)
    return True


def _sync_to_vector_store(db: Session, product: Product, delete: bool) -> None:
    try:
        if delete:
            vector_store.delete_product(product.id)
        else:
            vector_store.upsert_product(product)
        product.vector_sync_status = "synced"
    except Exception:  # noqa: BLE001 — deliberately catch-all; SQL already committed.
        logger.exception("Vector store sync failed for product %s; flagged for reconciliation", product.id)
        product.vector_sync_status = "failed"
    db.commit()
