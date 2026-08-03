"""User signals are isolated per-user; the admin all-users view is admin-only.

Locks in the guarantee that a regular user can never see another user's behavioral signals,
and that the cross-user admin dashboard endpoint rejects non-admins.
"""
from app.services import event_service


def _make_user(db, email, role="user"):
    from app.models.user import User
    from app.security import hash_password

    u = User(email=email, password_hash=hash_password("password123"), role=role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_user_signals_are_isolated(env):
    db = env["db_module"].SessionLocal()
    try:
        a = _make_user(db, "a@x.com")
        b = _make_user(db, "b@x.com")
        event_service.bulk_insert_events(db, a.id, [{"event_type": "search", "payload": {"query": "agents"}}])
        event_service.bulk_insert_events(db, b.id, [{"event_type": "search", "payload": {"query": "mlops"}}])

        a_events = event_service.get_recent_signal_events(db, user_id=a.id)
        b_events = event_service.get_recent_signal_events(db, user_id=b.id)

        assert a_events and all(e.user_id == a.id for e in a_events)
        assert b_events and all(e.user_id == b.id for e in b_events)
        # A must NEVER see B's signal.
        assert not any((e.payload or {}).get("query") == "mlops" for e in a_events)

        # The admin aggregate spans both users (this is the only cross-user read).
        everyone = event_service.get_recent_signal_events_all(db)
        assert {e.user_id for e in everyone} == {a.id, b.id}
    finally:
        db.close()


def test_admin_signals_endpoint_requires_admin(env):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app
    from app.security import create_session_token

    db = env["db_module"].SessionLocal()
    try:
        user = _make_user(db, "regular@x.com", role="user")
        admin = _make_user(db, "admin@x.com", role="admin")
        user_token = create_session_token(user.id, user.role)
        admin_token = create_session_token(admin.id, admin.role)
    finally:
        db.close()

    client = TestClient(app)  # no context manager -> lifespan/scheduler not started
    cookie = settings.session_cookie_name

    # Anonymous -> 401, regular user -> 403, admin -> 200.
    assert client.get("/admin/signals/data").status_code == 401
    assert client.get("/admin/signals/data", headers={"Cookie": f"{cookie}={user_token}"}).status_code == 403
    r = client.get("/admin/signals/data", headers={"Cookie": f"{cookie}={admin_token}"})
    assert r.status_code == 200
    assert "users" in r.json()
