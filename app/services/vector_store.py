"""Chroma vector store wrapper. Embeddings are always computed via Mesh (mesh_client),
never Chroma's built-in embedding function — every embedding call must go through Mesh.

The Chroma document id is str(product.id), so the SQL row and the vector entry always
correspond 1:1 with no separate mapping table.
"""
from __future__ import annotations

import logging

import chromadb

from app.config import settings
from app.models.product import Product
from app.services import mesh_client

logger = logging.getLogger(__name__)

COLLECTION_NAME = "products"

_client: chromadb.ClientAPI | None = None
_collection = None


def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.chroma_dir)
        # embedding_function=None: we pass embeddings explicitly (computed via Mesh).
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=None, metadata={"hnsw:space": "cosine"}
        )
    return _collection


def _metadata(product: Product) -> dict:
    return {
        "sql_id": product.id,
        "title": product.title,
        "category": product.category,
        "price": float(product.price),
        "level": product.level or "",
        "is_active": bool(product.is_active),
    }


def upsert_product(product: Product) -> None:
    """Embed the product's text via Mesh and upsert into Chroma (idempotent by id).

    Used for both create and update. A soft-deleted product is removed from the vector
    store instead so retrieval never surfaces it.
    """
    if not product.is_active:
        delete_product(product.id)
        return
    embedding = mesh_client.embed_text(product.embedding_text(), purpose="product embed (dual-write)")
    get_collection().upsert(
        ids=[str(product.id)],
        embeddings=[embedding],
        documents=[product.embedding_text()],
        metadatas=[_metadata(product)],
    )


def delete_product(product_id: int) -> None:
    get_collection().delete(ids=[str(product_id)])


def query(query_embedding: list[float], n_results: int = 10, where: dict | None = None) -> list[dict]:
    """Semantic search. `where` applies Chroma metadata filtering (category/price/etc.)."""
    res = get_collection().query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where or None,
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict] = []
    ids = res.get("ids", [[]])[0]
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for i, doc_id in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        dist = dists[i] if i < len(dists) else None
        hits.append(
            {
                "product_id": int(meta.get("sql_id", doc_id)),
                "document": docs[i] if i < len(docs) else "",
                "metadata": meta,
                "distance": dist,
                # cosine distance -> similarity for readability in debug/grading
                "similarity": (1.0 - dist) if dist is not None else None,
            }
        )
    return hits


def get_ids() -> set[str]:
    """All document ids currently in the collection (used by the reconciliation script)."""
    res = get_collection().get(include=[])
    return set(res.get("ids", []))


def count() -> int:
    return get_collection().count()
