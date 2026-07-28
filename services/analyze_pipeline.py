"""Shared analyze → pack → persist pipeline (sync or job worker)."""

from __future__ import annotations

import logging
from typing import Any

from services.analyzer import analyze_site
from services.analysis_store import persist_analysis
from services.artifacts import build_optimization_pack
from services.alerts import dispatch_alerts
from services.deep_checks import analyze_monitoring_alerts
from services.geo_suite import run_geo_suite
from services.prompt_bank import resolve_prompts
from services.rating import compute_rating
from services.signals import compare_with_previous
from services.sov_measured import should_run_measured

logger = logging.getLogger(__name__)


def run_analysis_pipeline(
    *,
    db_session,
    SiteAnalysis,
    AnalysisRun,
    user,
    url: str,
    openai_api_key: str | None,
    openai_model: str,
    competitor_urls: list[str] | None = None,
    run_measured: bool = False,
    measured_env_enabled: bool = True,
    source: str = "manual",
    public_base: str = "https://geopulse.it",
) -> Any:
    existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
    previous_run = None
    if existing is not None:
        previous_run = (
            AnalysisRun.query.filter_by(site_id=existing.id, user_id=user.id)
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )

    result = analyze_site(
        url,
        max_pages=user.crawl_pages,
        competitor_urls=(competitor_urls or [])[:3] if user.is_pro else [],
    )

    measured_ok = should_run_measured(
        user=user,
        requested=run_measured,
        env_enabled=measured_env_enabled,
    )
    prompts = (
        resolve_prompts(
            user=user,
            locale="it",
            domain=str((result.get("scraped") or {}).get("domain") or ""),
            max_prompts=8,
        )
        if measured_ok
        else None
    )

    # Suite GEO/AIO (entity, citability, schema, locale, publish verify).
    # SoV measured / citation monitor: solo Plus.
    run_geo_suite(
        result=result,
        user=user,
        previous_run=previous_run,
        run_measured=measured_ok,
        prompts=prompts,
    )

    run_diff = compare_with_previous(
        aio_score=result.get("aio_score"),
        geo_score=result.get("geo_score"),
        findings=result.get("findings"),
        previous=previous_run,
    )
    if run_diff.get("findings"):
        result["findings"] = list(result.get("findings") or []) + list(
            run_diff["findings"]
        )
    result["diff"] = run_diff
    rating_now = compute_rating(
        result.get("aio_score"),
        result.get("geo_score"),
        result.get("findings"),
    )
    alerts = analyze_monitoring_alerts(
        probes=result.get("probes") or {},
        rating=rating_now,
        previous=previous_run,
        diff=run_diff,
    )
    if alerts.get("findings"):
        result["findings"] = list(result.get("findings") or []) + list(
            alerts["findings"]
        )

    pack = build_optimization_pack(
        url,
        result["scraped"],
        api_key=openai_api_key,
        model=openai_model,
        logger=logger,
        findings=result.get("findings"),
        previous=previous_run,
        diff=run_diff,
        result=result,
    )
    analysis = persist_analysis(
        db_session,
        SiteAnalysis=SiteAnalysis,
        AnalysisRun=AnalysisRun,
        user_id=user.id,
        url=url,
        existing=existing,
        result=result,
        pack=pack,
        source=source,
    )

    # Outbound alerts (email / webhook) after persist
    try:
        if getattr(user, "alert_email_enabled", True) or (
            getattr(user, "webhook_url", None) or ""
        ).strip():
            dispatch_alerts(
                user=user,
                site=analysis,
                findings=result.get("findings") or [],
                rating=rating_now,
                base_url=public_base,
            )
    except Exception:
        logger.exception("dispatch_alerts failed")

    return analysis
