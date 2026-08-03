"""Agent graph routing + grounding, with all Mesh calls mocked so it runs in CI without a key.

Covers: the grade->route decision, that a good grade skips the refine loop and reaches
generate_copy, and that recommended ids are grounded in the retrieved candidate set.
"""
import app.agent.nodes.analyze_activity as analyze_mod
import app.agent.nodes.generate_copy as gen_mod
import app.agent.nodes.rerank as rerank_mod
import app.agent.graph as graph_mod
from app.agent.graph import _after_grade
from app.config import settings


def test_after_grade_routing():
    assert _after_grade({"grade": "good", "refine_count": 0}) == "rerank"
    assert _after_grade({"grade": "weak", "refine_count": 0}) == "refine_query"
    # At the cap, stop looping even if still weak.
    assert _after_grade({"grade": "weak", "refine_count": settings.max_refinements}) == "rerank"


class _FakeStructured:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, _prompt):
        name = self.schema.__name__
        if name == "ActivityAnalysis":
            return self.schema(interest_summary="Into AI agents", retrieval_query="ai agents", category=None, price_max=None)
        if name == "RerankResult":
            Item = rerank_mod.ScoredItem
            return self.schema(ranked=[Item(product_id=1, score=9.0), Item(product_id=2, score=7.0)])
        if name == "Recommendation":
            # Include a hallucinated id (999) to prove it gets filtered out.
            return self.schema(narrative="These fit your interest in AI agents.", product_ids=[1, 2, 999])
        raise AssertionError(f"unexpected schema {name}")


class _FakeChat:
    def with_structured_output(self, schema):
        return _FakeStructured(schema)

    def invoke(self, _prompt):
        return type("M", (), {"content": "ok"})()


def _fake_get_chat(temperature=0):
    return _FakeChat()


class _FakeEmbeddings:
    def embed_query(self, _text):
        return [0.1] * 32


def test_good_path_grounds_recommendations(monkeypatch):
    # Mock LLMs in every node that uses one.
    monkeypatch.setattr(analyze_mod, "get_chat", _fake_get_chat)
    monkeypatch.setattr(rerank_mod, "get_chat", _fake_get_chat)
    monkeypatch.setattr(gen_mod, "get_chat", _fake_get_chat)
    # Mock retrieval: strong-similarity candidates so the heuristic grades "good" (no judge call).
    import app.agent.nodes.retrieve as retrieve_mod

    monkeypatch.setattr(retrieve_mod, "get_embeddings", lambda: _FakeEmbeddings())
    canned = [
        {"product_id": 1, "document": "d1", "metadata": {"title": "Agents", "category": "Agentic AI", "price": 99, "level": "advanced"}, "similarity": 0.7},
        {"product_id": 2, "document": "d2", "metadata": {"title": "RAG", "category": "Agentic AI", "price": 79, "level": "intermediate"}, "similarity": 0.6},
        {"product_id": 3, "document": "d3", "metadata": {"title": "LLM", "category": "Agentic AI", "price": 59, "level": "beginner"}, "similarity": 0.5},
    ]
    monkeypatch.setattr(retrieve_mod.vector_store, "query", lambda *a, **k: canned)

    out = graph_mod.run_recommendation(
        1, [{"event_type": "search", "payload": {"query": "ai agents"}}], available_categories=["Agentic AI"]
    )

    assert out["retrieval_debug"]["grade"] == "good"
    assert out["retrieval_debug"]["refine_count"] == 0  # good grade -> no refine loop
    # Hallucinated id 999 dropped; all recommended ids exist in the candidate set.
    assert 999 not in out["recommended_product_ids"]
    assert set(out["recommended_product_ids"]).issubset({1, 2, 3})
    assert out["narrative"]
