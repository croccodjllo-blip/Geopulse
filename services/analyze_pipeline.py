"""Shared analyze → pack → persist pipeline (sync or job worker)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from services.analyzer import analyze_site
from services.analysis_store import persist_analysis
from services.artifacts import build_optimization_pack, scrape_fingerprint
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
from services.measured_pipeline import run_measured_only_pipeline
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
    # Deferred measured follow-up: citation monitor only (no crawl/pack).
    if (source or "").strip().lower() == "measured" and bool(run_measured):
        return run_measured_only_pipeline(
            db_session=db_session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user=user,
            url=url,
            measured_env_enabled=measured_env_enabled,
            source=source,
            usage_callback=usage_callback,
            heartbeat_callback=heartbeat_callback,
            SovSnapshot=SovSnapshot,
            organization_id=organization_id,
        )

    existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
    if existing is None:
        # Org member remesure must update the shared site, not fork under actor.
        try:
            from centropic.tenancy import sites_query_for_user

            existing = (
                sites_query_for_user(SiteAnalysis, user).filter_by(url=url).first()
            )
        except Exception:
            existing = None
    # Defense-in-depth: viewers may read shared sites but must not remesure them.
    if existing is not None:
        try:
            from centropic.tenancy import user_can_write_site

            if not user_can_write_site(user, existing):
                raise PermissionError(
                    "Ruolo viewer: non puoi modificare siti condivisi dell’organizzazione."
                )
        except PermissionError:
            raise
        except Exception:
            pass
    owner_user_id = int(getattr(existing, "user_id", None) or user.id)
    actor_user_id = int(user.id)
    site_org_id = organization_id
    if site_org_id is None and existing is not None:
        site_org_id = getattr(existing, "organization_id", None)
    previous_run = None
    if existing is not None:
        previous_run = (
            AnalysisRun.query.filter_by(site_id=existing.id, user_id=owner_user_id)
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

    prompts = None
    if measured_ok:
        scraped0 = result.get("scraped") if isinstance(result.get("scraped"), dict) else {}
        domain0 = str(scraped0.get("domain") or "")
        from services.sov_measured import is_user_owned_domain, resolve_measured_brand

        brand0 = resolve_measured_brand(user=user, domain=domain0, scraped=scraped0)
        prompts = resolve_prompts(
            user=user,
            locale=prompt_locale,
            domain=domain0,
            brand=brand0,
            own_site=is_user_owned_domain(user, domain0),
            max_prompts=8,
        )

    # Suite GEO/AIO (entity, citability, schema, locale, publish verify).
    # SoV measured / citation monitor: solo Plus — surface as phase "sov"
    # so the overlay does not look stuck on Score during the long probe.
    def _suite_hb(phase: str | None = None, done: int | None = None, total: int | None = None) -> None:
        _hb(
            phase=phase or ("sov" if measured_ok else "geo"),
            done=crawled if done is None else done,
            total=max(crawled, pages) if total is None else total,
        )

    if measured_ok:
        _hb(phase="sov", done=crawled, total=max(crawled, pages))

    run_geo_suite(
        result=result,
        user=user,
        previous_run=previous_run,
        run_measured=measured_ok,
        prompts=prompts,
        usage_callback=usage_callback,
        heartbeat_callback=_suite_hb,
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

    # FinOps: persist scrape fingerprint for llms.txt rescan cache.
    try:
        sig = result.setdefault("signals", {})
        if isinstance(sig, dict):
            sig["llms_fingerprint"] = scrape_fingerprint(result.get("scraped") or {})
    except Exception:
        logger.exception("llms fingerprint attach failed")
    analysis = persist_analysis(
        db_session,
        SiteAnalysis=SiteAnalysis,
        AnalysisRun=AnalysisRun,
        user_id=owner_user_id,
        run_user_id=actor_user_id,
        url=url,
        existing=existing,
        result=result,
        pack=pack,
        source=source,
        organization_id=site_org_id,
        user=user,
    )

    # Attribute recent usage events to this run when possible (spender = actor).
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
                    AnalysisRun.query.filter_by(
                        site_id=analysis.id, user_id=owner_user_id
                    )
                    .order_by(AnalysisRun.created_at.desc())
                    .first()
                )
                persist_sov_snapshot(
                    db_session,
                    SovSnapshot=SovSnapshot,
                    site_id=analysis.id,
                    user_id=owner_user_id,
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
