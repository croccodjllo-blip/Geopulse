"""Alert settings follow the Plus/Business entitlement."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app import User, app, db, ensure_schema


def _new_user(plan: str) -> User:
    user = User(
        email=f"alerts-{plan}-{uuid4().hex}@example.com",
        name=f"Alerts {plan}",
        plan=plan,
        alert_email_enabled=True,
    )
    user.set_password("AlertsTest!23456")
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.add(user)
    db.session.commit()
    return user


def _client_for(user_id: int, session_version: int):
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["session_version"] = session_version
    return client


def test_free_cannot_save_alerts_but_plus_can():
    with app.app_context():
        ensure_schema()
        free = _new_user("free")
        plus = _new_user("plus")
        free_id, plus_id = free.id, plus.id
        free_version = int(free.session_version or 0)
        plus_version = int(plus.session_version or 0)

    previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        free_response = _client_for(free_id, free_version).post(
            "/dashboard/impostazioni",
            data={"action": "alerts"},
            follow_redirects=False,
        )
        assert free_response.status_code in {302, 303}
        assert free_response.headers["Location"].endswith("/prezzi")

        with app.app_context():
            assert db.session.get(User, free_id).alert_email_enabled is True

        plus_response = _client_for(plus_id, plus_version).post(
            "/dashboard/impostazioni",
            data={"action": "alerts"},
            follow_redirects=False,
        )
        assert plus_response.status_code in {302, 303}
        assert plus_response.headers["Location"].endswith("/dashboard/impostazioni")

        with app.app_context():
            assert db.session.get(User, plus_id).alert_email_enabled is False
    finally:
        app.config["WTF_CSRF_ENABLED"] = previous_csrf
