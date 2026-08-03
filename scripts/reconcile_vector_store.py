"""Reconcile the Chroma vector store against SQL (the source of truth).

Retries the dual-write for any product left vector_sync_status in ('failed', 'pending').
Can be run manually or is registered as a periodic APScheduler job.

Usage: python -m scripts.reconcile_vector_store
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select

from app.db import SessionLocal
from app.models.product import Product
from app.services import vector_store

logger = logging.getLogger(__name__)


def reconcile() -> dict:
    """Returns a small summary dict: {fixed, failed, checked}."""
    db = SessionLocal()
    fixed, still_failed = 0, 0
    try:
        pending = db.scalars(
            select(Product).where(or_(Product.vector_sync_status == "failed", Product.vector_sync_status == "pending"))
        ).all()
        for product in pending:
            try:
                if product.is_active:
                    vector_store.upsert_product(product)
                else:
                    vector_store.delete_product(product.id)
                product.vector_sync_status = "synced"
                fixed += 1
            except Exception:  # noqa: BLE001
                logger.exception("Reconcile still failing for product %s", product.id)
                product.vector_sync_status = "failed"
                still_failed += 1
        db.commit()
        return {"fixed": fixed, "failed": still_failed, "checked": len(pending)}
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    summary = reconcile()
    print(f"Reconcile complete: {summary}")


if __name__ == "__main__":
    main()
