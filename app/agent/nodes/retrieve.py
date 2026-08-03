"""Node: embed the retrieval query via Mesh and run semantic search over Chroma,
applying metadata filters (category / price) — grounded retrieval, real catalog only.
"""
from __future__ import annotations

import logging

from app.agent.llm import get_embeddings
from app.agent.state import AgentState
from app.services import vector_store

logger = logging.getLogger(__name__)

N_RESULTS = 8


def _build_where(filters: dict) -> dict | None:
    """Translate agent filters into a Chroma `where` clause. Always excludes inactive products."""
    clauses: list[dict] = [{"is_active": True}]
    if filters.get("category"):
        clauses.append({"category": filters["category"]})
    if filters.get("price_max") is not None:
        clauses.append({"price": {"$lte": float(filters["price_max"])}})
    if filters.get("price_min") is not None:
        clauses.append({"price": {"$gte": float(filters["price_min"])}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def retrieve(state: AgentState) -> AgentState:
    query = state.get("retrieval_query") or "technology courses"
    filters = state.get("filters", {})
    try:
        embedding = get_embeddings().embed_query(query)
        candidates = vector_store.query(embedding, n_results=N_RESULTS, where=_build_where(filters))
        # Safety net: if a category/price filter over-narrowed to nothing, retry unfiltered
        # (excluding inactive only) so we always ground on real catalog items.
        if not candidates and filters:
            candidates = vector_store.query(embedding, n_results=N_RESULTS, where={"is_active": True})
    except Exception:
        logger.exception("retrieve failed for query=%r filters=%r", query, filters)
        candidates = []
    return {**state, "candidates": candidates}
