"""Regression suite for expert SaaS P0/P1 criticals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import (
    ADMIN_EMAIL,
    AnalysisJob,
    SiteAnalysis,
    User,
    active_analyze_job_for_url,
    app,
    db,
    ensure_admin_user,
    ensure_schema,
)
from services.alerts import dispatch_alerts
from services.jobs import (
    DuplicateAnalyzeJobError,
    enqueue_analysis,
    reclaim_stale_jobs,
)


def test_ensure_admin_refuses_preclaim_without_bootstrap(monkeypatch):
    with app.app_context():
        ensure_schema()
        email = ADMIN_EMAIL
        existing = User.query.filter_by(email=email).first()
        if existing is None:
            existing = User(
                email=email,
                name="Preclaim",
                plan="free",
                role=None,
                credit_balance_cents=0,
            )
            existing.set_password("attacker-password-1")
            db.session.add(existing)
            db.session.commit()
        else:
            existing.role = None
            existing.plan = "free"
            existing.set_password("attacker-password-1")
            db.session.commit()

        monkeypatch.setenv("ADMIN_PASSWORD", "ops-secret-password-99")
        monkeypatch.setattr("app.ADMIN_PASSWORD", "ops-secret-password-99")
        monkeypatch.setattr("app.ADMIN_BOOTSTRAP", False)

        promoted = ensure_admin_user()
        assert promoted is None
        db.session.refresh(existing)
        assert (existing.role or "").lower() != "admin"
        assert (existing.plan or "").lower() != "admin"


def test_ensure_admin_bootstrap_promotes_and_resets(monkeypatch):
    with app.app_context():
        ensure_schema()
        email = ADMIN_EMAIL
        existing = User.query.filter_by(email=email).first()
        if existing is None:
            existing = User(
                email=email,
                name="Preclaim",
                plan="free",
                role=None,
                credit_balance_cents=0,
            )
            existing.set_password("attacker-password-1")
            db.session.add(existing)
            db.session.commit()
        else:
            existing.role = None
            existing.plan = "free"
            existing.set_password("attacker-password-1")
            db.session.commit()

        monkeypatch.setenv("ADMIN_PASSWORD", "ops-secret-password-99")
        monkeypatch.setattr("app.ADMIN_PASSWORD", "ops-secret-password-99")
        monkeypatch.setattr("app.ADMIN_BOOTSTRAP", True)

        promoted = ensure_admin_user()
        assert promoted is not None
        db.session.refresh(existing)
        assert existing.role == "admin"
        assert existing.plan == "admin"
        assert existing.check_password("ops-secret-password-99")


def test_register_blocks_admin_email_enumeration_safe():
    with app.app_context():
        ensure_schema()
        prev = app.config.get("WTF_CSRF_ENABLED", True)
        app.config["WTF_CSRF_ENABLED"] = False
        try:
            before_ids = {u.id for u in User.query.filter_by(email=ADMIN_EMAIL).all()}
            client = app.test_client()
            resp = client.post(
                "/register",
                data={
                    "name": "Attacker",
                    "email": ADMIN_EMAIL,
                    "password": "AttackerPass!23456",
                    "confirm": "AttackerPass!23456",
                    "role": "founder",
                    "accept_terms": "y",
                },
                follow_redirects=False,
            )
            assert resp.status_code in {302, 200}
            after = User.query.filter_by(email=ADMIN_EMAIL).all()
            assert {u.id for u in after} == before_ids
            for u in after:
                assert (u.plan or "").lower() != "free" or u.id in before_ids
        finally:
            app.config["WTF_CSRF_ENABLED"] = prev


def test_paddle_prefers_customer_over_forged_custom_data():
    from services.paddle_billing import resolve_webhook_user

    victim = SimpleNamespace(id=10, paddle_customer_id=None, paddle_subscription_id=None)
    attacker = SimpleNamespace(
        id=20, paddle_customer_id="ctm_attacker", paddle_subscription_id=None
    )
    users = {10: victim, 20: attacker}

    resolved = resolve_webhook_user(
        {
            "customer_id": "ctm_attacker",
            "custom_data": {"centropic_user_id": "10"},
        },
        by_customer_id=lambda cid: attacker if cid == "ctm_attacker" else None,
        by_subscription_id=lambda sid: None,
        by_user_id=lambda uid: users.get(uid),
        customer_taken_by_other=lambda cid, uid: attacker if cid == "ctm_attacker" and uid != 20 else None,
    )
    assert resolved is attacker

    # First-bind hint still works when customer is unbound.
    unbound = resolve_webhook_user(
        {
            "customer_id": "ctm_new",
            "custom_data": {"centropic_user_id": "10"},
        },
        by_customer_id=lambda cid: None,
        by_subscription_id=lambda sid: None,
        by_user_id=lambda uid: users.get(uid),
        customer_taken_by_other=lambda cid, uid: None,
    )
    assert unbound is victim


def test_enqueue_dedupe_raises_under_active_check():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"dedupe-{uuid4().hex}@example.com",
            name="Dedupe",
            plan="plus",
            credit_balance_cents=5000,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        url = f"https://dedupe-{uuid4().hex}.example/"
        first = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url=url,
            max_pages=2,
        )
        with pytest.raises(DuplicateAnalyzeJobError) as exc:
            enqueue_analysis(
                db.session,
                AnalysisJob,
                user_id=user.id,
                url=url,
                max_pages=2,
                active_check=lambda: active_analyze_job_for_url(user.id, url),
            )
        assert exc.value.job.id == first.id


def test_reclaim_recovers_site_id_after_persist_crash_window():
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"reclaim2-{uuid4().hex}@example.com",
            name="Reclaim2",
            plan="plus",
            credit_balance_cents=5000,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        url = f"https://reclaim2-{uuid4().hex}.example/"
        site = SiteAnalysis(
            user_id=user.id,
            url=url,
            domain="reclaim2.example",
            aio_score=10,
            geo_score=10,
            findings_json="[]",
            updated_at=datetime.now(timezone.utc),
        )
        db.session.add(site)
        db.session.commit()
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url=url,
            max_pages=2,
        )
        job.status = "running"
        job.lease_token = "deadbeef"
        job.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        job.site_id = None
        job.billed_cents = 0
        db.session.commit()

        n = reclaim_stale_jobs(db.session, AnalysisJob, SiteAnalysis=SiteAnalysis)
        assert n >= 1
        row = db.session.get(AnalysisJob, job.id)
        assert row.status == "done"
        assert row.site_id == site.id


def test_dispatch_alerts_skips_free_after_downgrade():
    user = SimpleNamespace(
        id=1,
        email="free@example.com",
        plan="free",
        is_pro=False,
        is_admin=False,
        alert_email_enabled=True,
        webhook_url="https://example.com/hook",
        webhook_secret="sec",
    )
    site = SimpleNamespace(domain="example.com", url="https://example.com/")
    findings = [
        {
            "severity": "critical",
            "title": "Alert: regressione score",
            "detail": "drop",
            "category": "diff",
        }
    ]
    result = dispatch_alerts(user=user, site=site, findings=findings)
    assert result.get("skipped") == "entitlement"
    assert result.get("email") is None
    assert result.get("webhook") is None


def test_grant_plus_monthly_tokens_fails_closed_without_ledger_index(monkeypatch):
    from app import LedgerIndexMissingError, grant_plus_monthly_tokens

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"grant-{uuid4().hex}@example.com",
            name="Grant",
            plan="plus",
            credit_balance_cents=0,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        monkeypatch.setattr("app.CREDIT_LEDGER_PI_INDEX_OK", False, raising=False)
        with pytest.raises(LedgerIndexMissingError):
            grant_plus_monthly_tokens(
                user=user,
                idempotency_key=f"paddle-plus-tokens:test-{uuid4().hex}",
            )
        db.session.refresh(user)
        assert int(user.credit_balance_cents or 0) == 0


def test_health_marks_degraded_on_stale_jobs(monkeypatch):
    with app.app_context():
        ensure_schema()
    monkeypatch.setenv("CENTROPIC_SKIP_PROD_GUARDS", "1")
    monkeypatch.setattr(
        "centropic.ops_health.job_queue_snapshot",
        lambda *a, **k: {
            "pending": 1,
            "running": 1,
            "stale_running": 2,
            "stale_after_minutes": 12,
        },
    )
    client = app.test_client()
    body = client.get("/health").get_json()
    assert body["ok"] is True
    assert body["degraded"] is True
    assert "stale_jobs" in body["degraded_reasons"]
