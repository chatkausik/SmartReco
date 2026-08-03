"""Node: write the persuasive narrative + pick the final products.

The LLM is given ONLY the real retrieved candidates as grounding context, and any product
id it returns is validated against that candidate set — so recommendations can never be
fabricated. If generation fails, we fall back to the top candidates with a templated blurb.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.agent.llm import get_chat
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

MAX_RECOMMENDATIONS = 4


class Recommendation(BaseModel):
    narrative: str = Field(description="A short, warm, persuasive paragraph (2-4 sentences) speaking directly to the learner about why these courses fit their journey.")
    product_ids: list[int] = Field(description="The ids of the recommended products, most relevant first.")


def _candidate_block(candidates: list[dict]) -> str:
    lines = []
    for c in candidates:
        m = c.get("metadata", {})
        lines.append(
            f"- id={c['product_id']} | {m.get('title')} | {m.get('category')} | "
            f"${m.get('price')} | {m.get('level') or 'all levels'}"
        )
    return "\n".join(lines)


def generate_copy(state: AgentState) -> AgentState:
    # Prefer the reranked shortlist if present (Phase 6); otherwise use raw candidates.
    pool = state.get("reranked") or state.get("candidates", [])
    pool = pool[:MAX_RECOMMENDATIONS]
    valid_ids = {c["product_id"] for c in pool}

    if not pool:
        return {
            **state,
            "narrative": "We're still getting to know your interests — explore a few courses and we'll tailor picks for you.",
            "recommended_product_ids": [],
        }

    interest = state.get("interest_summary", "a curious learner")
    llm = get_chat(temperature=0.6).with_structured_output(Recommendation)
    try:
        result: Recommendation = llm.invoke(
            "You are a friendly learning advisor writing a personalized course recommendation.\n"
            f"The learner's interests: {interest}\n\n"
            "Recommend from ONLY these real catalog courses (do not invent any):\n"
            f"{_candidate_block(pool)}\n\n"
            "Write a persuasive narrative that connects these specific courses to the learner's "
            "interests, and return the product ids you recommend (most relevant first)."
        )
        # Ground the output: drop any hallucinated id not in the candidate pool.
        ids = [pid for pid in result.product_ids if pid in valid_ids]
        if not ids:
            ids = [c["product_id"] for c in pool]
        narrative = result.narrative
    except Exception:
        logger.exception("generate_copy LLM call failed; using templated fallback")
        ids = [c["product_id"] for c in pool]
        titles = ", ".join(c["metadata"].get("title", "") for c in pool)
        narrative = f"Based on what you've been exploring, these look like a strong fit: {titles}."

    return {**state, "narrative": narrative, "recommended_product_ids": ids}
