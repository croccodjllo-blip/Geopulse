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
    measured_pending = 0
    measured_running = 0
    if hasattr(AnalysisJob, "source"):
        measured_pending = AnalysisJob.query.filter_by(
            status="pending", source="measured"
        ).count()
        measured_running = AnalysisJob.query.filter_by(
            status="running", source="measured"
        ).count()
    out = {
        "pending": pending,
        "running": running,
        "stale_running": stale_running,
        "stale_after_minutes": int(stale_after_minutes),
        "measured_pending": measured_pending,
        "measured_running": measured_running,
    }
    try:
        from services.analyze_queue import queue_depth
        from services.measured_queue import (
            measured_queue_depth,
            measured_slots_in_use,
            max_concurrent_measured,
        )

        out["crawl_queue_depth"] = queue_depth()
        out["measured_queue_depth"] = measured_queue_depth()
        out["measured_slots_in_use"] = measured_slots_in_use()
        out["measured_slots_cap"] = max_concurrent_measured()
    except Exception:
        pass
    return out
