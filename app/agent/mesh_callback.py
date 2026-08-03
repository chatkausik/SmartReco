"""LangChain callback that records the agent's Mesh chat calls into the MeshAPI Console log.

Every ChatOpenAI call in the agent points at Mesh; this handler captures model, latency, and
token usage per call, and labels each with the agent node it came from (inferred from the
prompt) so the console reads like the agent's reasoning trace.
"""
from __future__ import annotations

import time

from langchain_core.callbacks import BaseCallbackHandler

from app.config import settings
from app.services import mesh_log

# Distinctive leading phrases from each node's prompt -> readable purpose label.
_NODE_HINTS = [
    ("analyze a learner", "analyze_activity"),
    ("friendly learning advisor", "generate_copy"),
    ("Score each candidate", "rerank"),
    ("broadly relevant", "grade_retrieval"),
    ("Rewrite it to be broader", "refine_query"),
]


def _purpose_from_prompt(prompts: list[str]) -> str:
    text = prompts[0] if prompts else ""
    for hint, label in _NODE_HINTS:
        if hint in text:
            return f"agent · {label}"
    return "agent · chat"


class MeshLogCallback(BaseCallbackHandler):
    def __init__(self) -> None:
        self._runs: dict = {}

    def on_llm_start(self, serialized, prompts, *, run_id=None, **kwargs) -> None:
        self._runs[run_id] = (time.time(), _purpose_from_prompt(prompts or []))

    def on_llm_end(self, response, *, run_id=None, **kwargs) -> None:
        started, purpose = self._runs.pop(run_id, (None, "agent · chat"))
        latency = (time.time() - started) * 1000 if started else None
        model, tokens = settings.mesh_chat_model, None
        try:
            out = response.llm_output or {}
            model = out.get("model_name") or out.get("model") or model
            usage = out.get("token_usage") or {}
            tokens = usage.get("total_tokens")
        except Exception:  # noqa: BLE001
            pass
        mesh_log.record("chat", model, purpose, latency_ms=latency, tokens=tokens)

    def on_llm_error(self, error, *, run_id=None, **kwargs) -> None:
        started, purpose = self._runs.pop(run_id, (None, "agent · chat"))
        latency = (time.time() - started) * 1000 if started else None
        mesh_log.record("chat", settings.mesh_chat_model, purpose, latency_ms=latency, status="error")
