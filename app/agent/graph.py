"""The recommendation agent as a compiled LangGraph.

Shape:
    START -> analyze_activity -> retrieve -> grade_retrieval
      grade weak & under refine cap -> refine_query -> retrieve   (loop)
      grade good (or cap hit)       -> rerank -> generate_copy -> END

Metadata filtering happens in `retrieve`; LLM reranking in `rerank`; the grade/refine loop
improves weak retrieval. LangSmith auto-traces every node/LLM call when tracing is enabled.
The graph is compiled once at import and invoked per user.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.analyze_activity import analyze_activity
from app.agent.nodes.generate_copy import generate_copy
from app.agent.nodes.grade_retrieval import grade_retrieval
from app.agent.nodes.refine_query import refine_query
from app.agent.nodes.rerank import rerank
from app.agent.nodes.retrieve import retrieve
from app.agent.state import AgentState
from app.agent.tracing import configure_tracing
from app.config import settings

logger = logging.getLogger(__name__)

configure_tracing()


def _after_grade(state: AgentState) -> str:
    """Loop to refine_query while retrieval is weak and we're under the refinement cap."""
    if state.get("grade") == "weak" and state.get("refine_count", 0) < settings.max_refinements:
        return "refine_query"
    return "rerank"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("analyze_activity", analyze_activity)
    g.add_node("retrieve", retrieve)
    g.add_node("grade_retrieval", grade_retrieval)
    g.add_node("refine_query", refine_query)
    g.add_node("rerank", rerank)
    g.add_node("generate_copy", generate_copy)

    g.add_edge(START, "analyze_activity")
    g.add_edge("analyze_activity", "retrieve")
    g.add_edge("retrieve", "grade_retrieval")
    g.add_conditional_edges(
        "grade_retrieval", _after_grade, {"refine_query": "refine_query", "rerank": "rerank"}
    )
    g.add_edge("refine_query", "retrieve")
    g.add_edge("rerank", "generate_copy")
    g.add_edge("generate_copy", END)
    return g.compile()


GRAPH = build_graph()


def run_recommendation(
    user_id: int, raw_events: list[dict], available_categories: list[str] | None = None
) -> dict:
    """Invoke the agent for one user. Returns {narrative, recommended_product_ids, retrieval_debug}."""
    initial: AgentState = {
        "user_id": user_id,
        "raw_events": raw_events,
        "available_categories": available_categories or [],
        "refine_count": 0,
    }
    final = GRAPH.invoke(initial, config={"run_name": f"reco-user-{user_id}", "tags": ["smartreco"]})

    reranked = final.get("reranked", [])
    debug = {
        "retrieval_query": final.get("retrieval_query"),
        "filters": final.get("filters"),
        "interest_summary": final.get("interest_summary"),
        "grade": final.get("grade"),
        "refine_count": final.get("refine_count"),
        "candidate_scores": [
            {"product_id": c["product_id"], "similarity": c.get("similarity")}
            for c in final.get("candidates", [])
        ],
        "reranked_order": [c["product_id"] for c in reranked],
    }
    return {
        "narrative": final.get("narrative", ""),
        "recommended_product_ids": final.get("recommended_product_ids", []),
        "retrieval_debug": debug,
    }
