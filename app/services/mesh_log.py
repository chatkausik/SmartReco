"""In-memory log of Mesh API calls, powering the MeshAPI Console.

Every LLM/embedding call the app makes goes through Mesh; embeddings are recorded from
mesh_client, and the agent's chat calls from a LangChain callback (app/agent/mesh_callback).
This is a bounded ring buffer — observability, not persistence.
"""
from __future__ import annotations

import threading
import time
from collections import deque

_MAX = 200
_lock = threading.Lock()
_calls: deque[dict] = deque(maxlen=_MAX)
_seq = 0


def record(kind: str, model: str, purpose: str, latency_ms: float | None = None,
           tokens: int | None = None, status: str = "ok") -> None:
    """kind: 'chat' | 'embedding'. purpose: short label e.g. 'analyze_activity', 'product embed'."""
    global _seq
    with _lock:
        _seq += 1
        _calls.appendleft(
            {
                "id": _seq,
                "ts": time.time(),
                "kind": kind,
                "model": model,
                "purpose": purpose,
                "latency_ms": round(latency_ms) if latency_ms is not None else None,
                "tokens": tokens,
                "status": status,
            }
        )


def snapshot(limit: int = 100) -> list[dict]:
    with _lock:
        return list(_calls)[:limit]


def summary() -> dict:
    with _lock:
        calls = list(_calls)
    chat = sum(1 for c in calls if c["kind"] == "chat")
    emb = sum(1 for c in calls if c["kind"] == "embedding")
    tokens = sum(c["tokens"] or 0 for c in calls)
    lat = [c["latency_ms"] for c in calls if c["latency_ms"] is not None]
    return {
        "total": len(calls),
        "chat": chat,
        "embedding": emb,
        "total_tokens": tokens,
        "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None,
    }
