"""Node: turn a user's recent behavior into an interest summary + retrieval query + filters.

Handles cold start (few/no events) with a generic exploration query rather than crashing.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.agent.llm import get_chat
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


class ActivityAnalysis(BaseModel):
    interest_summary: str = Field(description="1-2 sentences describing what this user is into.")
    retrieval_query: str = Field(description="A semantic search query capturing their strongest interest.")
    category: str | None = Field(default=None, description="A single category to filter to, if the interest is clearly focused; else null.")
    price_max: float | None = Field(default=None, description="A max price if the user only viewed cheaper items; else null.")


def _summarize_events(events: list[dict]) -> str:
    lines = []
    for e in events[:40]:
        etype = e.get("event_type")
        payload = e.get("payload") or {}
        title = payload.get("title")
        if etype == "search":
            lines.append(f"- searched: {payload.get('query')}")
        elif etype == "product_view":
            lines.append(f"- viewed product: {title or e.get('product_id')} ({payload.get('category', '')})")
        elif etype == "click":
            lines.append(f"- clicked: {payload.get('label')}")
        elif etype == "time_spent":
            lines.append(f"- spent {int(payload.get('duration_ms', 0) / 1000)}s on {title or payload.get('path', '')}")
        elif etype == "page_view":
            lines.append(f"- visited: {payload.get('path')}")
    return "\n".join(lines) if lines else "(no activity yet)"


def analyze_activity(state: AgentState) -> AgentState:
    events = state.get("raw_events", [])

    if not events:
        # Cold start: a broad, safe query so retrieval still returns real catalog items.
        return {
            **state,
            "interest_summary": "New learner exploring the catalog for the first time.",
            "retrieval_query": "popular beginner-friendly technology and programming courses",
            "filters": {},
            "refine_count": 0,
        }

    activity = _summarize_events(events)
    categories = state.get("available_categories", [])
    category_hint = (
        f"Valid categories (you may ONLY use one of these for the category filter, or null): "
        f"{', '.join(categories)}\n"
        if categories
        else ""
    )
    llm = get_chat(temperature=0).with_structured_output(ActivityAnalysis)
    try:
        result: ActivityAnalysis = llm.invoke(
            "You analyze a learner's activity on a course platform and infer what to recommend.\n"
            "Given the activity log below, produce an interest summary and a semantic search query "
            "that will retrieve the most relevant courses. Only set a category/price filter if the "
            "behavior clearly justifies it.\n"
            f"{category_hint}\n"
            f"Activity log:\n{activity}"
        )
    except Exception:
        logger.exception("analyze_activity LLM call failed; falling back to raw activity as query")
        return {
            **state,
            "interest_summary": "Interested learner (analysis unavailable).",
            "retrieval_query": activity.replace("\n", " ")[:300] or "technology courses",
            "filters": {},
            "refine_count": 0,
        }

    filters: dict = {}
    # Only honor a category filter that actually exists in the catalog (guard against invented ones).
    if result.category and (not categories or result.category in categories):
        filters["category"] = result.category
    if result.price_max:
        filters["price_max"] = result.price_max

    return {
        **state,
        "interest_summary": result.interest_summary,
        "retrieval_query": result.retrieval_query,
        "filters": filters,
        "refine_count": 0,
    }
