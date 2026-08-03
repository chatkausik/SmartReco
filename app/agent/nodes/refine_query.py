"""Node: when retrieval was weak, broaden/rewrite the query and drop over-narrow filters,
then loop back to retrieve. refine_count guards against infinite loops.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.agent.llm import get_chat
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


class RefinedQuery(BaseModel):
    retrieval_query: str = Field(description="A broader or reworded search query likely to retrieve more relevant courses.")


def refine_query(state: AgentState) -> AgentState:
    prev = state.get("retrieval_query", "")
    interest = state.get("interest_summary", "")
    new_count = state.get("refine_count", 0) + 1

    # Drop the category filter on refine — it's the most common cause of over-narrow retrieval.
    filters = dict(state.get("filters", {}))
    filters.pop("category", None)

    try:
        llm = get_chat(temperature=0.3).with_structured_output(RefinedQuery)
        result: RefinedQuery = llm.invoke(
            f"The search query '{prev}' returned weak results for a learner interested in: {interest}.\n"
            "Rewrite it to be broader and more likely to match real course titles/descriptions."
        )
        new_query = result.retrieval_query
    except Exception:
        logger.exception("refine_query failed; broadening heuristically")
        new_query = interest or prev or "technology courses"

    return {**state, "retrieval_query": new_query, "filters": filters, "refine_count": new_count}
