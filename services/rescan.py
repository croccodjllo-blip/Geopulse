"""Re-scan periodico per siti Pro con schedule attivo."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from services.analyze_pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)

UsageCallback = Callable[..., None]
UsageCallbackFactory = Callable[[Any], UsageCallback]


def due_sites_query(SiteAnalysis: Any, User: Any, *, now: datetime | None = None):
    """Siti Pro/admin con interval attivo e next_rescan_at scaduto."""
    now = now or datetime.now(timezone.utc)
    return (
        SiteAnalysis.query.join(User, SiteAnalysis.user_id == User.id)
        .filter(
            SiteAnalysis.rescan_interval.in_(("daily", "weekly")),
            SiteAnalysis.next_rescan_at.isnot(None),
            SiteAnalysis.next_rescan_at <= now,
            User.plan.in_(("plus", "pro", "business", "admin")),
        )
        .order_by(SiteAnalysis.next_rescan_at.asc())
    )


def claim_due_site(
    db_session: Any,
    SiteAnalysis: Any,
    site_id: int,
    *,
    now: datetime | None = None,
    claim_horizon_hours: int = 20,
) -> bool:
    """Atomically claim a due site by advancing ``next_rescan_at``.

    Prevents overlapping rescan timer ticks from running the same site twice.
    Returns True only for the winner of the race.
    """
    now = now or datetime.now(timezone.utc)
    claimed_until = now + timedelta(hours=max(1, int(claim_horizon_hours)))
    n = (
        db_session.query(SiteAnalysis)
        .filter(
            SiteAnalysis.id == int(site_id),
            SiteAnalysis.next_rescan_at.isnot(None),
            SiteAnalysis.next_rescan_at <= now,
        )
        .update({"next_rescan_at": claimed_until}, synchronize_session=False)
    )
    if n:
        db_session.commit()
        return True
    db_session.rollback()
    return False


def process_due_rescans(
    *,
    db_session: Any,
    SiteAnalysis: Any,
    AnalysisRun: Any,
    User: Any,
    openai_api_key: str = "",
    openai_model: str = "gpt-4o-mini",
    limit: int = 20,
    daily_limit_for: Callable[[Any], int] | None = None,
    runs_today_for: Callable[[int], int] | None = None,
    measured: bool = False,
    public_base: str = "https://centropic.ai",
    SovSnapshot: Any | None = None,
    AlertDelivery: Any | None = None,
    usage_callback: UsageCallback | None = None,
    usage_callback_factory: UsageCallbackFactory | None = None,
) -> dict[str, int]:
    """Esegue i re-scan scaduti via pipeline completa (suite + alert).

    Billing:
      - Prefer ``usage_callback_factory(user)`` (per-owner debit).
      - Fallback ``usage_callback`` (shared).
      - Measured SoV requires a billing callback.
      - Pack/artifact LLM always receives the billing callback when present
        so OpenAI spend is never free on scheduled rescans.
    """
    from services.analysis_store import mark_rescan_error

    stats = {"ok": 0, "error": 0, "skipped": 0}
    now = datetime.now(timezone.utc)
    sites = due_sites_query(SiteAnalysis, User, now=now).limit(max(1, limit)).all()

    has_any_billing = callable(usage_callback_factory) or callable(usage_callback)
    if measured and not has_any_billing:
        logger.warning(
            "Scheduled measured SoV disabled: no usage_callback (refuse free LLM spend)"
        )
    if openai_api_key and not has_any_billing:
        logger.warning(
            "Scheduled rescan has OpenAI key but no usage_callback — "
            "pack LLM calls will not be billed (callback absent)"
        )

    for site in sites:
        user = db_session.get(User, site.user_id)
        if user is None or not getattr(user, "is_pro", False):
            stats["skipped"] += 1
            continue

        if daily_limit_for and runs_today_for:
            if runs_today_for(user.id) >= daily_limit_for(user):
                logger.info(
                    "Skip rescan site_id=%s user_id=%s: daily limit",
                    site.id,
                    user.id,
                )
                stats["skipped"] += 1
                continue

        if not claim_due_site(db_session, SiteAnalysis, site.id, now=now):
            stats["skipped"] += 1
            continue

        # Refresh after claim so persist_analysis sees current row.
        site = db_session.get(SiteAnalysis, site.id)
        if site is None:
            stats["skipped"] += 1
            continue

        if callable(usage_callback_factory):
            billing_cb: UsageCallback | None = usage_callback_factory(user)
        elif callable(usage_callback):
            billing_cb = usage_callback
        else:
            billing_cb = None

        run_measured = bool(measured) and callable(billing_cb)

        try:
            run_analysis_pipeline(
                db_session=db_session,
                SiteAnalysis=SiteAnalysis,
                AnalysisRun=AnalysisRun,
                user=user,
                url=site.url,
                openai_api_key=openai_api_key,
                openai_model=openai_model,
                competitor_urls=[],
                run_measured=run_measured,
                measured_env_enabled=True,
                source="scheduled",
                public_base=public_base,
                usage_callback=billing_cb,
                SovSnapshot=SovSnapshot,
                AlertDelivery=AlertDelivery,
            )
            stats["ok"] += 1
            logger.info("Rescan ok site_id=%s url=%s", site.id, site.url)
        except Exception as exc:
            mark_rescan_error(db_session, site, str(exc)[:500])
            stats["error"] += 1
            logger.exception("Rescan failed site_id=%s", site.id)

    return stats
