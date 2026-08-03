"""MeshAPI Console — observability for the app's Mesh API calls.

Makes the "every AI call routes through Mesh" requirement visible: a live view of the real
chat (agent nodes) and embedding (dual-write, retrieval) calls, with model, tokens, latency.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.deps import get_current_user
from app.models.user import User
from app.services import mesh_log

router = APIRouter(tags=["mesh"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/mesh-console")
def console(request: Request, user: User | None = Depends(get_current_user)):
    return templates.TemplateResponse(
        request,
        "mesh_console.html",
        {
            "user": user,
            "base_url": settings.mesh_base_url,
            "chat_model": settings.mesh_chat_model,
            "embedding_model": settings.mesh_embedding_model,
        },
    )


@router.get("/api/mesh/console")
def console_data():
    return {"summary": mesh_log.summary(), "calls": mesh_log.snapshot(limit=100)}
