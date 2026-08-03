"""The digest activity recap summarizes searches + viewed products (by title)."""
from types import SimpleNamespace

from app.scheduler.jobs import _activity_recap


def _ev(event_type, payload=None, product_id=None):
    return SimpleNamespace(event_type=event_type, payload=payload or {}, product_id=product_id)


def test_recap_names_searches_and_viewed_products():
    events = [
        _ev("search", {"query": "web security"}),
        _ev("product_view", product_id=19),  # title comes from the lookup map, not payload
        _ev("page_view", {"path": "/"}),
    ]
    recap = _activity_recap(events, {19: "Web Application Security Essentials"})
    assert "web security" in recap
    assert "Web Application Security Essentials" in recap


def test_recap_falls_back_when_no_signal():
    assert _activity_recap([_ev("page_view", {"path": "/"})], {}) == "You explored the catalog today."
