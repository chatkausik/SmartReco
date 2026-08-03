"""Node: LLM-based reranking of the metadata-filtered candidates (retrieval polish bonus).

An LLM scores each candidate for relevance to the learner's interest, and we reorder and
keep the top-K. Chosen over a separate cross-encoder model to avoid an extra heavy dependency
while still improving on raw cosine ordering.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.agent.llm import get_chat
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

TOP_K = 5


class ScoredItem(BaseModel):
    product_id: int
    score: float = Field(description="Relevance 0-10 for this learner.")


class RerankResult(BaseModel):
    ranked: list[ScoredItem]


def rerank(state: AgentState) -> AgentState:
    candidates = state.get("candidates", [])
    if len(candidates) <= 1:
        return {**state, "reranked": candidates}

    interest = state.get("interest_summary", "")
    by_id = {c["product_id"]: c for c in candidates}
    listing = "\n".join(
        f"- id={c['product_id']} | {c['metadata'].get('title')} | {c['metadata'].get('category')} | "
        f"{c['metadata'].get('level') or 'all levels'}"
        for c in candidates
    )
    try:
        llm = get_chat(temperature=0).with_structured_output(RerankResult)
        result: RerankResult = llm.invoke(
            f"Learner interest: {interest}\n\n"
            f"Score each candidate course 0-10 for how well it fits this learner, and return them.\n"
            f"Candidates:\n{listing}"
        )
        ordered = sorted(result.ranked, key=lambda s: s.score, reverse=True)
        reranked = [by_id[s.product_id] for s in ordered if s.product_id in by_id]
        # Append any candidate the model omitted, preserving original order, so we never lose items.
        seen = {s.product_id for s in ordered}
        reranked += [c for c in candidates if c["product_id"] not in seen]
    except Exception:
        logger.exception("rerank failed; falling back to similarity order")
        reranked = candidates

    return {**state, "reranked": reranked[:TOP_K]}
