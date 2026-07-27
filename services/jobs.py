"""DB-backed analysis job queue (no Redis required)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def enqueue_analysis(
    db_session,
    AnalysisJob,
    *,
    user_id: int,
    url: str,
    max_pages: int,
    competitor_urls: list[str] | None = None,
) -> Any:
    job = AnalysisJob(
        user_id=user_id,
        url=url,
        max_pages=max_pages,
        competitors_json=json.dumps(competitor_urls or [], ensure_ascii=False),
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    return job


def claim_next_job(db_session, AnalysisJob) -> Any | None:
    job = (
        AnalysisJob.query.filter_by(status="pending")
        .order_by(AnalysisJob.created_at.asc())
        .first()
    )
    if not job:
        return None
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.error = None
    db_session.commit()
    return job


def complete_job(db_session, job, *, site_id: int | None = None) -> None:
    job.status = "done"
    job.finished_at = datetime.now(timezone.utc)
    job.site_id = site_id
    job.error = None
    db_session.commit()


def fail_job(db_session, job, error: str) -> None:
    job.status = "error"
    job.finished_at = datetime.now(timezone.utc)
    job.error = (error or "errore")[:500]
    db_session.commit()
