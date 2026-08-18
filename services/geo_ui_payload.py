"""Build JSON payload for the React GEO Live Charts embed."""

from __future__ import annotations

from typing import Any

from flask_babel import gettext as _

from centropic.tenancy import sites_query_for_user
from services.engine_breakdown import apply_measured_sov, compute_engine_breakdown
from services.i18n import translate_stored
from services.rating import compute_rating
from services.sov_graph import list_sov_snapshots, sov_series_for_chart

_TONES = ("emerald", "cyan", "steel", "amber")


def _engine_status(share: float | None) -> str:
    if share is None:
        return "unknown"
    if share >= 45:
        return "dominant"
    if share >= 30:
        return "optimal"
    return "needs_action"


def _insight_severity(raw: str) -> str:
    """Preserve finding severity — never remap critical→success."""
    sev = (raw or "").lower()
    if sev == "critical":
        return "critical"
    if sev in {"warn", "warning"}:
        return "warn"
    return "info"


def _severity_label(sev: str) -> str:
    """Native severity chip for Charts insights (Italian msgids)."""
    if sev == "critical":
        return _("Critico")
    if sev == "warn":
        return _("Attenzione")
    return _("Info")


def _issue_pressure(n_open: int) -> tuple[int, str]:
    """Honest KPI: open critical+warn count (not model sentiment).

    Returns Italian gettext msgids; translate at payload-build time.
    """
    n = max(0, int(n_open))
    if n <= 0:
        return n, "In ordine"
    if n <= 2:
        return n, "Da monitorare"
    if n <= 5:
        return n, "Elevata"
    return n, "Alta"


def _geo_ui_chrome() -> dict[str, str]:
    """Server-translated chrome for the React Charts embed."""
    return {
        "insightsTitle": _("Insight GEO actionable"),
        "insightsEmpty": _(
            "Nessun finding critico/warn nell'ultimo audit."
        ),
        "pagesScored": _("Pagine valutate"),
        "findingsInLastAudit": _("findings nell'ultimo audit"),
        "chartsTitle": _("GEO Charts"),
        "overviewTitle": _("Panoramica GEO"),
        "emptyBody": _(
            "Nessuna analisi ancora. Esegui un audit per vedere Share of Model, "
            "engine breakdown e insight dal tuo sito — niente dati demo."
        ),
        "runAudit": _("Esegui audit GEO"),
        "liveSubtitle": _(
            "Share of Model e visibilità AI dall'ultimo audit."
        ),
        "rangeLast30": _("Ultimi 30 giorni"),
        "rangeLast7": _("Ultimi 7 giorni"),
        "rangeQuarter": _("Trimestre in corso"),
        "rangeComingSoon": _("Range storico: in arrivo"),
        "somLabel": _("Share of Model"),
        "acrossEngines": _("su %(n)s engine LLM tracciati"),
        "recRankLabel": _("Ranking AI"),
        "recRankHint": _("Grado composito da AIO/GEO"),
        "issuePressureTitle": _("Pressione findings"),
        "issuePressureHint": _(
            "Critical + warn aperti (non sentiment del modello)"
        ),
        "somTrendTitle": _("Trend Share of Model"),
        "breakdownTitle": _("Breakdown visibilità LLM"),
        "viewReport": _("Vedi report dettagliato"),
        "enginesEmpty": _(
            "Nessun engine breakdown ancora — riesegui l'audit."
        ),
        "colEngine": _("Engine"),
        "colShare": _("Share of Voice"),
        "colTopDomain": _("Dominio più citato"),
        "colStatus": _("Stato"),
        "statusDominant": _("Dominante"),
        "statusOptimal": _("Ottimale"),
        "statusNeedsAction": _("Da migliorare"),
        "statusUnknown": "—",
    }


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
        sites_query_for_user(SiteAnalysis, user)
        .order_by(SiteAnalysis.updated_at.desc(), SiteAnalysis.created_at.desc())
        .first()
    )
    ui = _geo_ui_chrome()
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
        "issuePressure": None,
        "issuePressureLabel": None,
        "evidenceLabel": None,
        "engines": [],
        "engineBars": [],
        "insights": [],
        "somTrend": [],
        "auditHref": audit_href,
        "reportHref": report_href,
        "ui": ui,
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
        sev = _insight_severity(str(f.get("severity") or ""))
        title_raw = str(f.get("title") or "Finding")
        detail_raw = str(f.get("detail") or "")
        insights.append(
            {
                "severity": sev,
                "severityLabel": _severity_label(sev),
                "title": translate_stored(title_raw)[:120],
                "detail": translate_stored(detail_raw)[:220],
            }
        )

    n_crit = len(findings_critical)
    issue_n, issue_msgid = _issue_pressure(n_crit)
    issue_label = _(issue_msgid)

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
        "issuePressure": issue_n,
        "issuePressureLabel": issue_label,
        "evidenceLabel": (
            translate_stored(str(ev_label))
            if (ev_label := (engine_breakdown or {}).get("label"))
            else None
        ),
        "engines": engines,
        "engineBars": engine_bars,
        "insights": insights,
        "somTrend": som_trend,
        "auditHref": audit_href,
        "reportHref": report_href,
        "ui": ui,
    }
