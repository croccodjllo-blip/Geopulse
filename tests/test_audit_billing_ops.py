"""Audit fixes: waiver fail-closed, ops reclaim token, pack email domain, prod guards."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from centropic.prod_guards import evaluate_env_guards


def _verified_user(**kwargs):
    from app import User

    user = User(**kwargs)
    user.set_password("AuditTest!23456")
    user.email_verified_at = datetime.now(timezone.utc)
    return user


def test_waiver_persist_failure_returns_error_not_none(monkeypatch):
    """Commit failure during waiver persist must never silently fall through."""
    from app import User, _require_digital_service_waiver, app, db, ensure_schema

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"waiver-fail-{uuid4().hex}@example.com",
            name="Waiver Fail",
            plan="free",
        )
        user.set_password("AuditTest!23456")
        db.session.add(user)
        db.session.commit()

        def _boom():
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(db.session, "commit", _boom)

        with app.test_request_context(
            "/billing/checkout",
            method="POST",
            data={"accept_immediate_service": "y"},
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        ):
            result = _require_digital_service_waiver(user, redirect_to="/pricing")

        # Never None: a failed persist must not silently let checkout proceed.
        assert result is not None
        response, status = result
        assert status == 503
        body = response.get_json()
        assert body["ok"] is False
        assert body["error"] == "digital_service_waiver_persist_failed"


def test_waiver_persist_failure_redirects_for_html_form(monkeypatch):
    from app import User, _require_digital_service_waiver, app, db, ensure_schema

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"waiver-fail-html-{uuid4().hex}@example.com",
            name="Waiver Fail HTML",
            plan="free",
        )
        user.set_password("AuditTest!23456")
        db.session.add(user)
        db.session.commit()

        def _boom():
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(db.session, "commit", _boom)

        with app.test_request_context(
            "/billing/checkout",
            method="POST",
            data={"accept_immediate_service": "y"},
        ):
            result = _require_digital_service_waiver(user, redirect_to="/pricing")

        assert result is not None
        assert result.status_code == 302


def test_billing_accept_immediate_service_fails_closed_when_not_recorded(monkeypatch):
    """Even if the waiver "accepted" branch is reached, ok:false unless persisted."""
    from app import User, app, billing_accept_immediate_service, db, ensure_schema

    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"waiver-endpoint-{uuid4().hex}@example.com",
            name="Waiver Endpoint",
            plan="free",
        )
        user.set_password("AuditTest!23456")
        user.email_verified_at = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.commit()
        uid = user.id
        sv = int(user.session_version or 0)

    monkeypatch.setattr(
        "app._require_digital_service_waiver", lambda user, redirect_to: None
    )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = sv

    res = client.post(
        "/billing/accept-immediate-service",
        data={"accept_immediate_service": "y"},
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 503
    body = res.get_json()
    assert body["ok"] is False


def test_ops_reclaim_jobs_requires_token_even_for_admin(monkeypatch):
    """Admin session alone must not bypass HEALTH_DETAIL_TOKEN (fail-closed)."""
    from app import User, app, db, ensure_schema

    suffix = uuid4().hex
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", f"ops-token-{suffix}")

    with app.app_context():
        ensure_schema()
        admin = User(
            email=f"ops-admin-{suffix}@example.com",
            name="Ops Admin",
            plan="admin",
        )
        admin.set_password("AuditTest!23456")
        db.session.add(admin)
        db.session.commit()
        uid = admin.id
        sv = int(admin.session_version or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["session_version"] = sv

    denied = client.post("/ops/reclaim-jobs")
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "forbidden"

    allowed = client.post(f"/ops/reclaim-jobs?token=ops-token-{suffix}")
    assert allowed.status_code == 200
    assert allowed.get_json()["ok"] is True


def test_ops_reclaim_jobs_rejects_missing_health_token_env(monkeypatch):
    """No HEALTH_DETAIL_TOKEN configured at all → always forbidden."""
    from app import app

    monkeypatch.delenv("HEALTH_DETAIL_TOKEN", raising=False)
    client = app.test_client()
    denied = client.post("/ops/reclaim-jobs?token=anything")
    assert denied.status_code == 403


def test_email_pack_rejects_foreign_address(monkeypatch):
    """Pack email must reject an address outside the account/verified domain."""
    from app import SiteAnalysis, app, db

    monkeypatch.setattr("app.mail_configured", lambda: True)
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    app.config["WTF_CSRF_ENABLED"] = False
    called = {"n": 0}

    def _boom(**kwargs):
        called["n"] += 1

    monkeypatch.setattr("app.send_email_with_attachment", _boom)

    with app.app_context():
        user = _verified_user(
            email=f"owner-{uuid4().hex}@ownerdomain.example",
            name="Owner",
            plan="plus",
            credit_balance_cents=5000,
        )
        db.session.add(user)
        db.session.commit()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://pack-foreign.example.com/",
            domain="pack-foreign.example.com",
            aio_score=50,
            geo_score=42,
            findings_json="[]",
        )
        db.session.add(site)
        db.session.commit()
        site_id = site.id
        user_id = user.id
        sv = int(getattr(user, "session_version", 0) or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["session_version"] = sv

    res = client.post(
        f"/dashboard/email-pack/{site_id}",
        data={"to_email": "attacker@evil-domain.example"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 303)
    assert called["n"] == 0


def test_email_pack_allows_verified_same_domain(monkeypatch):
    """A different mailbox on the same verified domain is allowed."""
    from app import SiteAnalysis, app, db

    sent: dict[str, str] = {}

    def _fake_send(**kwargs):
        sent["to"] = kwargs.get("to_email") or ""

    monkeypatch.setattr("app.mail_configured", lambda: True)
    monkeypatch.setattr("app.send_email_with_attachment", _fake_send)
    monkeypatch.setattr("app.pack_fix_html_bytes", lambda analysis: b"<html>pack</html>")
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    app.config["WTF_CSRF_ENABLED"] = False

    domain = f"team-{uuid4().hex}.example"
    with app.app_context():
        user = _verified_user(
            email=f"owner@{domain}",
            name="Owner",
            plan="plus",
            credit_balance_cents=5000,
        )
        db.session.add(user)
        db.session.commit()
        site = SiteAnalysis(
            user_id=user.id,
            url="https://pack-samedomain.example.com/",
            domain="pack-samedomain.example.com",
            aio_score=50,
            geo_score=42,
            findings_json="[]",
        )
        db.session.add(site)
        db.session.commit()
        site_id = site.id
        user_id = user.id
        sv = int(getattr(user, "session_version", 0) or 0)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["session_version"] = sv

    res = client.post(
        f"/dashboard/email-pack/{site_id}",
        data={"to_email": f"colleague@{domain}"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 303)
    assert sent.get("to") == f"colleague@{domain}"


def test_prod_guards_includes_paddle_price_plus_monthly(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    monkeypatch.setenv("ADMIN_BOOTSTRAP", "0")
    monkeypatch.setenv("ALLOW_DROP_ANALYSIS_JOBS", "0")
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "5000")
    monkeypatch.setenv("TRUST_PROXY", "1")
    monkeypatch.setenv("BEHIND_NGINX", "1")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfsec_test")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", "health-test-token")
    monkeypatch.delenv("PADDLE_PRICE_PLUS_MONTHLY", raising=False)

    result = evaluate_env_guards()
    assert "PADDLE_PRICE_PLUS_MONTHLY" in result["checks"]
    assert result["ok"] is False
    assert "PADDLE_PRICE_PLUS_MONTHLY" in result["failures"]

    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_plus_test")
    result_ok = evaluate_env_guards()
    assert "PADDLE_PRICE_PLUS_MONTHLY" not in result_ok["failures"]


def test_prod_guards_paddle_price_soft_when_paddle_unset(monkeypatch):
    """No PADDLE_API_KEY/CLIENT_TOKEN at all → price check does not hard-fail."""
    monkeypatch.delenv("PADDLE_API_KEY", raising=False)
    monkeypatch.delenv("PADDLE_CLIENT_TOKEN", raising=False)
    monkeypatch.delenv("PADDLE_PRICE_PLUS_MONTHLY", raising=False)

    result = evaluate_env_guards()
    assert result["checks"]["PADDLE_PRICE_PLUS_MONTHLY"]["ok"] is True
