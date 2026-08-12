"""Persistenza analisi: aggiorna SiteAnalysis e appende AnalysisRun."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from services.analyzer import pages_for_storage
from services.artifact_s3 import (
    apply_pack_attrs,
    clear_bulky_pack_attrs,
    db_lean_enabled,
    upload_pack,
)

RESCAN_INTERVALS = ("off", "daily", "weekly")
DEFAULT_RESCAN_HOUR = 6
CRAWL_PAGES_STORE_LIMIT = 150


def _probe_for_storage(
    probe: dict[str, Any] | None,
    *,
    include_snippet: bool = True,
    snippet_limit: int = 80_000,
) -> dict[str, Any]:
    """Persiste metadati probe (robots/llms) senza gonfiare inutilmente il JSON."""
    if not isinstance(probe, dict):
        return {}
    out: dict[str, Any] = {
        "url": probe.get("url") or "",
        "ok": bool(probe.get("ok")),
        "status": probe.get("status"),
    }
    if include_snippet:
        snippet = probe.get("snippet") or ""
        if isinstance(snippet, str) and snippet:
            out["snippet"] = snippet[:snippet_limit]
        else:
            out["snippet"] = ""
    return out


def clamp_hour(hour: Any, default: int = DEFAULT_RESCAN_HOUR) -> int:
    try:
        value = int(hour)
    except (TypeError, ValueError):
        return default
    return max(0, min(23, value))


def next_rescan_after(
    interval: str,
    *,
    hour: int = DEFAULT_RESCAN_HOUR,
    from_dt: datetime | None = None,
    after_completion: bool = False,
) -> datetime | None:
    """Prossimo slot UTC all’ora scelta (daily / weekly)."""
    if interval not in {"daily", "weekly"}:
        return None
    now = from_dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    hour = clamp_hour(hour)

    if interval == "weekly" and after_completion:
        slot = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(
            days=7
        )
        if slot <= now:
            slot += timedelta(days=1)
        return slot

    slot = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if slot <= now:
        slot += timedelta(days=1)
    return slot


ALLOWED_RUN_SOURCES = frozenset(
    {
        "manual",
        "scheduled",
        "job",
        "api",
        "onboarding",
        "verify",
        "preview",
        "measured",
    }
)



def _assign_pack_fields(target: Any, pack: dict[str, str]) -> None:
    """Write pack artifacts onto SiteAnalysis / AnalysisRun."""
    apply_pack_attrs(target, pack)


def _maybe_offload_pack(
    *,
    analysis: Any,
    run: Any,
    pack: dict[str, str],
    user_id: int,
) -> None:
    """Upload pack to S3 when configured; lean DB columns on success."""
    site_id = getattr(analysis, "id", None)
    run_id = getattr(run, "id", None)
    if not site_id or not run_id:
        return
    uri = upload_pack(pack, user_id=user_id, site_id=int(site_id), run_id=int(run_id))
    if not uri:
        return
    if hasattr(analysis, "pack_uri"):
        analysis.pack_uri = uri
    if hasattr(run, "pack_uri"):
        run.pack_uri = uri
    if db_lean_enabled():
        preview = pack.get("llms.txt") or ""
        clear_bulky_pack_attrs(analysis, llms_preview=preview)
        clear_bulky_pack_attrs(run, llms_preview=preview)


def persist_analysis(
    db_session: Session,
    *,
    SiteAnalysis: Any,
    AnalysisRun: Any,
    user_id: int,
    url: str,
    result: dict[str, Any],
    pack: dict[str, str],
    existing: Any | None = None,
    source: str = "manual",
    organization_id: int | None = None,
    user: Any | None = None,
    run_user_id: int | None = None,
) -> Any:
    """Salva l’ultima analisi sul sito e crea una riga di storico.

    ``user_id`` owns the site row; ``run_user_id`` (default ``user_id``) is the
    actor who spent credits — used for daily/quota accounting.
    """
    scraped = result.get("scraped") or {}
    domain = scraped.get("domain") or urlparse(url).netloc
    now = datetime.now(timezone.utc)
    findings = result.get("findings") or []
    findings_json = json.dumps(findings, ensure_ascii=False)
    notes = result.get("notes")
    page_title = (scraped.get("title") or "")[:500] or None

    # Resolve org workspace for Business/Admin when not provided.
    org_id = organization_id
    if org_id is None and user is not None:
        try:
            from centropic.tenancy import ensure_personal_org

            org = ensure_personal_org(user)
            if org is not None:
                org_id = int(org.id)
        except Exception:
            org_id = None

    analysis = existing
    created_new = analysis is None
    if analysis is None:
        analysis = SiteAnalysis(user_id=user_id, url=url, domain=domain)
        if org_id is not None and hasattr(analysis, "organization_id"):
            analysis.organization_id = org_id
        db_session.add(analysis)

    pages = result.get("pages") or scraped.get("crawled_pages") or []
    pages_analyzed = int(result.get("pages_analyzed") or len(pages) or 1)

    analysis.domain = domain
    analysis.page_title = page_title
    analysis.aio_score = result.get("aio_score")
    analysis.geo_score = result.get("geo_score")
    analysis.findings_json = findings_json
    analysis.analysis_notes = notes
    _assign_pack_fields(analysis, pack)
    analysis.pages_analyzed = pages_analyzed
    analysis.crawl_pages_json = json.dumps(
        {
            "pages": pages_for_storage(pages, limit=CRAWL_PAGES_STORE_LIMIT),
            "competitors": result.get("competitors") or [],
            "signals": result.get("signals") or {},
            "probes": {
                "robots": _probe_for_storage((result.get("probes") or {}).get("robots")),
                "llms": _probe_for_storage((result.get("probes") or {}).get("llms")),
                "sitemap": _probe_for_storage(
                    (result.get("probes") or {}).get("sitemap"), include_snippet=False
                ),
                "ai": _probe_for_storage((result.get("probes") or {}).get("ai")),
            },
        },
        ensure_ascii=False,
    )
    # Edge hosting: ogni re-analisi invalida la cache client (version bump).
    if getattr(analysis, "signals_hosted", False):
        analysis.signals_version = int(getattr(analysis, "signals_version", 1) or 1) + 1
    # Attach org on remesure when missing (Business upgrade path).
    if (
        org_id is not None
        and hasattr(analysis, "organization_id")
        and not getattr(analysis, "organization_id", None)
    ):
        analysis.organization_id = org_id
    # Preserve first-seen; bump updated_at when the column exists.
    if created_new or not getattr(analysis, "created_at", None):
        analysis.created_at = now
    if hasattr(analysis, "updated_at"):
        analysis.updated_at = now

    if source == "scheduled":
        analysis.last_rescan_at = now
        analysis.last_rescan_error = None
        interval = (analysis.rescan_interval or "off").lower()
        analysis.next_rescan_at = next_rescan_after(
            interval,
            hour=getattr(analysis, "rescan_hour", DEFAULT_RESCAN_HOUR),
            from_dt=now,
            after_completion=True,
        )

    try:
        with db_session.begin_nested():
            db_session.flush()
    except Exception as exc:
        from sqlalchemy.exc import IntegrityError

        if not isinstance(exc, IntegrityError):
            raise
        # Concurrent first-analyze race on UniqueConstraint(user_id, url).
        # SAVEPOINT rollback keeps prior committed billing in other sessions.
        analysis = SiteAnalysis.query.filter_by(user_id=user_id, url=url).first()
        if analysis is None:
            raise
        analysis.domain = domain
        analysis.page_title = page_title
        analysis.aio_score = result.get("aio_score")
        analysis.geo_score = result.get("geo_score")
        analysis.findings_json = findings_json
        analysis.analysis_notes = notes
        _assign_pack_fields(analysis, pack)
        analysis.pages_analyzed = pages_analyzed
        analysis.crawl_pages_json = json.dumps(
            {
                "pages": pages_for_storage(pages, limit=CRAWL_PAGES_STORE_LIMIT),
                "competitors": result.get("competitors") or [],
                "signals": result.get("signals") or {},
                "probes": {
                    "robots": _probe_for_storage(
                        (result.get("probes") or {}).get("robots")
                    ),
                    "llms": _probe_for_storage((result.get("probes") or {}).get("llms")),
                    "sitemap": _probe_for_storage(
                        (result.get("probes") or {}).get("sitemap"),
                        include_snippet=False,
                    ),
                    "ai": _probe_for_storage((result.get("probes") or {}).get("ai")),
                },
            },
            ensure_ascii=False,
        )
        if hasattr(analysis, "updated_at"):
            analysis.updated_at = now
        db_session.flush()

    run_source = source if source in ALLOWED_RUN_SOURCES else "manual"
    run_uid = int(run_user_id if run_user_id is not None else user_id)
    run = AnalysisRun(
        site_id=analysis.id,
        user_id=run_uid,
        url=url,
        domain=domain,
        page_title=page_title,
        aio_score=result.get("aio_score"),
        geo_score=result.get("geo_score"),
        findings_json=findings_json,
        analysis_notes=notes,
        pages_analyzed=pages_analyzed,
        crawl_pages_json=analysis.crawl_pages_json,
        source=run_source,
        created_at=now,
    )
    _assign_pack_fields(run, pack)
    db_session.add(run)
    db_session.flush()
    _maybe_offload_pack(
        analysis=analysis, run=run, pack=pack, user_id=run_uid
    )
    # Expose for callers that want to attribute UsageEvents.
    analysis._last_run_id = getattr(run, "id", None)  # type: ignore[attr-defined]
    db_session.commit()
    return analysis


def mark_rescan_error(
    db_session: Session,
    analysis: Any,
    error: str,
    *,
    retry_hours: int = 6,
) -> None:
    now = datetime.now(timezone.utc)
    analysis.last_rescan_at = now
    analysis.last_rescan_error = (error or "Errore re-scan")[:500]
    analysis.next_rescan_at = now + timedelta(hours=retry_hours)
    db_session.commit()
