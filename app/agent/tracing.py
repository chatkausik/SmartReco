"""LangSmith observability wiring (bonus feature).

LangChain/LangGraph auto-trace every LLM call and graph node once these env vars are set,
so there is no per-node instrumentation to maintain — we just export the config the user
put in .env. Tracing is off unless LANGCHAIN_TRACING_V2=true and an API key is present.
"""
import os

from app.config import settings


def configure_tracing() -> bool:
    """Export LangSmith env if enabled. Returns True if tracing is active."""
    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        return True
    # Make sure a stale env var doesn't silently enable tracing without a key.
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    return False
