from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_admin
from app.models.product import Product
from app.models.user import User
from app.services import event_service, product_service, recommendation_service, related, signals

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")

# Short, per-category curriculum outlines shown on the product page (illustrative).
_CURRICULA = {
    "Generative AI": ["Foundations & tokenization", "Retrieval & grounding", "Evaluation & guardrails", "Serving & cost control", "Capstone: ship a feature"],
    "Agentic AI": ["State machines for agents", "Tool routing patterns", "Working memory & scratchpads", "Self-grading & refinement", "Observability & debugging"],
    "MLOps": ["Experiment tracking", "Model registry & CI/CD", "Deployment strategies", "Monitoring & drift", "Incident playbooks"],
    "Data Engineering": ["Ingestion & modeling", "Batch pipelines", "Streaming & windowing", "Data quality & tests", "Serving features"],
    "Cloud & DevOps": ["Containers & images", "Orchestration basics", "CI/CD pipelines", "Observability", "Scaling & rollouts"],
    "Python for AI": ["Modern Python & typing", "Async & concurrency", "The data stack", "Testing & packaging", "Project: end to end"],
}
_DEFAULT_CURRICULUM = ["Getting started", "Core concepts", "Hands-on project", "Advanced patterns", "Wrap-up & next steps"]


def _categories(db: Session) -> list[str]:
    return [
        row[0]
        for row in db.query(Product.category).filter(Product.is_active.is_(True)).distinct().order_by(Product.category).all()
    ]


def _recent_signals(db: Session, request: Request, user: User | None, limit: int = 10) -> list[dict]:
    """The last interaction events as Your-Signal chips {k, v}, newest-first.

    Strictly scoped to the current visitor: a logged-in user's chips come from THEIR user_id
    only (never another user's), and anonymous visitors are scoped to their sr_sid session
    cookie. get_recent_signal_events enforces this — user_id wins and is never mixed across users.
    """
    sid = request.cookies.get("sr_sid")
    events = event_service.get_recent_signal_events(
        db, user_id=(user.id if user else None), session_id=sid, limit=limit * 2
    )
    return signals.events_to_chips(events, signals.titles_for(db, events), limit=limit)


@router.get("/")
def home(request: Request, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    products = product_service.list_products(db)
    # Personalized picks at the foot of the landing page for logged-in users. Gated/cached by the
    # same trigger logic as /recommendations — usually a plain SQL read, no LLM call on each load.
    rec = rec_products = None
    if user is not None:
        rec = recommendation_service.get_or_generate_recommendation(db, user)
        rec_products = recommendation_service.get_recommended_products(db, rec)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"user": user, "products": products, "categories": _categories(db),
         "recent_signals": _recent_signals(db, request, user),
         "rec": rec, "rec_products": rec_products},
    )


@router.get("/products")
def search(
    request: Request,
    q: str = "",
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = q.strip()
    stmt = select(Product).where(Product.is_active.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Product.title.ilike(like), Product.description.ilike(like), Product.category.ilike(like))
        )
    products = list(db.scalars(stmt.order_by(Product.created_at.desc())).all())
    return templates.TemplateResponse(
        request,
        "index.html",
        {"user": user, "products": products, "query": q, "categories": _categories(db),
         "recent_signals": _recent_signals(db, request, user)},
    )


@router.get("/products/{product_id}")
def product_detail(
    request: Request,
    product_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = product_service.get_product(db, product_id)
    if product is None or not product.is_active:
        return RedirectResponse(url="/", status_code=303)

    curriculum = _CURRICULA.get(product.category, _DEFAULT_CURRICULUM)
    related_products = related.related_products(db, product_id, limit=4)

    # AGENT · RECOMMENDATION: real cached narrative for logged-in users (gated — usually no LLM
    # call). Anonymous users get a client-side teaser composed by signal.js.
    agent_rec = None
    if user is not None:
        rec = recommendation_service.get_or_generate_recommendation(db, user)
        agent_rec = rec.narrative if rec else None

    return templates.TemplateResponse(
        request,
        "product_detail.html",
        {
            "user": user,
            "product": product,
            "curriculum": curriculum,
            "related": related_products,
            "agent_rec": agent_rec,
            "recent_signals": _recent_signals(db, request, user),
        },
    )


@router.get("/cart")
def cart(request: Request, user: User | None = Depends(get_current_user)):
    # Cart contents live in localStorage; the page renders them client-side (cart.js).
    return templates.TemplateResponse(request, "cart.html", {"user": user})


@router.get("/admin")
def admin_home(user: User = Depends(require_admin)):
    return RedirectResponse(url="/admin/products", status_code=303)
