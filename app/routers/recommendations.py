"""User-facing recommendations. The page lazily triggers regeneration (gated by the
trigger logic) and otherwise serves the cached row."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.deps import get_db, require_login
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.user import User
from app.services import recommendation_service

router = APIRouter(tags=["recommendations"])
templates = Jinja2Templates(directory="app/templates")


def _explain(db: Session, rec: Recommendation | None) -> dict | None:
    """Turn the stored retrieval_debug audit trail into a display model for the
    'How the agent chose these' panel — real query, filters, self-correction loop, and the
    reranked shortlist with similarity scores. Proves the RAG pipeline is genuine, not canned.
    """
    debug = getattr(rec, "retrieval_debug", None)
    if not debug:
        return None
    candidate_scores = debug.get("candidate_scores") or []
    reranked_order = debug.get("reranked_order") or []
    sim_by_id = {c["product_id"]: c.get("similarity") for c in candidate_scores}

    # Batch-load titles for every product id the trail references (pattern mirrors
    # pages._recent_signals).
    ids = {*sim_by_id.keys(), *reranked_order}
    titles = {}
    if ids:
        titles = {p.id: p.title for p in db.query(Product).filter(Product.id.in_(ids)).all()}

    reranked = [
        {"product_id": pid, "title": titles.get(pid, f"course #{pid}"), "similarity": sim_by_id.get(pid)}
        for pid in reranked_order
    ]
    filters = debug.get("filters") or {}
    return {
        "interest_summary": debug.get("interest_summary"),
        "retrieval_query": debug.get("retrieval_query"),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "grade": debug.get("grade"),
        "refine_count": debug.get("refine_count") or 0,
        "candidate_count": len(candidate_scores),
        "reranked": reranked,
    }


@router.get("/recommendations")
def recommendations_page(
    request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)
):
    rec = recommendation_service.get_or_generate_recommendation(db, user)
    products = recommendation_service.get_recommended_products(db, rec)
    return templates.TemplateResponse(
        request,
        "recommendations.html",
        {"user": user, "rec": rec, "products": products, "explain": _explain(db, rec)},
    )


@router.post("/recommendations/refresh")
def refresh_recommendations(user: User = Depends(require_login), db: Session = Depends(get_db)):
    """Force a fresh run (used by the 'refresh' button)."""
    recommendation_service.get_or_generate_recommendation(db, user, force=True)
    return RedirectResponse(url="/recommendations", status_code=303)
