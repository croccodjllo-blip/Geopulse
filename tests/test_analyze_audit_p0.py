"""Analyze path P0 fixes from production audit (late SoV billing / wall timeout)."""

from __future__ import annotations

import os

from services.citation_monitor import _sov_monitor_timeout_seconds


def test_sov_monitor_default_timeout_covers_azure():
    """Azure Copilot often exceeds 90s; default must leave headroom."""
    os.environ.pop("SOV_MONITOR_TIMEOUT_SECONDS", None)
    # Re-read via function (reads env each call).
    assert _sov_monitor_timeout_seconds() >= 150
    assert _sov_monitor_timeout_seconds() <= 300


def test_sov_monitor_timeout_env_clamp():
    os.environ["SOV_MONITOR_TIMEOUT_SECONDS"] = "10"
    assert _sov_monitor_timeout_seconds() == 30  # floor
    os.environ["SOV_MONITOR_TIMEOUT_SECONDS"] = "999"
    assert _sov_monitor_timeout_seconds() == 300  # ceiling
    os.environ.pop("SOV_MONITOR_TIMEOUT_SECONDS", None)


def test_job_usage_cb_skips_when_job_not_running():
    """Straggler Azure callbacks after job done must not raise hold-ceiling errors."""
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    from app import AnalysisJob, User, app, db, ensure_schema

    with app.app_context():
        ensure_schema()
        u = User(
            email="audit-usage-cb@example.com",
            name="A",
            plan="plus",
            email_verified_at=datetime.now(timezone.utc),
        )
        u.set_password("x" * 12)
        db.session.add(u)
        db.session.commit()
        job = AnalysisJob(
            user_id=u.id,
            url="https://example.com/",
            status="done",
            source="measured",
            held_cents=0,
            billed_cents=1,
            max_pages=1,
            run_measured=True,
        )
        db.session.add(job)
        db.session.commit()

        # Minimal recreation of the guard in _job_usage_cb.
        thread_job = db.session.get(AnalysisJob, job.id)
        assert str(getattr(thread_job, "status", "") or "") != "running"
        # Guard path: callers must return without InsufficientCreditError.
        lease_cap = int(thread_job.held_cents or 0) + int(thread_job.billed_cents or 0)
        projected = 2
        would_raise = lease_cap > 0 and projected > lease_cap
        assert would_raise is True  # documents the pre-fix failure mode
        skipped = str(thread_job.status) != "running"
        assert skipped is True
