"""Persistenza analisi: aggiorna SiteAnalysis e appende AnalysisRun."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from services.analyzer import pages_for_storage

RESCAN_INTERVALS = ("off", "daily", "weekly")
DEFAULT_RESCAN_HOUR = 6
CRAWL_PAGES_STORE_LIMIT = 150


def clamp_hour(hour: Any, default: int = DEFAULT_RESCAN_HOUR) -> int:
    try:
        value = int(hour)
    except (TypeError, ValueError):
        return default
    return max(0, min(23, value))


def interval_delta(interval: str) -> timedelta | None:
    if interval == "daily":
        return timedelta(days=1)
    if interval == "weekly":
        return timedelta(days=7)
    return None


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
) -> Any:
    """Salva l’ultima analisi sul sito e crea una riga di storico."""
    scraped = result.get("scraped") or {}
    domain = scraped.get("domain") or urlparse(url).netloc
    now = datetime.now(timezone.utc)
    findings = result.get("findings") or []
    findings_json = json.dumps(findings, ensure_ascii=False)
    notes = result.get("notes")
    page_title = (scraped.get("title") or "")[:500] or None

    analysis = existing
    if analysis is None:
        analysis = SiteAnalysis(user_id=user_id, url=url, domain=domain)
        db_session.add(analysis)

    pages = result.get("pages") or scraped.get("crawled_pages") or []
    pages_analyzed = int(result.get("pages_analyzed") or len(pages) or 1)

    analysis.domain = domain
    analysis.page_title = page_title
    analysis.aio_score = result.get("aio_score")
    analysis.geo_score = result.get("geo_score")
    analysis.findings_json = findings_json
    analysis.analysis_notes = notes
    analysis.llms_txt = pack.get("llms.txt") or ""
    analysis.json_ld_artifact = pack.get("organization.jsonld.html") or ""
    analysis.faq_artifact = pack.get("faq.jsonld.html") or ""
    analysis.meta_pack_artifact = pack.get("meta-pack.html") or ""
    analysis.robots_artifact = pack.get("robots.txt") or ""
    analysis.checklist_artifact = pack.get("fix-this-week.md") or ""
    analysis.before_after_artifact = pack.get("before-after.md") or ""
    analysis.pages_analyzed = pages_analyzed
    advanced_artifacts = result.get("advanced_artifacts") or {}
    if not advanced_artifacts and isinstance(pack, dict):
        advanced_artifacts = {
            k: v
            for k, v in pack.items()
            if k
            in {
                "page-checklist.md",
                "html-patches.html",
                "brand-knowledge-graph.json",
                "competitor-benchmark.md",
                "executive-report.html",
            }
            and isinstance(v, str)
        }
    # PDF bytes → base64 per persistenza leggera nel blob JSON
    executive_pdf_b64 = ""
    pdf_bytes = result.get("executive_pdf")
    if isinstance(pdf_bytes, (bytes, bytearray)) and pdf_bytes:
        import base64

        executive_pdf_b64 = base64.b64encode(bytes(pdf_bytes)).decode("ascii")

    analysis.crawl_pages_json = json.dumps(
        {
            "pages": pages_for_storage(pages, limit=CRAWL_PAGES_STORE_LIMIT),
            "competitors": result.get("competitors") or [],
            "signals": result.get("signals") or {},
            "artifacts": advanced_artifacts,
            "executive_pdf_b64": executive_pdf_b64,
        },
        ensure_ascii=False,
    )
    analysis.created_at = now

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

    db_session.flush()

    run = AnalysisRun(
        site_id=analysis.id,
        user_id=user_id,
        url=url,
        domain=domain,
        page_title=page_title,
        aio_score=result.get("aio_score"),
        geo_score=result.get("geo_score"),
        findings_json=findings_json,
        analysis_notes=notes,
        llms_txt=pack.get("llms.txt") or "",
        json_ld_artifact=pack.get("organization.jsonld.html") or "",
        faq_artifact=pack.get("faq.jsonld.html") or "",
        meta_pack_artifact=pack.get("meta-pack.html") or "",
        robots_artifact=pack.get("robots.txt") or "",
        checklist_artifact=pack.get("fix-this-week.md") or "",
        before_after_artifact=pack.get("before-after.md") or "",
        pages_analyzed=pages_analyzed,
        crawl_pages_json=analysis.crawl_pages_json,
        source=source if source in {"manual", "scheduled"} else "manual",
        created_at=now,
    )
    db_session.add(run)
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
