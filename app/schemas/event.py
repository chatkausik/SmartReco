from datetime import datetime

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    event_type: str = Field(max_length=50)
    product_id: int | None = None
    payload: dict = Field(default_factory=dict)
    session_id: str | None = Field(default=None, max_length=64)
    client_ts: datetime | None = None


class EventBatchIn(BaseModel):
    events: list[EventIn] = Field(max_length=100)  # server-side defensive cap
