"""Guest PLG preview: crawl/score without account, gate pack behind register.

Runs the structural analyze path (no measured SoV, no OpenAI spend) so marketers
see AIO score + a couple of critical findings before creating an account.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PREVIEW_CRAWL_PAGES = max(1, min(3, int(os.getenv("PREVIEW_CRAWL_PAGES", "1"))))
PREVIEW_TTL_HOURS = max(1, int(os.getenv("PREVIEW_TTL_HOURS", "48")))
PREVIEW_IP_HOUR = max(1, int(os.getenv("PREVIEW_IP_HOUR", "5")))
PREVIEW_IP_DAY = max(1, int(os.getenv("PREVIEW_IP_DAY", "15")))


def new_preview_token() -> str:
    return secrets.token_urlsafe(18)


def hash_client_ip(ip: str) -> str:
    raw = (ip or "").strip().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:64]


def preview_expires_at(*, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now + timedelta(hours=PREVIEW_TTL_HOURS)


def domain_from_url(url: str) -> str:
    host = (urlparse(url).netloc or "").lower().removeprefix("www.")
    return host or "sito"


def pick_preview_findings(
    findings: list[dict[str, Any]] | None, *, limit: int = 2
) -> list[dict[str, str]]:
    """Prefer critical, then warn; return at most ``limit`` public-safe rows."""
    items = [f for f in (findings or []) if isinstance(f, dict)]
    critical = [
        f for f in items if str(f.get("severity") or "").lower() == "critical"
    ]
    warn = [f for f in items if str(f.get("severity") or "").lower() == "warn"]
    ordered = critical + warn + [
        f
        for f in items
        if str(f.get("severity") or "").lower() not in {"critical", "warn"}
    ]
    out: list[dict[str, str]] = []
    for f in ordered:
        title = str(f.get("title") or "").strip()
        if not title:
            continue
        out.append(
            {
                "title": title[:160],
                "detail": str(f.get("detail") or "").strip()[:280],
                "severity": str(f.get("severity") or "info")[:20],
            }
        )
        if len(out) >= limit:
            break
    return out


def public_preview_payload(preview: Any) -> dict[str, Any]:
    """Fields safe to show before registration (no pack / fix bodies)."""
    findings: list[dict[str, Any]] = []
    try:
        data = json.loads(getattr(preview, "findings_json", None) or "[]")
        if isinstance(data, list):
            findings = data
    except json.JSONDecodeError:
        findings = []
    status = str(getattr(preview, "status", "") or "pending")
    return {
        "token": getattr(preview, "token", ""),
        "status": status,
        "domain": getattr(preview, "domain", "") or "",
        "url": getattr(preview, "url", "") or "",
        "aio_score": getattr(preview, "aio_score", None),
        "geo_score": getattr(preview, "geo_score", None),
        "findings_preview": pick_preview_findings(findings, limit=2),
        "findings_total": len(findings),
        "error": getattr(preview, "error", None) if status == "error" else None,
        "done": status == "done",
    }


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def run_guest_preview(
    *,
    db_session: Any,
    GuestPreview: Any,
    preview_id: int,
) -> None:
    """Execute structural analysis + pack (fallback llms, no API key) for a guest row."""
    from services.analyzer import analyze_site
    from services.artifacts import build_optimization_pack
    from services.geo_suite import run_geo_suite

    preview = db_session.get(GuestPreview, preview_id)
    if preview is None:
        return
    if preview.status == "done":
        return
    if getattr(preview, "claimed_user_id", None):
        return

    preview.status = "running"
    preview.error = None
    db_session.commit()

    try:
        result = analyze_site(preview.url, max_pages=PREVIEW_CRAWL_PAGES)
        run_geo_suite(result=result, user=None, run_measured=False)
        scraped = result.get("scraped") or {}
        pack = build_optimization_pack(
            preview.url,
            scraped,
            api_key="",  # force fallback llms — no anonymous LLM spend
            model="gpt-4o-mini",
            logger=logger,
            findings=result.get("findings"),
            result=result,
            locale=getattr(preview, "locale", None) or "it",
        )
        preview.aio_score = result.get("aio_score")
        preview.geo_score = result.get("geo_score")
        preview.findings_json = _json_dumps(result.get("findings") or [])
        preview.result_json = _json_dumps(
            {
                "scraped": {
                    "domain": scraped.get("domain") or preview.domain,
                    "title": scraped.get("title") or "",
                    "description": (scraped.get("description") or "")[:500],
                    "final_url": scraped.get("final_url") or preview.url,
                },
                "aio_score": result.get("aio_score"),
                "geo_score": result.get("geo_score"),
                "findings": result.get("findings") or [],
                "pages": result.get("pages") or [],
                "probes": {
                    k: {
                        "ok": bool((v or {}).get("ok")),
                        "status": (v or {}).get("status"),
                        "url": (v or {}).get("url"),
                    }
                    for k, v in (result.get("probes") or {}).items()
                    if isinstance(v, dict)
                },
                "signals": result.get("signals") or {},
            }
        )
        preview.pack_json = _json_dumps(pack)
        preview.domain = str(
            scraped.get("domain") or preview.domain or domain_from_url(preview.url)
        )
        preview.status = "done"
        preview.finished_at = datetime.now(timezone.utc)
        db_session.commit()
    except Exception as exc:
        logger.exception("guest preview failed id=%s", preview_id)
        try:
            db_session.rollback()
        except Exception:
            pass
        preview = db_session.get(GuestPreview, preview_id)
        if preview is None:
            return
        preview.status = "error"
        preview.error = str(exc)[:480]
        preview.finished_at = datetime.now(timezone.utc)
        db_session.commit()


def claim_guest_preview(
    *,
    db_session: Any,
    GuestPreview: Any,
    SiteAnalysis: Any,
    AnalysisRun: Any,
    user: Any,
    token: str,
) -> Any | None:
    """Attach a completed guest preview to ``user`` as a SiteAnalysis (+ run)."""
    from services.analysis_store import persist_analysis

    tok = (token or "").strip()
    if not tok or user is None:
        return None
    preview = GuestPreview.query.filter_by(token=tok).first()
    if preview is None:
        return None
    if preview.status != "done":
        return None
    expires = getattr(preview, "expires_at", None)
    if expires is not None:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return None
    if preview.claimed_user_id and int(preview.claimed_user_id) != int(user.id):
        return None
    if preview.claimed_site_id and preview.claimed_user_id == user.id:
        return db_session.get(SiteAnalysis, preview.claimed_site_id)

    try:
        result = json.loads(preview.result_json or "{}")
        pack = json.loads(preview.pack_json or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(result, dict) or not isinstance(pack, dict):
        return None

    existing = SiteAnalysis.query.filter_by(user_id=user.id, url=preview.url).first()
    analysis = persist_analysis(
        db_session,
        SiteAnalysis=SiteAnalysis,
        AnalysisRun=AnalysisRun,
        user_id=user.id,
        url=preview.url,
        existing=existing,
        result=result,
        pack={str(k): str(v) for k, v in pack.items()},
        source="preview",
        user=user,
    )
    preview.claimed_user_id = user.id
    preview.claimed_site_id = analysis.id
    if not getattr(user, "website_url", None):
        user.website_url = preview.url
    db_session.commit()
    return analysis
