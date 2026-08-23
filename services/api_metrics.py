"""Stable read models for the Business API and outbound product webhooks.

Does not include artifact bodies or LLM samples. Pack apply events carry
SHA-256 checksums + Edge URLs so a customer plugin can apply idempotently.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from services.rating import compute_rating


def _crit_index(totals: dict[str, int]) -> dict[str, Any]:
    """Same formula as Panoramica: (crit×100 + warn×40) / totale."""
    crit = int(totals.get("critical") or 0)
    warn = int(totals.get("warn") or 0)
    ok = int(totals.get("ok") or 0)
    all_n = int(totals.get("all") or 0)
    if all_n <= 0:
        score = 0
    else:
        score = min(100, round((crit * 100 + warn * 40) / all_n))
    if score >= 55:
        band = "high"
    elif score >= 25:
        band = "mid"
    else:
        band = "ok"
    return {"score": score, "band": band, "crit": crit, "warn": warn, "ok": ok}


SCHEMA_SITE = "centropic.site/v1"
SCHEMA_RUNS = "centropic.runs/v1"
SCHEMA_EVENT = "centropic.event/v1"


def sha256_text(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _finding_summaries(findings: list[dict[str, Any]] | None, *, limit: int = 20) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in findings or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "severity": str(item.get("severity") or "")[:20],
                "title": str(item.get("title") or "")[:200],
                "category": str(item.get("category") or "")[:40],
            }
        )
        if len(out) >= limit:
            break
    return out


def _finding_totals(findings: list[dict[str, Any]] | None) -> dict[str, int]:
    totals = {"critical": 0, "warn": 0, "ok": 0, "all": 0}
    for item in findings or []:
        if not isinstance(item, dict):
            continue
        totals["all"] += 1
        sev = str(item.get("severity") or "").lower()
        if sev == "critical":
            totals["critical"] += 1
        elif sev == "warn":
            totals["warn"] += 1
        elif sev == "ok":
            totals["ok"] += 1
    return totals


def _sov_brief(site: Any) -> dict[str, Any] | None:
    signals = getattr(site, "signals", None) or {}
    if not isinstance(signals, dict):
        return None
    sov = signals.get("sov_measured")
    if not isinstance(sov, dict):
        return None
    engines: list[dict[str, Any]] = []
    for engine in sov.get("engines") or []:
        if not isinstance(engine, dict):
            continue
        engines.append(
            {
                "id": engine.get("id"),
                "label": engine.get("label"),
                "mention_rate": engine.get("mention_rate"),
                "evidence": engine.get("evidence"),
            }
        )
    return {
        "brand_mention_rate": sov.get("brand_mention_rate"),
        "evidence": sov.get("evidence"),
        "engines": engines,
    }


def pack_checksums(site: Any) -> dict[str, str]:
    """SHA-256 of generated artifacts — never the file bodies."""
    mapping = (
        ("llms.txt", "llms_txt"),
        ("organization.jsonld", "json_ld_artifact"),
        ("robots.txt", "robots_artifact"),
    )
    out: dict[str, str] = {}
    for name, attr in mapping:
        digest = sha256_text(getattr(site, attr, None))
        if digest:
            out[name] = digest
    return out


def site_metrics_payload(
    site: Any,
    *,
    findings_limit: int = 20,
) -> dict[str, Any]:
    findings = list(getattr(site, "findings", None) or [])
    rating = compute_rating(
        getattr(site, "aio_score", None),
        getattr(site, "geo_score", None),
        findings,
    )
    totals = _finding_totals(findings)
    crit = _crit_index(totals)
    hosted = bool(getattr(site, "signals_hosted", False) and getattr(site, "public_token", None))
    return {
        "ok": True,
        "schema": SCHEMA_SITE,
        "site": {
            "id": getattr(site, "id", None),
            "url": getattr(site, "url", None),
            "domain": getattr(site, "domain", None),
            "updated_at": _iso(getattr(site, "updated_at", None)),
        },
        "scores": {
            "aio": getattr(site, "aio_score", None),
            "geo": getattr(site, "geo_score", None),
            "cvi": rating.get("code"),
            "cvi_score": rating.get("score"),
        },
        "criticality": {
            "score": crit.get("score"),
            "band": crit.get("band"),
            "critical": crit.get("crit"),
            "warn": crit.get("warn"),
            "ok": crit.get("ok"),
        },
        "sov": _sov_brief(site),
        "findings": _finding_summaries(findings, limit=findings_limit),
        "edge": {
            "hosted": hosted,
            "version": int(getattr(site, "signals_version", 1) or 1),
        },
        "pack": {"checksums": pack_checksums(site)},
    }


def run_list_item(run: Any) -> dict[str, Any]:
    findings = []
    raw = getattr(run, "findings_json", None)
    if raw:
        try:
            import json

            parsed = json.loads(raw)
            findings = parsed if isinstance(parsed, list) else []
        except Exception:
            findings = []
    elif hasattr(run, "findings"):
        findings = list(getattr(run, "findings") or [])
    rating = compute_rating(
        getattr(run, "aio_score", None),
        getattr(run, "geo_score", None),
        findings,
    )
    return {
        "id": getattr(run, "id", None),
        "source": getattr(run, "source", None),
        "created_at": _iso(getattr(run, "created_at", None)),
        "aio": getattr(run, "aio_score", None),
        "geo": getattr(run, "geo_score", None),
        "cvi": rating.get("code"),
        "cvi_score": rating.get("score"),
        "findings_count": len(findings),
    }


def pack_ready_payload(
    site: Any,
    *,
    public_base: str,
    edge_full: bool,
    run_id: int | None = None,
) -> dict[str, Any]:
    checksums = pack_checksums(site)
    version = int(getattr(site, "signals_version", 1) or 1)
    site_id = getattr(site, "id", None)
    hosted = bool(getattr(site, "signals_hosted", False) and getattr(site, "public_token", None))
    token = getattr(site, "public_token", None) if hosted else None
    base = ""
    if hosted and token:
        root = (public_base or "https://centropic.ai").rstrip("/")
        base = f"{root}/e/{token}"
    endpoints: dict[str, str] = {}
    if base:
        endpoints["llms_txt"] = f"{base}/llms.txt"
        endpoints["signals_json"] = f"{base}/signals.json"
        if edge_full:
            endpoints["robots_txt"] = f"{base}/robots.txt"
            endpoints["organization_jsonld"] = f"{base}/organization.jsonld"
    return {
        "schema": SCHEMA_EVENT,
        "event": "pack.ready",
        "event_id": f"pack.ready:{site_id}:{version}:{run_id or 0}",
        "site": {
            "id": site_id,
            "url": getattr(site, "url", None),
            "domain": getattr(site, "domain", None),
        },
        "run_id": run_id,
        "signals_version": version,
        "idempotency_key": f"{site_id}:{version}",
        "checksums": checksums,
        "endpoints": endpoints,
        "apply": {
            "mode": "proxy" if hosted else "download",
            "note": (
                "Fetch artifacts from endpoints (or the dashboard pack). "
                "Apply once per idempotency_key; do not persist this payload's secrets."
            ),
        },
    }


def analysis_completed_payload(
    site: Any,
    *,
    run_id: int | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    metrics = site_metrics_payload(site, findings_limit=12)
    version = int(getattr(site, "signals_version", 1) or 1)
    site_id = getattr(site, "id", None)
    return {
        "schema": SCHEMA_EVENT,
        "event": "analysis.completed",
        "event_id": f"analysis.completed:{site_id}:{run_id or 0}:{version}",
        "source": source or "analyze",
        "run_id": run_id,
        "site": metrics["site"],
        "scores": metrics["scores"],
        "criticality": metrics["criticality"],
        "sov": metrics["sov"],
        "findings": metrics["findings"],
        "edge": metrics["edge"],
        "pack": metrics["pack"],
    }


def openapi_document(*, public_base: str = "https://centropic.ai") -> dict[str, Any]:
    """Minimal OpenAPI 3 document for /api/v1 (Business)."""
    root = (public_base or "https://centropic.ai").rstrip("/")
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Centropic API",
            "version": "1.1.0",
            "description": (
                "Business-only programmatic access. Bearer ct_… (legacy gp_… accepted). "
                "Read endpoints return scores and checksums, never pack file bodies."
            ),
        },
        "servers": [{"url": root}],
        "paths": {
            "/api/v1/analyze": {
                "post": {
                    "summary": "Enqueue an analysis",
                    "security": [{"bearerAuth": []}],
                }
            },
            "/api/v1/jobs/{job_id}": {
                "get": {"summary": "Poll an analyze job", "security": [{"bearerAuth": []}]}
            },
            "/api/v1/sites": {
                "get": {"summary": "List accessible sites", "security": [{"bearerAuth": []}]}
            },
            "/api/v1/sites/{site_id}": {
                "get": {
                    "summary": "Latest metrics (AIO, GEO, CVI, SoV, findings, checksums)",
                    "security": [{"bearerAuth": []}],
                }
            },
            "/api/v1/sites/{site_id}/runs": {
                "get": {"summary": "Analysis run history", "security": [{"bearerAuth": []}]}
            },
            "/api/v1/sites/{site_id}/edge": {
                "get": {"summary": "Edge + CMS connector metadata", "security": [{"bearerAuth": []}]}
            },
            "/api/v1/sites/{site_id}/edge/cms-bundle.zip": {
                "get": {"summary": "CMS connector ZIP", "security": [{"bearerAuth": []}]}
            },
            "/api/v1/openapi.json": {"get": {"summary": "This specification"}},
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"}
            }
        },
    }
