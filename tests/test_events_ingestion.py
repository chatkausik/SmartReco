"""Event ingestion: bulk insert, disallowed types dropped, malformed payloads ignored."""
from app.services import event_service


def test_bulk_insert_and_count(env):
    db = env["db_module"].SessionLocal()
    try:
        from app.models.user import User
        from app.security import hash_password

        u = User(email="e@x.com", password_hash=hash_password("password123"), role="user")
        db.add(u)
        db.commit()
        db.refresh(u)

        stored = event_service.bulk_insert_events(
            db,
            u.id,
            [
                {"event_type": "page_view", "payload": {"path": "/"}},
                {"event_type": "product_view", "product_id": 1, "payload": {}},
                {"event_type": "search", "payload": {"query": "agents"}},
                {"event_type": "not_a_real_type", "payload": {}},  # dropped
            ],
        )
        assert stored == 3  # the disallowed type is filtered out
        assert event_service.count_events_for_user(db, u.id) == 3

        recent = event_service.get_recent_events_for_user(db, u.id, limit=10)
        assert {e.event_type for e in recent} == {"page_view", "product_view", "search"}
    finally:
        db.close()


def test_empty_batch_is_noop(env):
    db = env["db_module"].SessionLocal()
    try:
        assert event_service.bulk_insert_events(db, None, []) == 0
    finally:
        db.close()
