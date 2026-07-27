"""Shared analyze → pack → persist pipeline (sync or job worker)."""

from __future__ import annotations

import logging
from typing import Any

from services.analyzer import analyze_site
from services.analysis_store import persist_analysis
from services.artifacts import build_optimization_pack
from services.deep_checks import analyze_monitoring_alerts
from services.rating import compute_rating
from services.signals import compare_with_previous
from services.sov_measured import measured_sov_available, run_measured_sov

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
    source: str = "manual",
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

    if run_measured and user.is_pro and measured_sov_available():
        brand = user.company or (result.get("scraped") or {}).get("domain") or url
        domain = (result.get("scraped") or {}).get("domain") or url
        measured = run_measured_sov(brand=str(brand), domain=str(domain))
        signals = dict(result.get("signals") or {})
        signals["sov_measured"] = measured
        result["signals"] = signals

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
    return analysis
