"""DB-backed analysis job queue (no Redis required)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Job stuck in "running" longer than this are re-queued (worker crash / hang).
STALE_RUNNING_MINUTES = 25


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


def reclaim_stale_jobs(
    db_session,
    AnalysisJob,
    *,
    older_than_minutes: int = STALE_RUNNING_MINUTES,
) -> int:
    """Re-queue jobs stuck in running (lost worker). Returns count reclaimed."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(5, older_than_minutes))
    stale = (
        AnalysisJob.query.filter(
            AnalysisJob.status == "running",
            AnalysisJob.started_at.isnot(None),
            AnalysisJob.started_at < cutoff,
        )
        .limit(50)
        .all()
    )
    n = 0
    for job in stale:
        job.status = "pending"
        job.started_at = None
        job.error = None
        n += 1
        logger.warning("Reclaimed stale analysis job %s (url=%s)", job.id, job.url)
    if n:
        db_session.commit()
    return n


def claim_next_job(db_session, AnalysisJob) -> Any | None:
    """Claim atomico: solo un worker vince l'UPDATE condizionale su status=pending."""
    try:
        reclaim_stale_jobs(db_session, AnalysisJob)
    except Exception:
        logger.exception("reclaim_stale_jobs failed")
        db_session.rollback()

    now = datetime.now(timezone.utc)
    # Fino a 3 tentativi in caso di race stretta tra worker.
    for _ in range(3):
        job = (
            AnalysisJob.query.filter_by(status="pending")
            .order_by(AnalysisJob.created_at.asc())
            .first()
        )
        if job is None:
            return None
        # Optimistic lock: aggiorna solo se ancora pending.
        updated = (
            AnalysisJob.query.filter_by(id=job.id, status="pending")
            .update(
                {
                    "status": "running",
                    "started_at": now,
                    "error": None,
                },
                synchronize_session=False,
            )
        )
        db_session.commit()
        if updated == 1:
            return db_session.get(AnalysisJob, job.id)
        # Perso la race: ritenta sul prossimo pending.
        db_session.rollback()
    return None


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
