"""DB-backed analysis job queue (no Redis required)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

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
    """Claim atomico: solo un worker vince l'UPDATE condizionale su status=pending."""
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


def claim_next_job_sql(db_session, AnalysisJob) -> Any | None:
    """Variante SQL (SQLite RETURNING) — usata dai test / fallback esplicito."""
    now = datetime.now(timezone.utc)
    try:
        row = db_session.execute(
            text(
                """
                UPDATE analysis_jobs
                SET status = 'running',
                    started_at = :now,
                    error = NULL
                WHERE id = (
                    SELECT id FROM analysis_jobs
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 1
                )
                RETURNING id
                """
            ),
            {"now": now.isoformat()},
        ).fetchone()
        db_session.commit()
    except Exception:
        db_session.rollback()
        logger.exception("claim_next_job_sql failed; falling back")
        return claim_next_job(db_session, AnalysisJob)
    if not row:
        return None
    return db_session.get(AnalysisJob, row[0])


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
