"""Trigger/caching logic: the expensive agent run is gated by event-count threshold +
cooldown, with a max-staleness backstop. Between regenerations the cache is served."""
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.recommendation import Recommendation
from app.services.recommendation_service import should_regenerate


def _rec(generated_ago_minutes: float, event_count: int) -> Recommendation:
    r = Recommendation(user_id=1)
    r.generated_at = datetime.now(timezone.utc) - timedelta(minutes=generated_ago_minutes)
    r.event_count_at_generation = event_count
    return r


def test_cold_start_always_generates():
    assert should_regenerate(None, 0) is True


def test_no_regen_when_below_threshold():
    # Fresh rec, only a couple new events, within cooldown -> serve cache.
    rec = _rec(generated_ago_minutes=1, event_count=10)
    assert should_regenerate(rec, current_event_count=12) is False


def test_no_regen_when_enough_events_but_within_cooldown():
    rec = _rec(generated_ago_minutes=1, event_count=0)
    # Plenty of new events, but cooldown (min_cooldown_minutes) not elapsed.
    assert settings.min_cooldown_minutes > 1
    assert should_regenerate(rec, current_event_count=settings.event_threshold + 5) is False


def test_regen_when_threshold_and_cooldown_met():
    rec = _rec(generated_ago_minutes=settings.min_cooldown_minutes + 1, event_count=0)
    assert should_regenerate(rec, current_event_count=settings.event_threshold) is True


def test_regen_on_max_staleness_even_without_events():
    rec = _rec(generated_ago_minutes=settings.max_staleness_hours * 60 + 1, event_count=100)
    # No new events, but past the staleness backstop -> refresh anyway.
    assert should_regenerate(rec, current_event_count=100) is True
