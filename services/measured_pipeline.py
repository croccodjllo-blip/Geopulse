"""Measured-only SoV path: citation monitor without a full re-crawl.

Used by deferred ``source=measured`` jobs after Stimato+pack completed.
Rebuilds a minimal result from the existing ``SiteAnalysis`` row, runs the
LLM citation monitor, persists SoV snapshot + signal merge.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from services.prompt_bank import resolve_prompts
from services.sov_graph import extract_sov_snapshot, persist_sov_snapshot
from services.sov_measured import should_run_measured, user_can_run_measured
from services.citation_monitor import run_citation_monitor

logger = logging.getLogger(__name__)


def result_skeleton_from_site(site: Any, *, url: str) -> dict[str, Any]:
    """Rebuild enough of an analyze ``result`` dict for citation monitor."""
    blob = {}
    try:
        raw = getattr(site, "crawl_pages_json", None) or "{}"
        parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
        if isinstance(parsed, dict):
            blob = parsed
        elif isinstance(parsed, list):
            blob = {"pages": parsed}
    except Exception:
        blob = {}

    pages = blob.get("pages") if isinstance(blob.get("pages"), list) else []
    probes = blob.get("probes") if isinstance(blob.get("probes"), dict) else {}
    signals = blob.get("signals") if isinstance(blob.get("signals"), dict) else {}
    competitors = (
        blob.get("competitors") if isinstance(blob.get("competitors"), list) else []
    )
    domain = (
        getattr(site, "domain", None)
        or urlparse(url).netloc
        or ""
    )
    scraped = {
        "domain": domain,
        "title": getattr(site, "page_title", None) or "",
        "url": url,
        "crawled_pages": pages,
        "entity": {"brand_name": domain},
    }
    return {
        "aio_score": getattr(site, "aio_score", None),
        "geo_score": getattr(site, "geo_score", None),
        "findings": list(getattr(site, "findings", None) or []),
        "notes": getattr(site, "analysis_notes", None),
        "pages": pages,
        "pages_analyzed": int(getattr(site, "pages_analyzed", None) or len(pages) or 1),
        "scraped": scraped,
        "probes": probes,
        "signals": dict(signals),
        "competitors": competitors,
    }


def _merge_signals_into_site(site: Any, result: dict[str, Any]) -> None:
    """Update crawl_pages_json signals in-place without dropping pages/probes."""
    try:
        raw = getattr(site, "crawl_pages_json", None) or "{}"
        blob = json.loads(raw) if isinstance(raw, str) else (raw or {})
        if not isinstance(blob, dict):
            blob = {"pages": blob if isinstance(blob, list) else []}
    except Exception:
        blob = {}
    signals = blob.get("signals") if isinstance(blob.get("signals"), dict) else {}
    incoming = result.get("signals") if isinstance(result.get("signals"), dict) else {}
    signals.update(incoming)
    blob["signals"] = signals
    if result.get("competitors") is not None:
        blob["competitors"] = result.get("competitors") or []
    site.crawl_pages_json = json.dumps(blob, ensure_ascii=False)
    # Keep findings_json in sync — dashboard reads site.findings, not only signals.
    if result.get("findings") is not None and hasattr(site, "findings_json"):
        site.findings_json = json.dumps(result.get("findings") or [], ensure_ascii=False)
    if hasattr(site, "updated_at"):
        site.updated_at = datetime.now(timezone.utc)


def run_measured_only_pipeline(
    *,
    db_session: Any,
    SiteAnalysis: Any,
    AnalysisRun: Any,
    user: Any,
    url: str,
    measured_env_enabled: bool = True,
    source: str = "measured",
    usage_callback: Any | None = None,
    heartbeat_callback: Any | None = None,
    SovSnapshot: Any | None = None,
    organization_id: int | None = None,
    locale: str | None = None,
) -> Any:
    """Run citation monitor against an existing site; no crawl/pack rebuild."""
    existing = SiteAnalysis.query.filter_by(user_id=user.id, url=url).first()
    if existing is None:
        try:
            from centropic.tenancy import sites_query_for_user

            existing = sites_query_for_user(SiteAnalysis, user).filter_by(url=url).first()
        except Exception:
            existing = None
    if existing is None:
        raise RuntimeError(
            "Measured follow-up richiede un sito già analizzato (Stimato/pack)."
        )

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
            try:
                heartbeat_callback()
            except Exception:
                logger.debug("heartbeat failed", exc_info=True)
                raise
        except Exception:
            logger.debug("heartbeat failed", exc_info=True)
            raise

    _hb(phase="sov", done=0, total=1)

    if not should_run_measured(
        user=user,
        requested=True,
        env_enabled=measured_env_enabled,
    ):
        raise RuntimeError("Measured SoV non disponibile per questo account.")

    result = result_skeleton_from_site(existing, url=url)
    scraped = result.get("scraped") or {}
    domain = str(scraped.get("domain") or existing.domain or "")

    from services.pack_i18n import capture_ui_locale

    prompt_locale = capture_ui_locale(locale)

    scraped = result.get("scraped") if isinstance(result.get("scraped"), dict) else {}
    if not scraped.get("title"):
        scraped = {
            **scraped,
            "title": getattr(existing, "page_title", None) or scraped.get("title") or "",
        }

    from services.sov_measured import is_user_owned_domain, resolve_measured_brand

    brand = resolve_measured_brand(user=user, domain=domain, scraped=scraped)
    prompts = resolve_prompts(
        user=user,
        locale=prompt_locale,
        domain=domain,
        brand=brand,
        own_site=is_user_owned_domain(user, domain),
        max_prompts=8,
    )
    competitors = result.get("competitors") or []

    if not user_can_run_measured(user):
        raise RuntimeError("Measured SoV riservato a Plus/Business.")

    monitored = run_citation_monitor(
        brand=str(brand),
        domain=str(domain),
        prompts=prompts,
        competitors=competitors,
        usage_callback=usage_callback,
        heartbeat_callback=lambda **kw: _hb(
            phase=kw.get("phase") or "sov",
            done=kw.get("done"),
            total=kw.get("total") or 1,
        ),
    )
    signals = dict(result.get("signals") or {})
    signals["sov_measured"] = monitored
    findings = list(result.get("findings") or [])
    findings.extend(monitored.get("findings") or [])
    result["signals"] = signals
    result["findings"] = findings
    result["sov_measured"] = monitored

    _hb(phase="persist", done=1, total=1)
    _merge_signals_into_site(existing, result)

    # Lightweight history row so measured runs appear in timeline.
    now = datetime.now(timezone.utc)
    run = None
    try:
        run = AnalysisRun(
            site_id=existing.id,
            user_id=int(getattr(existing, "user_id", None) or user.id),
            url=url,
            domain=domain,
            aio_score=existing.aio_score,
            geo_score=existing.geo_score,
            findings_json=json.dumps(findings, ensure_ascii=False),
            pages_analyzed=int(existing.pages_analyzed or 1),
            source="measured",
            created_at=now,
        )
        # Copy pack fields if columns exist on AnalysisRun
        for attr in (
            "llms_txt",
            "json_ld_artifact",
            "faq_artifact",
            "meta_pack_artifact",
            "robots_artifact",
            "checklist_artifact",
            "before_after_artifact",
            "pack_uri",
            "crawl_pages_json",
        ):
            if hasattr(run, attr) and hasattr(existing, attr):
                setattr(run, attr, getattr(existing, attr))
        db_session.add(run)
        db_session.flush()
        existing._last_run_id = int(run.id)
    except Exception:
        logger.exception("measured AnalysisRun create failed")
        try:
            db_session.rollback()
        except Exception:
            pass
        # Re-apply signal merge after rollback
        _merge_signals_into_site(existing, result)

    if SovSnapshot is not None:
        try:
            snap = extract_sov_snapshot(result)
            if snap:
                persist_sov_snapshot(
                    db_session,
                    SovSnapshot=SovSnapshot,
                    site_id=int(existing.id),
                    user_id=int(getattr(existing, "user_id", None) or user.id),
                    run_id=int(getattr(run, "id", 0) or 0) or None,
                    snapshot=snap,
                    source="measured",
                )
        except Exception:
            logger.exception("measured persist_sov_snapshot failed")

    db_session.commit()
    _hb(phase="done", done=1, total=1)
    return existing
