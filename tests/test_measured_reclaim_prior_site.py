"""Measured reclaim must not treat a prior Stimato SiteAnalysis as persist-done."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-measured-reclaim")

from services.jobs import STALE_HEARTBEAT_MINUTES, reclaim_stale_jobs


def test_stale_heartbeat_default_is_fast_after_deploy():
    assert STALE_HEARTBEAT_MINUTES <= 5
    assert STALE_HEARTBEAT_MINUTES >= 2


def test_reclaim_measured_with_hold_fails_closed_despite_prior_site(monkeypatch):
    """Recovering site_id from an older Stimato row must not mark measured done."""
    monkeypatch.setenv("USAGE_DEBIT_MODE", "aggregate")
    # Force aggregate helper true even if env already loaded.
    monkeypatch.setattr(
        "services.usage_billing.usage_debit_aggregate",
        lambda: True,
    )

    stale_hb = datetime.now(timezone.utc) - timedelta(minutes=30)
    job = SimpleNamespace(
        id=922,
        status="running",
        url="https://centropic.ai/",
        user_id=20,
        attempt_count=1,
        billed_cents=0,
        held_cents=3,
        run_measured=True,
        source="measured",
        site_id=None,  # worker never marked site_id
        lease_token="deadbeef",
        started_at=stale_hb,
        heartbeat_at=stale_hb,
        finished_at=None,
        error=None,
    )

    class _Q:
        def filter(self, *a, **k):
            return self

        def limit(self, n):
            return self

        def all(self):
            return [job]

    AnalysisJob = SimpleNamespace(query=_Q(), status="status")
    # Prior Stimato site for same URL — must not count as this measured persist.
    prior_site = SimpleNamespace(id=23, updated_at=stale_hb)
    SiteAnalysis = MagicMock()
    SiteAnalysis.query.filter_by.return_value.order_by.return_value.first.return_value = (
        prior_site
    )

    abandoned: list[int] = []

    n = reclaim_stale_jobs(
        MagicMock(),
        AnalysisJob,
        older_than_minutes=2,
        on_abandon=lambda j: abandoned.append(j.id),
        SiteAnalysis=SiteAnalysis,
    )
    assert n == 1
    assert job.status == "error"
    assert "measured interrotto" in (job.error or "").lower() or "interrotto" in (
        job.error or ""
    )
    assert abandoned == [922]
    # May attach recovered site_id for ops, but must not reconcile as done.
    assert job.status != "done"
