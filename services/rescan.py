"""Re-scan periodico per siti Pro con schedule attivo."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from services.analyze_pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)


def due_sites_query(SiteAnalysis: Any, User: Any, *, now: datetime | None = None):
    """Siti Pro/admin con interval attivo e next_rescan_at scaduto."""
    now = now or datetime.now(timezone.utc)
    return (
        SiteAnalysis.query.join(User, SiteAnalysis.user_id == User.id)
        .filter(
            SiteAnalysis.rescan_interval.in_(("daily", "weekly")),
            SiteAnalysis.next_rescan_at.isnot(None),
            SiteAnalysis.next_rescan_at <= now,
            User.plan.in_(("plus", "pro", "admin")),
        )
        .order_by(SiteAnalysis.next_rescan_at.asc())
    )


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
    public_base: str = "https://geopulse.it",
) -> dict[str, int]:
    """Esegue i re-scan scaduti via pipeline completa (suite + alert)."""
    from services.analysis_store import mark_rescan_error

    stats = {"ok": 0, "error": 0, "skipped": 0}
    sites = due_sites_query(SiteAnalysis, User).limit(max(1, limit)).all()

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
                run_measured=bool(measured),
                measured_env_enabled=True,
                source="scheduled",
                public_base=public_base,
            )
            stats["ok"] += 1
            logger.info("Rescan ok site_id=%s url=%s", site.id, site.url)
        except Exception as exc:
            mark_rescan_error(db_session, site, str(exc)[:500])
            stats["error"] += 1
            logger.exception("Rescan failed site_id=%s", site.id)

    return stats
