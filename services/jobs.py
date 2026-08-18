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
# Heartbeat is refreshed during crawl/SoV; 2–5 min silence ⇒ lost worker (deploy/OOM).
# Keep the floor at 2 so a deploy mid-SoV does not strand the UI for 12+ minutes.
STALE_HEARTBEAT_MINUTES = max(2, int(os.getenv("JOB_STALE_HEARTBEAT_MINUTES", "12")))
MAX_JOB_ATTEMPTS = max(1, int(os.getenv("JOB_MAX_ATTEMPTS", "2")))
# Global in-flight cap across all tenants (0 = unlimited). Claim returns None when full.
# Global in-flight cap across tenants (crawl + measured). Target ≈100+100.
MAX_RUNNING_ANALYZE_JOBS = max(0, int(os.getenv("MAX_RUNNING_ANALYZE_JOBS", "200")))
# Postgres advisory lock key for serialize(count running + claim).
_CLAIM_ADVISORY_LOCK_KEY = 872_341


def _acquire_claim_lock(db_session: Any) -> None:
    """Serialize global running-cap check + claim (Postgres only).

    ``pg_advisory_xact_lock`` is held until the current transaction commits —
    ``_finish_claim`` commits, so the next waiter sees an up-to-date running count.
    No-op on SQLite / non-Postgres.
    """
    try:
        from sqlalchemy import text

        bind = db_session.get_bind()
        dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""
        if dialect != "postgresql":
            return
        db_session.execute(
            text("SELECT pg_advisory_xact_lock(:k)"),
            {"k": _CLAIM_ADVISORY_LOCK_KEY},
        )
    except Exception:
        logger.exception("claim advisory lock failed; continuing without it")


class DuplicateAnalyzeJobError(RuntimeError):
    """Raised when an active job already covers the same tenant URL."""

    def __init__(self, job: Any):
        self.job = job
        super().__init__(f"active analyze job already exists id={getattr(job, 'id', '?')}")


def _begin_immediate(db_session: Any) -> None:
    """Take a reserved write lock early (SQLite only; no-op on Postgres).

    Never emit ``BEGIN IMMEDIATE`` on Postgres: a syntax error aborts the
    transaction even if caught, and the next query raises InFailedSqlTransaction
    (analyze enqueue 500 on ``/dashboard/analyze/confirmed``).
    """
    from sqlalchemy import text

    bind = db_session.get_bind()
    dialect = getattr(getattr(bind, "dialect", None), "name", "") or ""
    if dialect != "sqlite":
        return
    db_session.execute(text("BEGIN IMMEDIATE"))


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
    source: str = "job",
    active_check: Callable[[], Any | None] | None = None,
    plan: str | None = None,
    is_admin: bool = False,
    locale: str | None = None,
) -> Any:
    """Enqueue a pending analyze job.

    When ``active_check`` is provided it runs under a reserved write lock and
    must return an existing active job (or ``None``). A non-None result raises
    ``DuplicateAnalyzeJobError`` so callers can release holds and reuse the job.

    ``plan`` / ``is_admin`` select the Redis priority lane (Business → Plus → Free).
    ``locale`` is the UI locale for pack copy (captured from the request when omitted).
    """
    _begin_immediate(db_session)
    if active_check is not None:
        dup = active_check()
        if dup is not None:
            raise DuplicateAnalyzeJobError(dup)
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
    if hasattr(AnalysisJob, "source"):
        src = (source or "job").strip().lower() or "job"
        kwargs["source"] = src[:20]
    if hasattr(AnalysisJob, "locale"):
        loc = (locale or "").strip()
        if not loc:
            try:
                from services.pack_i18n import capture_ui_locale

                loc = capture_ui_locale(None)
            except Exception:
                from services.i18n import DEFAULT_LOCALE

                loc = DEFAULT_LOCALE
        kwargs["locale"] = str(loc)[:8]
    job = AnalysisJob(**kwargs)
    db_session.add(job)
    db_session.commit()
    try:
        src = str(kwargs.get("source") or source or "job").strip().lower()
        if src == "measured":
            from services.measured_queue import dispatch_measured_job

            if dispatch_measured_job(
                int(job.id),
                plan=plan,
                is_admin=bool(is_admin),
            ):
                logger.info(
                    "measured job %s dispatched to measured queue plan=%s",
                    job.id,
                    plan or "plus",
                )
        else:
            from services.analyze_queue import dispatch_analyze_job

            if dispatch_analyze_job(
                int(job.id),
                plan=plan,
                is_admin=bool(is_admin),
            ):
                logger.info(
                    "analyze job %s dispatched to redis queue plan=%s",
                    job.id,
                    plan or "free",
                )
    except Exception:
        logger.exception("redis dispatch failed for job %s (DB pending still valid)", job.id)
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


def _job_already_persisted(job: Any) -> bool:
    """True when site_id was written before complete (persist succeeded)."""
    return bool(getattr(job, "site_id", None))


def release_stranded_holds(
    db_session,
    AnalysisJob,
    *,
    on_release: Callable[[Any], None],
    limit: int = 50,
) -> int:
    """Release holds left on terminal jobs when ``on_abandon`` previously failed."""
    stranded = (
        AnalysisJob.query.filter(
            AnalysisJob.status.in_(("error", "done")),
            AnalysisJob.held_cents > 0,
        )
        .limit(max(1, limit))
        .all()
    )
    n = 0
    for job in stranded:
        try:
            on_release(job)
            n += 1
        except Exception:
            logger.exception("release_stranded_holds failed for job %s", job.id)
    if n:
        db_session.commit()
    return n


def _resolve_persisted_site_id(
    job: Any,
    *,
    SiteAnalysis: Any | None,
) -> int | None:
    """If persist committed but ``job.site_id`` was never marked, recover it."""
    if SiteAnalysis is None:
        return None
    started = _as_utc(getattr(job, "started_at", None) or getattr(job, "created_at", None))
    if started is None:
        return None
    try:
        site = (
            SiteAnalysis.query.filter_by(
                user_id=int(job.user_id),
                url=str(job.url),
            )
            .order_by(SiteAnalysis.updated_at.desc())
            .first()
        )
    except Exception:
        logger.exception("resolve persisted site failed for job %s", getattr(job, "id", "?"))
        return None
    if site is None:
        return None
    updated = _as_utc(getattr(site, "updated_at", None) or getattr(site, "created_at", None))
    if updated is None:
        return None
    # Allow a small clock skew; persist must have happened during/after this attempt.
    if updated + timedelta(seconds=30) < started:
        return None
    return int(site.id)


def reclaim_stale_jobs(
    db_session,
    AnalysisJob,
    *,
    older_than_minutes: int = STALE_HEARTBEAT_MINUTES,
    on_abandon: Callable[[Any], None] | None = None,
    SiteAnalysis: Any | None = None,
) -> int:
    """Re-queue jobs whose lease heartbeat expired (lost worker).

    Live workers must call ``heartbeat_job``; without heartbeats a job is
    treated as abandoned. After ``MAX_JOB_ATTEMPTS`` the job fails permanently
    instead of looping forever.

    ``on_abandon(job)`` is invoked for permanent failures (e.g. release credit
    holds) before the reclaim commit. On callback failure the job keeps
    ``held_cents`` so ``release_stranded_holds`` can retry.

    When ``SiteAnalysis`` is provided, reclaim reconciles the crash window
    after ``persist_analysis`` committed but before ``mark_job_site``.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(2, older_than_minutes))
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

        def _call_abandon() -> None:
            if on_abandon is not None:
                try:
                    on_abandon(job)
                except Exception:
                    logger.exception("on_abandon failed for job %s", job.id)
                    # Keep held_cents so stranded-hold sweeper can retry.
                    return
            elif hasattr(job, "held_cents"):
                job.held_cents = 0

        # Recover site_id when persist won the race against mark_job_site.
        if not _job_already_persisted(job):
            recovered = _resolve_persisted_site_id(job, SiteAnalysis=SiteAnalysis)
            if recovered is not None:
                job.site_id = recovered

        # Soft reclaim after partial billing would re-run the pipeline and
        # double-charge. Fail permanently and release remaining hold instead —
        # unless persist already completed (deliverable exists).
        if billed > 0 and attempts < MAX_JOB_ATTEMPTS and not _job_already_persisted(job):
            job.status = "error"
            job.finished_at = datetime.now(timezone.utc)
            job.lease_token = None
            job.error = (
                "Job interrotto dopo addebito parziale "
                "(worker perso / timeout heartbeat) — non rieseguito per evitare doppia fatturazione. "
                "Il credito addebitato verrà rimborsato automaticamente."
            )[:500]
            _call_abandon()
            logger.error(
                "Permanently failed partially-billed stale job %s (billed=%s)",
                job.id,
                billed,
            )
            n += 1
            continue
        # Aggregate debit mode: measured jobs may have spent LLM before flush
        # (billed_cents still 0). Soft-reclaim would re-run probes — fail closed.
        held_left = int(getattr(job, "held_cents", 0) or 0)
        measuredish = bool(getattr(job, "run_measured", False)) or (
            str(getattr(job, "source", "") or "").lower() == "measured"
        )
        if (
            measuredish
            and held_left > 0
            and attempts >= 1
            and billed <= 0
            and not _job_already_persisted(job)
        ):
            try:
                from services.usage_billing import usage_debit_aggregate

                aggregate = usage_debit_aggregate()
            except Exception:
                aggregate = False
            if aggregate:
                job.status = "error"
                job.finished_at = datetime.now(timezone.utc)
                job.lease_token = None
                job.error = (
                    "Job measured interrotto prima del flush addebito "
                    "(worker perso / timeout) — non rieseguito per evitare doppia spesa LLM. "
                    "L’eventuale hold verrà rilasciato/rimborsato."
                )[:500]
                _call_abandon()
                logger.error(
                    "Permanently failed aggregate measured stale job %s (held=%s)",
                    job.id,
                    held_left,
                )
                n += 1
                continue
        # If persist already wrote a run for this attempt, mark done instead of
        # soft-reclaiming (avoids duplicate AnalysisRun when billed_cents==0).
        if _job_already_persisted(job):
            job.status = "done"
            job.finished_at = datetime.now(timezone.utc)
            job.lease_token = None
            job.error = None
            _call_abandon()
            logger.warning(
                "Reconciled stale job %s as done (persist already completed)",
                job.id,
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
            _call_abandon()
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
    SiteAnalysis: Any | None = None,
    preferred_job_id: int | None = None,
    source_filter: str | None = None,
    source_exclude: str | None = None,
) -> Any | None:
    """Claim atomico: solo un worker vince l'UPDATE condizionale su status=pending.

    When ``preferred_job_id`` is set (Redis pop), try that row first; if it was
    already claimed/cancelled, fall through to FIFO pending.

    ``source_filter`` limits FIFO to that source (e.g. measured workers).
    ``source_exclude`` skips a source on FIFO (e.g. crawl workers skip measured).
    """
    try:
        reclaim_stale_jobs(
            db_session,
            AnalysisJob,
            on_abandon=on_abandon,
            SiteAnalysis=SiteAnalysis,
        )
        if on_abandon is not None:
            release_stranded_holds(db_session, AnalysisJob, on_release=on_abandon)
    except Exception:
        logger.exception("reclaim_stale_jobs failed")
        db_session.rollback()

    # Hold xact lock through count + claim commit so two workers cannot both
    # pass a near-cap check and overshoot MAX_RUNNING_ANALYZE_JOBS.
    _acquire_claim_lock(db_session)

    if MAX_RUNNING_ANALYZE_JOBS > 0:
        running_n = AnalysisJob.query.filter_by(status="running").count()
        if running_n >= MAX_RUNNING_ANALYZE_JOBS:
            logger.info(
                "claim skipped: global running cap reached (%s/%s)",
                running_n,
                MAX_RUNNING_ANALYZE_JOBS,
            )
            try:
                db_session.rollback()  # release advisory lock without claiming
            except Exception:
                pass
            return None

    if preferred_job_id is not None:
        claimed = _try_claim_pending_id(
            db_session, AnalysisJob, int(preferred_job_id)
        )
        if claimed is not None:
            return claimed

    now = datetime.now(timezone.utc)
    lease = secrets.token_hex(16)
    for _ in range(3):
        q = AnalysisJob.query.filter_by(status="pending")
        if source_filter and hasattr(AnalysisJob, "source"):
            q = q.filter_by(source=str(source_filter))
        if source_exclude and hasattr(AnalysisJob, "source"):
            q = q.filter(AnalysisJob.source != str(source_exclude))
        job = q.order_by(AnalysisJob.created_at.asc()).first()
        if job is None:
            return None
        claimed = _finish_claim(db_session, AnalysisJob, job.id, lease=lease, now=now)
        if claimed is not None:
            return claimed
    return None


def _try_claim_pending_id(db_session, AnalysisJob, job_id: int) -> Any | None:
    now = datetime.now(timezone.utc)
    lease = secrets.token_hex(16)
    return _finish_claim(db_session, AnalysisJob, job_id, lease=lease, now=now)


def _finish_claim(
    db_session,
    AnalysisJob,
    job_id: int,
    *,
    lease: str,
    now: datetime,
) -> Any | None:
    attempts_row = db_session.get(AnalysisJob, job_id)
    if attempts_row is None or getattr(attempts_row, "status", None) != "pending":
        return None
    attempts = int(getattr(attempts_row, "attempt_count", 0) or 0) + 1
    claim_fields = {
        "status": "running",
        "started_at": now,
        "heartbeat_at": now,
        "lease_token": lease,
        "attempt_count": attempts,
        "error": None,
    }
    if hasattr(attempts_row, "progress_done"):
        claim_fields["progress_done"] = 0
        claim_fields["progress_total"] = 0
        claim_fields["progress_phase"] = "crawl"
    updated = (
        AnalysisJob.query.filter_by(id=job_id, status="pending").update(
            claim_fields, synchronize_session=False
        )
    )
    db_session.commit()
    if updated == 1:
        return db_session.get(AnalysisJob, job_id)
    db_session.rollback()
    return None


def heartbeat_job(
    db_session,
    job,
    *,
    progress_done: int | None = None,
    progress_total: int | None = None,
    progress_phase: str | None = None,
    lease_token: str | None = None,
) -> bool:
    """Refresh lease heartbeat for a running job owned by this worker.

    Pass ``lease_token=`` from claim time so a stale ORM reload after
    ``expire_on_commit`` cannot heartbeat under a stolen lease.

    Optional crawl/stage progress fields power the overlay ETA.
    """
    Job = job.__class__
    token = lease_token if lease_token is not None else getattr(job, "lease_token", None)
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


def mark_job_site(
    db_session,
    job,
    *,
    site_id: int,
    lease_token: str | None = None,
) -> bool:
    """Record site_id while lease is still owned (pre-complete safety)."""
    Job = job.__class__
    token = lease_token if lease_token is not None else getattr(job, "lease_token", None)
    if not token or not site_id:
        return False
    updated = (
        Job.query.filter_by(id=job.id, status="running", lease_token=token)
        .update({"site_id": int(site_id)}, synchronize_session=False)
    )
    if updated == 1:
        db_session.commit()
        job.site_id = int(site_id)
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
    # Never write site_id=NULL on complete — that would wipe mark_job_site
    # if the caller passes site_id=None after a successful persist.
    fields: dict[str, Any] = {
        "status": "done",
        "finished_at": now,
        "error": None,
        "lease_token": None,
        "heartbeat_at": now,
    }
    if site_id is not None:
        fields["site_id"] = int(site_id)
    updated = (
        Job.query.filter_by(id=job.id, status="running", lease_token=token)
        .update(fields, synchronize_session=False)
    )
    db_session.commit()
    if updated == 1:
        job.status = "done"
        job.lease_token = None
        if site_id is not None:
            job.site_id = int(site_id)
        return True
    # Idempotent reconcile: persist already completed but lease was stolen.
    if site_id and _job_already_persisted(job):
        forced = (
            Job.query.filter(
                Job.id == job.id,
                Job.status.in_(("running", "error", "pending")),
            ).update(
                {
                    "status": "done",
                    "finished_at": now,
                    "site_id": int(site_id),
                    "error": None,
                    "lease_token": None,
                    "heartbeat_at": now,
                },
                synchronize_session=False,
            )
        )
        db_session.commit()
        if forced == 1:
            job.status = "done"
            job.lease_token = None
            job.site_id = int(site_id)
            logger.warning(
                "complete_job reconciled job %s after lease loss (site_id=%s)",
                getattr(job, "id", "?"),
                site_id,
            )
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
    lease_token: str | None = None,
) -> bool:
    """Mark job error from pending/running.

    When ``require_lease`` is True (worker path), a running job must still
    own ``lease_token``. Pass ``lease_token=`` explicitly so a zombie worker
    does not autoflush a stale token onto a reclaimed row. Pending jobs
    without a lease are allowed so system paths can fail unclaimed work.
    Admin cancel should use ``require_lease=False`` or its own update.
    """
    Job = job.__class__
    now = datetime.now(timezone.utc)
    token = lease_token if lease_token is not None else getattr(job, "lease_token", None)
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
    # Avoid autoflush of a dirty in-memory lease_token overwriting a reclaim.
    with db_session.no_autoflush:
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
