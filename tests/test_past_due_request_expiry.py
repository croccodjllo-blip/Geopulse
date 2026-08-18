"""Request-time past_due grace expiry (sticky plan P1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app import User, app, db, ensure_schema
from services import paddle_billing as pb
from services.entitlements import entitlements_for
from services.paddle_billing import (
    enforce_past_due_plan_expiry,
    past_due_grace_elapsed,
)


def test_past_due_grace_elapsed_boundaries(monkeypatch):
    monkeypatch.setenv("PADDLE_PAST_DUE_GRACE_DAYS", "3")
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert past_due_grace_elapsed(None, now=now) is False
    assert (
        past_due_grace_elapsed(now - timedelta(days=2), now=now) is False
    )
    assert past_due_grace_elapsed(now - timedelta(days=3), now=now) is False
    assert past_due_grace_elapsed(now - timedelta(days=4), now=now) is True


def test_enforce_downgrades_sticky_plus_after_grace():
    class U:
        id = 1
        plan = "plus"
        is_admin = False
        paddle_past_due_since = datetime(2026, 8, 1, tzinfo=timezone.utc)
        alert_email_enabled = True
        webhook_url = "https://hooks.example.com/x"
        webhook_secret = "secret"

    user = U()
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert enforce_past_due_plan_expiry(user, now=now) is True
    assert user.plan == "free"
    assert user.alert_email_enabled is False
    assert user.webhook_url is None
    assert user.webhook_secret is None
    # Idempotent once already free.
    assert enforce_past_due_plan_expiry(user, now=now) is False


def test_enforce_keeps_plan_inside_grace():
    class U:
        id = 2
        plan = "business"
        is_admin = False
        paddle_past_due_since = datetime(2026, 8, 17, tzinfo=timezone.utc)
        alert_email_enabled = True
        webhook_url = None
        webhook_secret = None

    user = U()
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert enforce_past_due_plan_expiry(user, now=now, grace_days=3) is False
    assert user.plan == "business"


def test_user_is_pro_fail_closed_when_grace_elapsed(monkeypatch):
    suffix = uuid4().hex
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"past-due-{suffix}@example.com",
            name="Past Due",
            plan="plus",
            credit_balance_cents=10_000,
        )
        user.set_password("PastDue!23456")
        user.email_verified_at = datetime.now(timezone.utc)
        if hasattr(user, "welcome_credit_granted"):
            user.welcome_credit_granted = True
        user.paddle_past_due_since = datetime.now(timezone.utc) - timedelta(days=10)
        db.session.add(user)
        db.session.commit()
        assert user.is_pro is False
        assert user.is_business is False
        ents = entitlements_for(
            user,
            max_sites_free=1,
            max_sites_pro=50,
            free_total_analyses=3,
            pro_daily_analyses=30,
            free_crawl_pages=5,
            pro_crawl_pages=25,
            pro_crawl_unlimited=False,
            free_history_limit=5,
            pro_history_limit=50,
        )
        assert ents.plan == "free"
        assert ents.is_pro is False


def test_current_user_persists_downgrade(monkeypatch):
    suffix = uuid4().hex
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"past-due-sess-{suffix}@example.com",
            name="Past Due Sess",
            plan="plus",
            credit_balance_cents=10_000,
        )
        user.set_password("PastDue!23456")
        user.email_verified_at = datetime.now(timezone.utc)
        if hasattr(user, "welcome_credit_granted"):
            user.welcome_credit_granted = True
        user.paddle_past_due_since = datetime.now(timezone.utc) - timedelta(days=10)
        user.alert_email_enabled = True
        db.session.add(user)
        db.session.commit()
        uid = int(user.id)
        sv = int(user.session_version or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = sv

    # Any authenticated hit runs current_user() → enforce + commit.
    resp = client.get("/dashboard")
    assert resp.status_code in (200, 302)

    with app.app_context():
        row = db.session.get(User, uid)
        assert row is not None
        assert row.plan == "free"
        assert row.alert_email_enabled is False


def test_plan_from_status_uses_env_grace(monkeypatch):
    monkeypatch.setenv("PADDLE_PAST_DUE_GRACE_DAYS", "1")
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert (
        pb.plan_from_paddle_subscription_status(
            "past_due", past_due_at=now - timedelta(hours=12), now=now
        )
        == "plus"
    )
    assert (
        pb.plan_from_paddle_subscription_status(
            "past_due", past_due_at=now - timedelta(days=2), now=now
        )
        == "free"
    )
