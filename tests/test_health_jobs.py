"""Detailed health payload exposes queue pressure without leaking publicly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app import AnalysisJob, User, app, db, ensure_schema


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
