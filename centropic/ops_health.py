"""Ops health helpers — extracted from the HTTP monolith for reuse/tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def job_queue_snapshot(
    AnalysisJob: Any,
    *,
    stale_after_minutes: int = 15,
    func: Any = None,
    or_: Any = None,
) -> dict[str, int]:
    """Return pending/running counts and stale running jobs for /health detail.

    A running job is stale when it has no lease token, or its last heartbeat
    (or start/create time) is older than ``stale_after_minutes``.
    """
    if func is None or or_ is None:
        from sqlalchemy import func as sa_func
        from sqlalchemy import or_ as sa_or

        func = sa_func
        or_ = sa_or

    stale_cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=max(1, int(stale_after_minutes))
    )
    pending = AnalysisJob.query.filter_by(status="pending").count()
    running = AnalysisJob.query.filter_by(status="running").count()
    stale_running = AnalysisJob.query.filter(
        AnalysisJob.status == "running",
        or_(
            AnalysisJob.lease_token.is_(None),
            AnalysisJob.lease_token == "",
            func.coalesce(
                AnalysisJob.heartbeat_at,
                AnalysisJob.started_at,
                AnalysisJob.created_at,
            )
            < stale_cutoff,
        ),
    ).count()
    return {
        "pending": pending,
        "running": running,
        "stale_running": stale_running,
        "stale_after_minutes": int(stale_after_minutes),
    }
