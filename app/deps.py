from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.user import User
from app.security import read_session_token

__all__ = ["get_db", "get_current_user", "require_login", "require_admin"]


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    data = read_session_token(token)
    if not data:
        return None
    return db.get(User, data.get("user_id"))


def require_login(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return user


def require_admin(user: User = Depends(require_login)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
