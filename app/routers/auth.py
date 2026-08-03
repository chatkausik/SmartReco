from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.models.user import User
from app.schemas.auth import is_valid_email
from app.security import create_session_token, hash_password, verify_password

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None})


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    if not is_valid_email(email):
        return templates.TemplateResponse(
            request, "register.html", {"error": "Please enter a valid email address."}, status_code=400
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request, "register.html", {"error": "Password must be at least 8 characters."}, status_code=400
        )
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        return templates.TemplateResponse(
            request, "register.html", {"error": "An account with that email already exists."}, status_code=400
        )

    user = User(email=email, password_hash=hash_password(password), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)

    response = RedirectResponse(url="/", status_code=303)
    _set_session_cookie(response, user)
    return response


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "login.html", {"error": "Invalid email or password."}, status_code=400
        )

    response = RedirectResponse(url="/", status_code=303)
    _set_session_cookie(response, user)
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response


def _set_session_cookie(response: RedirectResponse, user: User) -> None:
    token = create_session_token(user.id, user.role)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
    )
