from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_admin
from app.models.product import Product
from app.models.user import User
from app.services import product_service

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def home(request: Request, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    products = product_service.list_products(db)
    return templates.TemplateResponse(request, "index.html", {"user": user, "products": products})


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
        request, "index.html", {"user": user, "products": products, "query": q}
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
    return templates.TemplateResponse(
        request, "product_detail.html", {"user": user, "product": product}
    )


@router.get("/admin")
def admin_home(user: User = Depends(require_admin)):
    return RedirectResponse(url="/admin/products", status_code=303)
