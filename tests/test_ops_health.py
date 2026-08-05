"""Unit tests for extracted ops health helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app import AnalysisJob, User, app, db, ensure_schema
from centropic.ops_health import job_queue_snapshot


def test_job_queue_snapshot_counts_stale_running():
    suffix = uuid4().hex
    now = datetime.now(timezone.utc)
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"ops-health-{suffix}@example.com",
            name="Ops",
            plan="plus",
        )
        user.set_password("OpsHealth!23456")
        db.session.add(user)
        db.session.flush()
        db.session.add_all(
            [
                AnalysisJob(
                    user_id=user.id,
                    url=f"https://p-{suffix}.example.com/",
                    status="pending",
                ),
                AnalysisJob(
                    user_id=user.id,
                    url=f"https://s-{suffix}.example.com/",
                    status="running",
                    lease_token=f"s-{suffix}",
                    heartbeat_at=now - timedelta(hours=2),
                    started_at=now - timedelta(hours=2),
                ),
            ]
        )
        db.session.commit()
        snap = job_queue_snapshot(AnalysisJob, stale_after_minutes=15)
        assert snap["pending"] >= 1
        assert snap["running"] >= 1
        assert snap["stale_running"] >= 1
        assert snap["stale_after_minutes"] == 15
