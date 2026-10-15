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


def _fixture_error_clause(AnalysisJob: Any, User: Any, or_: Any) -> Any:
    """Stress/capacity fixtures — keep rows, exclude from 'live error' counts."""
    return or_(
        User.email.ilike("%@stress.invalid"),
        AnalysisJob.error.ilike("%stress%"),
        AnalysisJob.error == "claim-cap-clean",
    )


def analyze_activity_snapshot(
    AnalysisJob: Any,
    User: Any,
    *,
    now: datetime | None = None,
    window_days: int = 14,
    func: Any = None,
    or_: Any = None,
) -> dict[str, Any]:
    """Last successful analyze + error split (fixture vs other). Never mutates."""
    if func is None or or_ is None:
        from sqlalchemy import func as sa_func
        from sqlalchemy import or_ as sa_or

        func = sa_func
        or_ = sa_or

    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=max(1, int(window_days)))
    last = (
        AnalysisJob.query.filter(AnalysisJob.status == "done")
        .order_by(
            func.coalesce(AnalysisJob.finished_at, AnalysisJob.created_at).desc()
        )
        .first()
    )
    last_at = None
    if last is not None:
        last_at = getattr(last, "finished_at", None) or getattr(last, "created_at", None)
        if last_at is not None and getattr(last_at, "tzinfo", None) is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
    age_hours: int | None = None
    if last_at is not None:
        age_hours = max(0, int((now - last_at).total_seconds() // 3600))

    done_window = AnalysisJob.query.filter(
        AnalysisJob.status == "done",
        AnalysisJob.created_at >= since,
    ).count()
    error_total = AnalysisJob.query.filter_by(status="error").count()
    error_fixture = (
        AnalysisJob.query.outerjoin(User, AnalysisJob.user_id == User.id)
        .filter(AnalysisJob.status == "error")
        .filter(_fixture_error_clause(AnalysisJob, User, or_))
        .count()
    )
    return {
        "last_done_at": last_at.isoformat() if last_at is not None else None,
        "last_done_age_hours": age_hours,
        "done_14d": int(done_window),
        "error_total": int(error_total),
        "error_fixture": int(error_fixture),
        "error_excl_fixture": int(max(0, error_total - error_fixture)),
    }
