"""Unit tests for extracted ops health helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app import AnalysisJob, User, app, db, ensure_schema
from centropic.ops_health import analyze_activity_snapshot, job_queue_snapshot


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


def test_analyze_activity_snapshot_splits_fixture_errors():
    suffix = uuid4().hex
    now = datetime.now(timezone.utc)
    with app.app_context():
        ensure_schema()
        live = User(
            email=f"live-{suffix}@example.com",
            name="Live",
            plan="plus",
            email_verified_at=now,
        )
        live.set_password("LiveOps!23456")
        stress = User(
            email=f"cap-{suffix}@stress.invalid",
            name="Stress",
            plan="business",
            email_verified_at=now,
        )
        stress.set_password("StressOps!23456")
        db.session.add_all([live, stress])
        db.session.flush()
        db.session.add_all(
            [
                AnalysisJob(
                    user_id=live.id,
                    url=f"https://done-{suffix}.example.com/",
                    status="done",
                    finished_at=now - timedelta(hours=5),
                    created_at=now - timedelta(hours=5),
                ),
                AnalysisJob(
                    user_id=live.id,
                    url=f"https://err-{suffix}.example.com/",
                    status="error",
                    error="SSL handshake failed",
                ),
                AnalysisJob(
                    user_id=stress.id,
                    url=f"https://stress-{suffix}.example.com/",
                    status="error",
                    error="claim-cap-clean",
                ),
            ]
        )
        db.session.commit()
        snap = analyze_activity_snapshot(AnalysisJob, User, now=now)
        assert snap["last_done_at"]
        assert snap["last_done_age_hours"] is not None
        assert snap["error_total"] >= 2
        assert snap["error_fixture"] >= 1
        assert snap["error_excl_fixture"] >= 1
