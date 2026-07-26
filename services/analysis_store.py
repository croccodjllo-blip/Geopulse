"""Persistenza analisi: aggiorna SiteAnalysis e appende AnalysisRun."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

RESCAN_INTERVALS = ("off", "daily", "weekly")


def interval_delta(interval: str) -> timedelta | None:
    if interval == "daily":
        return timedelta(days=1)
    if interval == "weekly":
        return timedelta(days=7)
    return None


def next_rescan_after(interval: str, *, from_dt: datetime | None = None) -> datetime | None:
    delta = interval_delta(interval)
    if delta is None:
        return None
    base = from_dt or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + delta


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

    analysis.domain = domain
    analysis.page_title = page_title
    analysis.aio_score = result.get("aio_score")
    analysis.geo_score = result.get("geo_score")
    analysis.findings_json = findings_json
    analysis.analysis_notes = notes
    analysis.llms_txt = pack.get("llms.txt") or ""
    analysis.json_ld_artifact = pack.get("organization.jsonld.html") or ""
    analysis.meta_pack_artifact = pack.get("meta-pack.html") or ""
    analysis.robots_artifact = pack.get("robots.txt") or ""
    analysis.created_at = now

    if source == "scheduled":
        analysis.last_rescan_at = now
        analysis.last_rescan_error = None
        interval = (analysis.rescan_interval or "off").lower()
        analysis.next_rescan_at = next_rescan_after(interval, from_dt=now)

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
        meta_pack_artifact=pack.get("meta-pack.html") or "",
        robots_artifact=pack.get("robots.txt") or "",
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
