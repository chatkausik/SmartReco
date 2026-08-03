from typing import TypedDict


class AgentState(TypedDict, total=False):
    # inputs
    user_id: int
    raw_events: list[dict]  # recent events pulled from DB [{event_type, product_id, payload, ...}]
    available_categories: list[str]  # real catalog categories — constrains the category filter

    # analyze_activity outputs
    interest_summary: str
    retrieval_query: str
    filters: dict  # {category?, price_min?, price_max?} -> Chroma metadata `where`

    # retrieve / grade / refine
    candidates: list[dict]  # [{product_id, document, metadata, similarity}]
    grade: str              # "good" | "weak"
    refine_count: int

    # rerank
    reranked: list[dict]    # top-K after LLM reranking

    # generate_copy outputs
    narrative: str
    recommended_product_ids: list[int]

    # audit trail (stored on the Recommendation row)
    retrieval_debug: dict
