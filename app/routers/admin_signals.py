"""Admin-only live view of every registered user's behavioral signals (real-time via polling).

Both routes are locked behind require_admin. This is the ONLY place signals are shown across
users; a regular user can never reach it (403) and their own Your Signal panel is scoped to
their user_id (see pages._recent_signals / event_service.get_recent_signal_events).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models.user import User
from app.services import event_service, signals

router = APIRouter(prefix="/admin/signals", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def signals_page(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse(request, "admin/signals.html", {"user": user})


@router.get("/data")
def signals_data(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """JSON polled by admin_signals.js: every user with their recent signal chips + last-active."""
    events = event_service.get_recent_signal_events_all(db, limit=400)
    titles = signals.titles_for(db, events)

    grouped: dict[int, list] = {}
    for e in events:  # already newest-first
        grouped.setdefault(e.user_id, []).append(e)

    rows = []
    for u in db.query(User).all():
        evs = grouped.get(u.id, [])
        last = evs[0].created_at if evs else None
        rows.append(
            {
                "id": u.id,
                "email": u.email,
                "role": u.role,
                "last_active": last.isoformat() if last else None,
                "event_count": len(evs),
                "signals": signals.events_to_chips(evs, titles, limit=8),
            }
        )
    # Most-recently-active users first; users with no activity fall to the bottom.
    rows.sort(key=lambda r: r["last_active"] or "", reverse=True)
    return {"users": rows, "total": len(rows)}
