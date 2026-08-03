"""Shared LangChain LLM/embeddings clients for the agent, pointed at Mesh.

Using langchain_openai (rather than the raw openai SDK) for the agent's calls is what
gives us automatic LangSmith tracing. The base_url still points at Mesh, so this satisfies
the "every LLM call goes through Mesh" requirement.
"""
from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.agent.mesh_callback import MeshLogCallback
from app.config import settings

_mesh_logger = MeshLogCallback()


@lru_cache
def get_chat(temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.mesh_base_url,
        api_key=settings.mesh_api_key,
        model=settings.mesh_chat_model,
        temperature=temperature,
        callbacks=[_mesh_logger],  # records each call into the MeshAPI Console log
    )


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        base_url=settings.mesh_base_url,
        api_key=settings.mesh_api_key,
        model=settings.mesh_embedding_model,
        check_embedding_ctx_length=False,  # Mesh gateway doesn't need client-side tokenization
    )
