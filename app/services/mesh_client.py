"""Single entry point for non-agent Mesh API calls (embeddings + simple chat).

Every LLM/embedding call in SmartReco must go through Mesh (OpenAI-compatible gateway).
The LangGraph agent uses langchain_openai pointed at the same Mesh base_url so LangSmith
can auto-trace it; everything outside the agent (product embeddings, seed script) uses
this thin wrapper over the raw openai SDK.
"""
from __future__ import annotations

import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=settings.mesh_base_url, api_key=settings.mesh_api_key)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts through Mesh. Raises on failure (callers decide how to handle)."""
    if not texts:
        return []
    resp = get_client().embeddings.create(model=settings.mesh_embedding_model, input=texts)
    # Preserve input order.
    return [item.embedding for item in sorted(resp.data, key=lambda d: d.index)]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
