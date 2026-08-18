"""Detailed health payload exposes queue pressure without leaking publicly."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app import AnalysisJob, User, app, db, ensure_schema


def _csrf_from_html(html: str) -> str:
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="csrf_token"',
        html,
    )
    assert match, "csrf_token field not found in HTML"
    return match.group(1) or match.group(2)


def test_health_detail_is_read_only_snapshot(monkeypatch):
    suffix = uuid4().hex
    now = datetime.now(timezone.utc)
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"health-jobs-{suffix}@example.com",
            name="Health Jobs",
            plan="plus",
        )
        user.set_password("HealthTest!23456")
        db.session.add(user)
        db.session.flush()
        db.session.add_all(
            [
                AnalysisJob(
                    user_id=user.id,
                    url=f"https://pending-{suffix}.example.com/",
                    status="pending",
                ),
                AnalysisJob(
                    user_id=user.id,
                    url=f"https://stale-{suffix}.example.com/",
                    status="running",
                    lease_token=f"stale-{suffix}",
                    heartbeat_at=now - timedelta(hours=1),
                    started_at=now - timedelta(hours=1),
                ),
                AnalysisJob(
                    user_id=user.id,
                    url=f"https://fresh-{suffix}.example.com/",
                    status="running",
                    lease_token=f"fresh-{suffix}",
                    heartbeat_at=now,
                    started_at=now,
                ),
            ]
        )
        db.session.commit()

    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", f"health-{suffix}")
    client = app.test_client()

    public_payload = client.get("/health").get_json()
    assert "jobs" not in public_payload

    detail = client.get(f"/health?token=health-{suffix}").get_json()
    # GET /health is read-only: stale running stays visible until ops reclaim.
    assert detail["jobs"]["pending"] >= 1
    assert detail["jobs"]["running"] >= 2
    assert detail["jobs"]["stale_running"] >= 1
    assert "jobs_reclaimed" not in detail
    assert detail["jobs"]["stale_after_minutes"] >= 5


def test_ops_reclaim_jobs_releases_stale(monkeypatch):
    suffix = uuid4().hex
    now = datetime.now(timezone.utc)
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"ops-reclaim-{suffix}@example.com",
            name="Ops Reclaim",
            plan="plus",
            credit_balance_cents=10_000,
            credit_held_cents=200,
        )
        user.set_password("HealthTest!23456")
        db.session.add(user)
        db.session.flush()
        job = AnalysisJob(
            user_id=user.id,
            url=f"https://stale-ops-{suffix}.example.com/",
            status="running",
            lease_token=f"stale-ops-{suffix}",
            heartbeat_at=now - timedelta(hours=1),
            started_at=now - timedelta(hours=1),
            attempt_count=99,
            held_cents=200,
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id
        user_id = user.id

    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", f"ops-{suffix}")
    client = app.test_client()
    denied = client.post("/ops/reclaim-jobs")
    assert denied.status_code == 403

    ok = client.post(f"/ops/reclaim-jobs?token=ops-{suffix}").get_json()
    assert ok["ok"] is True
    assert ok["jobs_reclaimed"] >= 1

    with app.app_context():
        row = db.session.get(AnalysisJob, job_id)
        assert row is not None
        assert row.status == "error"
        assert int(row.held_cents or 0) == 0
        owner = db.session.get(User, user_id)
        assert int(owner.credit_held_cents or 0) == 0


def test_ops_reclaim_admin_session_requires_csrf(monkeypatch):
    """Admin cookie without CSRF fails; with csrf_token succeeds."""
    suffix = uuid4().hex
    now = datetime.now(timezone.utc)
    monkeypatch.delenv("HEALTH_DETAIL_TOKEN", raising=False)

    with app.app_context():
        ensure_schema()
        admin = User(
            email=f"ops-admin-{suffix}@example.com",
            name="Ops Admin",
            plan="admin",
            role="admin",
            credit_balance_cents=10_000,
            credit_held_cents=150,
        )
        admin.set_password("HealthTest!23456")
        if hasattr(admin, "welcome_credit_granted"):
            admin.welcome_credit_granted = True
        db.session.add(admin)
        db.session.flush()
        job = AnalysisJob(
            user_id=admin.id,
            url=f"https://stale-admin-{suffix}.example.com/",
            status="running",
            lease_token=f"stale-admin-{suffix}",
            heartbeat_at=now - timedelta(hours=1),
            started_at=now - timedelta(hours=1),
            attempt_count=99,
            held_cents=150,
        )
        db.session.add(job)
        db.session.commit()
        admin_id = int(admin.id)
        job_id = int(job.id)
        session_ver = int(getattr(admin, "session_version", 0) or 0)

    client = app.test_client()

    # Mint CSRF from login form (anonymous), then attach admin session.
    login_html = client.get("/login").get_data(as_text=True)
    csrf_val = _csrf_from_html(login_html)

    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["session_version"] = session_ver

    no_csrf = client.post("/ops/reclaim-jobs")
    assert no_csrf.status_code == 400
    assert (no_csrf.get_json() or {}).get("error") == "csrf_failed"

    ok = client.post("/ops/reclaim-jobs", data={"csrf_token": csrf_val})
    assert ok.status_code == 200, ok.get_data(as_text=True)
    body = ok.get_json()
    assert body["ok"] is True
    assert body["jobs_reclaimed"] >= 1

    with app.app_context():
        row = db.session.get(AnalysisJob, job_id)
        assert row is not None
        assert row.status == "error"
