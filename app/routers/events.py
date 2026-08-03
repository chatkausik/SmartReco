"""Behavioral event ingestion. Fast, batched, non-blocking: parses a batch, bulk-inserts,
returns 204 immediately. No recommendation-trigger work happens inline here.

Accepts both fetch (application/json) and navigator.sendBeacon (text/plain) bodies — the
Beacon API can't set arbitrary Content-Type headers, so we parse the raw body ourselves.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.event import EventBatchIn
from app.services import event_service

router = APIRouter(tags=["events"])


@router.post("/api/events", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_events(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    if not raw:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    try:
        data = json.loads(raw)
        batch = EventBatchIn.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        # Bad payloads are dropped silently — telemetry must never surface errors to the UX.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Tie events to the server-managed session cookie so the Your Signal panel can query them
    # back on a page load (works for anonymous visitors too). Falls back to the client id.
    sr_sid = request.cookies.get("sr_sid")
    events = []
    for e in batch.events:
        d = e.model_dump()
        if sr_sid:
            d["session_id"] = sr_sid
        events.append(d)
    event_service.bulk_insert_events(db, user.id if user else None, events)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
