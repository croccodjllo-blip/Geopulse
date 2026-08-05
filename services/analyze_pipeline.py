"""Shared analyze → pack → persist pipeline (sync or job worker)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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
from services.sov_graph import (
    extract_sov_snapshot,
    persist_sov_snapshot,
    previous_brand_rate,
    sov_delta_findings,
)
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
    public_base: str = "https://centropic.ai",
    # Billing: optional callbacks and context
    usage_callback: Any | None = None,
    max_pages: int | None = None,
    heartbeat_callback: Any | None = None,
    SovSnapshot: Any | None = None,
    AlertDelivery: Any | None = None,
    UsageEvent: Any | None = None,
    organization_id: int | None = None,
    run_started_at: Any | None = None,
) -> Any:
    existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
    previous_run = None
    if existing is not None:
        previous_run = (
            AnalysisRun.query.filter_by(site_id=existing.id, user_id=user.id)
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )

    prev_sov_rate = None
    if existing is not None and SovSnapshot is not None:
        try:
            prev_sov_rate = previous_brand_rate(
                SovSnapshot, site_id=existing.id, user_id=user.id
            )
        except Exception:
            logger.exception("previous_brand_rate failed")

    pages = int(max_pages) if max_pages is not None else int(user.crawl_pages)
    if pages <= 0:
        pages = int(getattr(user, "crawl_pages", 8) or 8)

    pipeline_started = run_started_at or datetime.now(timezone.utc)

    def _hb(
        phase: str | None = None,
        done: int | None = None,
        total: int | None = None,
    ) -> None:
        if not callable(heartbeat_callback):
            return
        try:
            heartbeat_callback(phase=phase, done=done, total=total)
        except TypeError:
            # Older callers that only accept zero-arg heartbeats.
            try:
                heartbeat_callback()
            except Exception:
                logger.debug("heartbeat failed", exc_info=True)
                raise
        except Exception:
            logger.debug("heartbeat failed", exc_info=True)
            raise

    _hb(phase="crawl", done=0, total=pages)

    def _crawl_progress(done: int, total: int) -> None:
        _hb(phase="crawl", done=int(done), total=int(total))

    # Prefer capability gate over coarse is_pro when available.
    can_competitors = True
    try:
        can_competitors = bool(getattr(user, "can")("competitors"))
    except Exception:
        can_competitors = bool(getattr(user, "is_pro", False))

    result = analyze_site(
        url,
        max_pages=pages,
        competitor_urls=(competitor_urls or [])[:3] if can_competitors else [],
        progress_callback=_crawl_progress,
    )

    crawled = len(result.get("pages") or result.get("page_reports") or []) or pages
    _hb(phase="geo", done=crawled, total=max(crawled, pages))

    measured_ok = should_run_measured(
        user=user,
        requested=run_measured,
        env_enabled=measured_env_enabled,
    )
    prompt_locale = "it"
    try:
        from flask import has_request_context

        if has_request_context():
            from services.i18n import active_ui_locale

            prompt_locale = active_ui_locale() or "it"
    except Exception:
        prompt_locale = "it"

    prompts = (
        resolve_prompts(
            user=user,
            locale=prompt_locale,
            domain=str((result.get("scraped") or {}).get("domain") or ""),
            max_prompts=8,
        )
        if measured_ok
        else None
    )

    # Suite GEO/AIO (entity, citability, schema, locale, publish verify).
    # SoV measured / citation monitor: solo Plus.
    def _geo_hb() -> None:
        _hb(phase="geo", done=crawled, total=max(crawled, pages))

    run_geo_suite(
        result=result,
        user=user,
        previous_run=previous_run,
        run_measured=measured_ok,
        prompts=prompts,
        usage_callback=usage_callback,
        heartbeat_callback=_geo_hb,
    )

    _hb(phase="score", done=crawled, total=max(crawled, pages))

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

    # Measurement graph: SoV drop → alert findings (before pack/persist)
    try:
        snap = extract_sov_snapshot(result)
        delta = sov_delta_findings(current=snap, previous_rate=prev_sov_rate)
        if delta:
            result["findings"] = list(result.get("findings") or []) + list(delta)
    except Exception:
        logger.exception("sov_delta_findings failed")

    _hb(phase="pack", done=crawled, total=max(crawled, pages))

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
        usage_callback=usage_callback,
        heartbeat_callback=lambda: _hb(
            phase="pack", done=crawled, total=max(crawled, pages)
        ),
    )

    # Lease / cancel check before persist: avoid writing if job was reclaimed
    # or cancelled mid-pack.
    _hb(phase="persist", done=crawled, total=max(crawled, pages))

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
        organization_id=organization_id,
        user=user,
    )

    # Attribute recent usage events to this run when possible.
    run_id = getattr(analysis, "_last_run_id", None)
    if UsageEvent is not None and run_id:
        try:
            (
                UsageEvent.query.filter(
                    UsageEvent.user_id == user.id,
                    UsageEvent.analysis_run_id.is_(None),
                    UsageEvent.created_at >= pipeline_started,
                ).update(
                    {"analysis_run_id": int(run_id)},
                    synchronize_session=False,
                )
            )
            db_session.commit()
        except Exception:
            logger.exception("usage event attribution failed")
            try:
                db_session.rollback()
            except Exception:
                pass

    # Persist SoV snapshot for measurement graph / agency charts
    if SovSnapshot is not None:
        try:
            snap = extract_sov_snapshot(result)
            if snap:
                run = (
                    AnalysisRun.query.filter_by(site_id=analysis.id, user_id=user.id)
                    .order_by(AnalysisRun.created_at.desc())
                    .first()
                )
                persist_sov_snapshot(
                    db_session,
                    SovSnapshot=SovSnapshot,
                    site_id=analysis.id,
                    user_id=user.id,
                    run_id=getattr(run, "id", None) or run_id,
                    snapshot=snap,
                    source=source
                    if source
                    in {"manual", "scheduled", "api", "job", "verify", "onboarding"}
                    else "analyze",
                )
                db_session.commit()
        except Exception:
            logger.exception("persist_sov_snapshot failed")
            try:
                db_session.rollback()
            except Exception:
                pass

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
                db_session=db_session if AlertDelivery is not None else None,
                AlertDelivery=AlertDelivery,
            )
    except Exception:
        logger.exception("dispatch_alerts failed")

    return analysis
