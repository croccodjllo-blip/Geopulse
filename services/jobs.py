"""DB-backed analysis job queue (no Redis required)."""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Reclaim only when heartbeat (or started_at) is older than this.
# Heartbeat should be refreshed during long crawls so live jobs are not stolen.
STALE_HEARTBEAT_MINUTES = max(5, int(os.getenv("JOB_STALE_HEARTBEAT_MINUTES", "12")))
MAX_JOB_ATTEMPTS = max(1, int(os.getenv("JOB_MAX_ATTEMPTS", "2")))


def enqueue_analysis(
    db_session,
    AnalysisJob,
    *,
    user_id: int,
    url: str,
    max_pages: int,
    competitor_urls: list[str] | None = None,
    run_measured: bool = False,
    held_cents: int = 0,
) -> Any:
    kwargs: dict[str, Any] = {
        "user_id": user_id,
        "url": url,
        "max_pages": max_pages,
        "competitors_json": json.dumps(competitor_urls or [], ensure_ascii=False),
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "attempt_count": 0,
        "held_cents": max(0, int(held_cents or 0)),
    }
    if hasattr(AnalysisJob, "run_measured"):
        kwargs["run_measured"] = bool(run_measured)
    job = AnalysisJob(**kwargs)
    db_session.add(job)
    db_session.commit()
    return job


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def job_lease_owns(job: Any, *, token: str | None = None) -> bool:
    """True if ``job`` is still running under the given (or current) lease."""
    expected = token if token is not None else getattr(job, "lease_token", None)
    if not expected:
        return False
    return (
        getattr(job, "status", None) == "running"
        and getattr(job, "lease_token", None) == expected
    )


def reclaim_stale_jobs(
    db_session,
    AnalysisJob,
    *,
    older_than_minutes: int = STALE_HEARTBEAT_MINUTES,
    on_abandon: Callable[[Any], None] | None = None,
) -> int:
    """Re-queue jobs whose lease heartbeat expired (lost worker).

    Live workers must call ``heartbeat_job``; without heartbeats a job is
    treated as abandoned. After ``MAX_JOB_ATTEMPTS`` the job fails permanently
    instead of looping forever.

    ``on_abandon(job)`` is invoked for permanent failures (e.g. release credit
    holds) before the reclaim commit.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(5, older_than_minutes))
    stale = (
        AnalysisJob.query.filter(AnalysisJob.status == "running")
        .limit(50)
        .all()
    )
    n = 0
    for job in stale:
        # Running without a lease is always reclaimable (zombie / legacy claim).
        token = getattr(job, "lease_token", None)
        beat = _as_utc(getattr(job, "heartbeat_at", None) or job.started_at)
        if token and (beat is None or beat >= cutoff):
            continue
        if not token:
            logger.warning(
                "Reclaiming running job %s with missing lease_token", job.id
            )
        attempts = int(getattr(job, "attempt_count", 0) or 0)
        billed = int(getattr(job, "billed_cents", 0) or 0)
        # Soft reclaim after partial billing would re-run the pipeline and
        # double-charge. Fail permanently and release remaining hold instead.
        if billed > 0 and attempts < MAX_JOB_ATTEMPTS:
            job.status = "error"
            job.finished_at = datetime.now(timezone.utc)
            job.lease_token = None
            job.error = (
                "Job interrotto dopo addebito parziale "
                "(worker perso / timeout heartbeat) — non rieseguito per evitare doppia fatturazione."
            )[:500]
            if on_abandon is not None:
                try:
                    on_abandon(job)
                except Exception:
                    logger.exception("on_abandon failed for billed job %s", job.id)
            else:
                if hasattr(job, "held_cents"):
                    job.held_cents = 0
            logger.error(
                "Permanently failed partially-billed stale job %s (billed=%s)",
                job.id,
                billed,
            )
            n += 1
            continue
        if attempts >= MAX_JOB_ATTEMPTS:
            job.status = "error"
            job.finished_at = datetime.now(timezone.utc)
            job.lease_token = None
            job.error = (
                f"Job abbandonato dopo {attempts} tentativi "
                "(worker perso / timeout heartbeat)."
            )[:500]
            if on_abandon is not None:
                try:
                    on_abandon(job)
                except Exception:
                    logger.exception("on_abandon failed for job %s", job.id)
            else:
                # Ensure hold marker is cleared even without a release callback.
                if hasattr(job, "held_cents"):
                    job.held_cents = 0
            logger.error(
                "Permanently failed stale job %s after %s attempts", job.id, attempts
            )
            n += 1
            continue
        job.status = "pending"
        job.started_at = None
        job.heartbeat_at = None
        job.lease_token = None
        job.error = None
        n += 1
        logger.warning(
            "Reclaimed stale analysis job %s (url=%s attempts=%s)",
            job.id,
            job.url,
            attempts,
        )
    if n:
        db_session.commit()
    return n


def claim_next_job(
    db_session,
    AnalysisJob,
    *,
    on_abandon: Callable[[Any], None] | None = None,
) -> Any | None:
    """Claim atomico: solo un worker vince l'UPDATE condizionale su status=pending."""
    try:
        reclaim_stale_jobs(db_session, AnalysisJob, on_abandon=on_abandon)
    except Exception:
        logger.exception("reclaim_stale_jobs failed")
        db_session.rollback()

    now = datetime.now(timezone.utc)
    lease = secrets.token_hex(16)
    for _ in range(3):
        job = (
            AnalysisJob.query.filter_by(status="pending")
            .order_by(AnalysisJob.created_at.asc())
            .first()
        )
        if job is None:
            return None
        attempts = int(getattr(job, "attempt_count", 0) or 0) + 1
        claim_fields = {
            "status": "running",
            "started_at": now,
            "heartbeat_at": now,
            "lease_token": lease,
            "attempt_count": attempts,
            "error": None,
        }
        if hasattr(job, "progress_done"):
            claim_fields["progress_done"] = 0
            claim_fields["progress_total"] = 0
            claim_fields["progress_phase"] = "crawl"
        updated = (
            AnalysisJob.query.filter_by(id=job.id, status="pending")
            .update(claim_fields, synchronize_session=False)
        )
        db_session.commit()
        if updated == 1:
            claimed = db_session.get(AnalysisJob, job.id)
            return claimed
        db_session.rollback()
    return None


def heartbeat_job(
    db_session,
    job,
    *,
    progress_done: int | None = None,
    progress_total: int | None = None,
    progress_phase: str | None = None,
) -> bool:
    """Refresh lease heartbeat for a running job owned by this worker.

    Optional crawl/stage progress fields power the overlay ETA.
    """
    Job = job.__class__
    token = getattr(job, "lease_token", None)
    if not token:
        return False
    now = datetime.now(timezone.utc)
    fields: dict[str, Any] = {"heartbeat_at": now}
    if progress_done is not None and hasattr(job, "progress_done"):
        fields["progress_done"] = max(0, int(progress_done))
    if progress_total is not None and hasattr(job, "progress_total"):
        fields["progress_total"] = max(0, int(progress_total))
    if progress_phase is not None and hasattr(job, "progress_phase"):
        fields["progress_phase"] = str(progress_phase)[:20]
    updated = (
        Job.query.filter_by(id=job.id, status="running", lease_token=token)
        .update(fields, synchronize_session=False)
    )
    if updated == 1:
        db_session.commit()
        job.heartbeat_at = now
        if "progress_done" in fields:
            job.progress_done = fields["progress_done"]
        if "progress_total" in fields:
            job.progress_total = fields["progress_total"]
        if "progress_phase" in fields:
            job.progress_phase = fields["progress_phase"]
        return True
    db_session.rollback()
    return False


def complete_job(
    db_session,
    job,
    *,
    site_id: int | None = None,
    lease_token: str | None = None,
) -> bool:
    """Mark job done only if this worker still owns the lease.

    Prevents a zombie worker (lease reclaimed) from finishing after a new
    worker already claimed the same job.
    """
    Job = job.__class__
    token = lease_token if lease_token is not None else getattr(job, "lease_token", None)
    if not token:
        logger.warning("complete_job refused: missing lease for job %s", getattr(job, "id", "?"))
        return False
    now = datetime.now(timezone.utc)
    updated = (
        Job.query.filter_by(id=job.id, status="running", lease_token=token)
        .update(
            {
                "status": "done",
                "finished_at": now,
                "site_id": site_id,
                "error": None,
                "lease_token": None,
                "heartbeat_at": now,
            },
            synchronize_session=False,
        )
    )
    db_session.commit()
    if updated == 1:
        job.status = "done"
        job.lease_token = None
        return True
    logger.warning(
        "complete_job lost race for job %s (lease=%s…)",
        getattr(job, "id", "?"),
        token[:8],
    )
    return False


def fail_job(
    db_session,
    job,
    error: str,
    *,
    require_lease: bool = True,
) -> bool:
    """Mark job error from pending/running.

    When ``require_lease`` is True (worker path), a running job must still
    own ``lease_token``. Pending jobs without a lease are allowed so system
    paths can fail unclaimed work. Admin cancel should use ``require_lease=False``
    or its own update.
    """
    Job = job.__class__
    now = datetime.now(timezone.utc)
    token = getattr(job, "lease_token", None)
    q = Job.query.filter(
        Job.id == job.id,
        Job.status.in_(("pending", "running")),
    )
    if require_lease:
        if token:
            q = q.filter(Job.lease_token == token)
        else:
            # Only unclaimed pending jobs may fail without a lease.
            q = q.filter(Job.status == "pending")
    updated = q.update(
        {
            "status": "error",
            "finished_at": now,
            "error": (error or "errore")[:500],
            "lease_token": None,
        },
        synchronize_session=False,
    )
    db_session.commit()
    if updated == 1:
        job.status = "error"
        job.error = (error or "errore")[:500]
        job.lease_token = None
        return True
    return False
