"""Bootstrap the database: create tables and seed the admin account from .env.

Usage: python -m scripts.init_db
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, create_all
from app.models.user import User
from app.security import hash_password


def main() -> None:
    create_all()
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email))
        if existing:
            print(f"Admin already exists: {settings.bootstrap_admin_email}")
            return
        admin = User(
            email=settings.bootstrap_admin_email,
            password_hash=hash_password(settings.bootstrap_admin_password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        print(f"Created bootstrap admin: {settings.bootstrap_admin_email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
