"""Detailed health payload exposes queue pressure without leaking publicly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app import AnalysisJob, User, app, db, ensure_schema


def test_health_detail_includes_stale_running_jobs(monkeypatch):
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
    # Health detail reclaim_stale_jobs turns the abandoned lease into pending
    # (or error), so the snapshot after reclaim must not count it as running.
    assert detail["jobs"]["pending"] >= 2
    assert detail["jobs"]["running"] >= 1
    assert detail["jobs"]["stale_running"] == 0
    assert detail.get("jobs_reclaimed", 0) >= 1
    assert detail["jobs"]["stale_after_minutes"] >= 5
