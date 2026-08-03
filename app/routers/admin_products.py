"""Admin product management. All writes go through product_service (dual-write)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models.user import User
from app.services import product_service

router = APIRouter(prefix="/admin/products", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_view(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    products = product_service.list_products(db, include_inactive=True)
    return templates.TemplateResponse(
        request, "admin/product_list.html", {"user": user, "products": products}
    )


@router.get("/new")
def new_form(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse(
        request, "admin/product_form.html", {"user": user, "product": None, "action": "/admin/products/new"}
    )


@router.post("/new")
def create(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(...),
    price: float = Form(0),
    level: str = Form(""),
    rating: float | None = Form(None),
    students: int | None = Form(None),
):
    product_service.create_product(
        db,
        {"title": title, "description": description, "category": category, "price": price,
         "level": level or None, "rating": rating, "students": students},
    )
    return RedirectResponse(url="/admin/products", status_code=303)


@router.get("/{product_id}/edit")
def edit_form(
    request: Request, product_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)
):
    product = product_service.get_product(db, product_id)
    if product is None:
        return RedirectResponse(url="/admin/products", status_code=303)
    return templates.TemplateResponse(
        request,
        "admin/product_form.html",
        {"user": user, "product": product, "action": f"/admin/products/{product_id}/edit"},
    )


@router.post("/{product_id}/edit")
def update(
    request: Request,
    product_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(...),
    price: float = Form(0),
    level: str = Form(""),
    rating: float | None = Form(None),
    students: int | None = Form(None),
    is_active: bool = Form(False),
):
    product_service.update_product(
        db,
        product_id,
        {
            "title": title,
            "description": description,
            "category": category,
            "price": price,
            "level": level or None,
            "rating": rating,
            "students": students,
            "is_active": is_active,
        },
    )
    return RedirectResponse(url="/admin/products", status_code=303)


@router.post("/{product_id}/delete")
def delete(
    request: Request, product_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)
):
    product_service.delete_product(db, product_id)
    return RedirectResponse(url="/admin/products", status_code=303)
