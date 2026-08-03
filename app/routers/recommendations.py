"""User-facing recommendations. The page lazily triggers regeneration (gated by the
trigger logic) and otherwise serves the cached row."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.deps import get_db, require_login
from app.models.user import User
from app.services import recommendation_service

router = APIRouter(tags=["recommendations"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/recommendations")
def recommendations_page(
    request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)
):
    rec = recommendation_service.get_or_generate_recommendation(db, user)
    products = recommendation_service.get_recommended_products(db, rec)
    return templates.TemplateResponse(
        request, "recommendations.html", {"user": user, "rec": rec, "products": products}
    )


@router.post("/recommendations/refresh")
def refresh_recommendations(user: User = Depends(require_login), db: Session = Depends(get_db)):
    """Force a fresh run (used by the 'refresh' button)."""
    recommendation_service.get_or_generate_recommendation(db, user, force=True)
    return RedirectResponse(url="/recommendations", status_code=303)
