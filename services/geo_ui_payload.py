"""Build JSON payload for the React GEO Live Charts embed."""

from __future__ import annotations

from typing import Any

from services.engine_breakdown import apply_measured_sov, compute_engine_breakdown
from services.rating import compute_rating
from services.sov_graph import list_sov_snapshots, sov_series_for_chart

_TONES = ("emerald", "cyan", "violet", "amber")


def _engine_status(share: float | None) -> str:
    if share is None:
        return "unknown"
    if share >= 45:
        return "dominant"
    if share >= 30:
        return "optimal"
    return "needs_action"


def _insight_severity(raw: str) -> str:
    sev = (raw or "").lower()
    if sev == "critical":
        return "high"
    if sev == "warn":
        return "gap"
    return "info"


def build_geo_ui_payload(
    *,
    user: Any,
    SiteAnalysis: Any,
    SovSnapshot: Any,
    audit_href: str = "/dashboard#analyze",
    report_href: str = "/dashboard",
) -> dict[str, Any]:
    """Session-safe payload for ``window.__CENTROPIC_GEO_DATA__``."""
    latest = (
        SiteAnalysis.query.filter_by(user_id=user.id)
        .order_by(SiteAnalysis.created_at.desc())
        .first()
    )
    empty: dict[str, Any] = {
        "ready": False,
        "domain": None,
        "somPercent": None,
        "somDelta": None,
        "enginesTracked": 0,
        "recRank": None,
        "aioScore": None,
        "geoScore": None,
        "pagesAnalyzed": None,
        "findingsCount": 0,
        "sentiment": None,
        "sentimentLabel": None,
        "evidenceLabel": None,
        "engines": [],
        "engineBars": [],
        "insights": [],
        "somTrend": [],
        "auditHref": audit_href,
        "reportHref": report_href,
    }
    if latest is None:
        return empty

    findings_all = list(latest.findings or [])
    findings_critical = [
        f
        for f in findings_all
        if str((f or {}).get("severity") or "").lower() in {"critical", "warn"}
    ]
    engine_breakdown = compute_engine_breakdown(
        aio_score=latest.aio_score,
        geo_score=latest.geo_score,
        findings=findings_all,
        robots_text=latest.robots_probed_text or "",
        competitors=latest.competitors,
    )
    measured = (latest.signals or {}).get("sov_measured")
    if getattr(user, "is_pro", False) and isinstance(measured, dict):
        engine_breakdown = apply_measured_sov(engine_breakdown, measured)

    engines_raw = list((engine_breakdown or {}).get("engines") or [])
    engines: list[dict[str, Any]] = []
    engine_bars: list[dict[str, Any]] = []
    for i, eng in enumerate(engines_raw):
        if not isinstance(eng, dict):
            continue
        share = eng.get("share")
        try:
            share_f = float(share) if share is not None else None
        except (TypeError, ValueError):
            share_f = None
        tone = _TONES[i % len(_TONES)]
        eid = str(eng.get("id") or f"engine-{i}")
        label = str(eng.get("label") or eid)
        top = None
        # Prefer measured top domain / sample URL if present
        for key in ("top_domain", "topDomain", "sample_url", "url"):
            if eng.get(key):
                top = str(eng.get(key))[:80]
                break
        engines.append(
            {
                "id": eid,
                "label": label,
                "share": share_f,
                "status": _engine_status(share_f),
                "topDomain": top,
                "tone": tone,
            }
        )
        if share_f is not None:
            engine_bars.append(
                {
                    "id": eid,
                    "label": label,
                    "share": round(share_f, 1),
                    "tone": tone,
                }
            )

    insights: list[dict[str, Any]] = []
    for f in findings_critical[:5]:
        if not isinstance(f, dict):
            continue
        insights.append(
            {
                "severity": _insight_severity(str(f.get("severity") or "")),
                "title": str(f.get("title") or "Finding")[:120],
                "detail": str(f.get("detail") or "")[:220],
            }
        )

    n_crit = len(findings_critical)
    sentiment = max(8, min(100, 100 - n_crit * 8))
    if sentiment >= 75:
        sent_label = "Positive"
    elif sentiment >= 45:
        sent_label = "Mixed"
    else:
        sent_label = "At risk"

    rating = compute_rating(latest.aio_score, latest.geo_score, findings_all)
    series_rows = list_sov_snapshots(
        SovSnapshot, site_id=latest.id, user_id=user.id, limit=30
    )
    som_trend = [
        {"t": p.get("t"), "rate": p.get("rate")}
        for p in sov_series_for_chart(series_rows)
        if isinstance(p, dict)
    ]

    som = (engine_breakdown or {}).get("brand_sov")
    try:
        som_f = float(som) if som is not None else None
    except (TypeError, ValueError):
        som_f = None

    pages = int(latest.pages_analyzed or 0) or len(latest.crawl_pages or [])

    return {
        "ready": True,
        "domain": getattr(latest, "domain", None) or latest.url,
        "somPercent": som_f,
        "somDelta": None,
        "enginesTracked": len(engines),
        "recRank": rating.get("code"),
        "aioScore": latest.aio_score,
        "geoScore": latest.geo_score,
        "pagesAnalyzed": pages,
        "findingsCount": len(findings_all),
        "sentiment": sentiment,
        "sentimentLabel": sent_label,
        "evidenceLabel": (engine_breakdown or {}).get("label"),
        "engines": engines,
        "engineBars": engine_bars,
        "insights": insights,
        "somTrend": som_trend,
        "auditHref": audit_href,
        "reportHref": report_href,
    }
