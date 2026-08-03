"""Node: judge whether the retrieved candidates are good enough to recommend from.

Cheap-first: a similarity heuristic decides most cases with no extra LLM call. Only the
ambiguous middle band escalates to a small LLM relevance judge — keeping the agent efficient.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.agent.llm import get_chat
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

GOOD_SIM = 0.42   # top hit at/above this -> clearly good, no LLM judge needed
WEAK_SIM = 0.22   # top hit below this -> clearly weak
MIN_CANDIDATES = 3


class RelevanceJudgement(BaseModel):
    relevant: bool = Field(description="True if the candidates broadly match the learner's interest.")


def grade_retrieval(state: AgentState) -> AgentState:
    candidates = state.get("candidates", [])
    if len(candidates) < MIN_CANDIDATES:
        return {**state, "grade": "weak"}

    top_sim = max((c.get("similarity") or 0.0) for c in candidates)
    if top_sim >= GOOD_SIM:
        return {**state, "grade": "good"}
    if top_sim < WEAK_SIM:
        return {**state, "grade": "weak"}

    # Ambiguous band -> one cheap LLM judge call.
    interest = state.get("interest_summary", "")
    titles = "\n".join(f"- {c['metadata'].get('title')}" for c in candidates[:6])
    try:
        judge = get_chat(temperature=0).with_structured_output(RelevanceJudgement)
        result: RelevanceJudgement = judge.invoke(
            f"Learner interest: {interest}\n\nCandidate courses:\n{titles}\n\n"
            "Are these candidates broadly relevant to the learner's interest?"
        )
        return {**state, "grade": "good" if result.relevant else "weak"}
    except Exception:
        logger.exception("grade_retrieval judge failed; treating as good to avoid a stall")
        return {**state, "grade": "good"}
