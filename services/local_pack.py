"""Local pack heuristics (NAP / LocalBusiness) — complementa brand digitale."""

from __future__ import annotations

from typing import Any


def analyze_local_signals(*, scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    entity = scraped.get("entity") or {}
    jsonld = scraped.get("jsonld") or {}
    types = set(jsonld.get("types") or [])
    is_local = "LocalBusiness" in types or bool(entity.get("has_local_business"))
    phones = scraped.get("phones") or []
    emails = scraped.get("emails") or []
    addresses = scraped.get("addresses") or []

    if not is_local:
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Local pack non richiesto",
                "detail": "Nessun LocalBusiness: focus su Organization digitale + email.",
                "evidence": "measured",
            }
        )
        return {
            "applicable": False,
            "score": 100,
            "findings": findings,
            "checklist": ["email_contact", "sameAs_external", "organization_schema"],
        }

    score = 20
    if phones:
        score += 25
    if addresses:
        score += 30
    if emails:
        score += 15
    if entity.get("telephone") and phones:
        score += 10
    score = min(100, score)

    missing = []
    if not phones:
        missing.append("telefono")
    if not addresses:
        missing.append("indirizzo")
    if missing:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Local pack incompleto",
                "detail": "Per LocalBusiness manca: " + ", ".join(missing) + ". Allinea NAP a GBP.",
                "evidence": "estimated",
            }
        )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Local pack NAP presente",
                "detail": "Telefono + indirizzo rilevati. Verifica coerenza con Google Business Profile.",
                "evidence": "measured",
            }
        )

    return {
        "applicable": True,
        "score": score,
        "phones": phones[:3],
        "emails": emails[:3],
        "addresses": addresses[:2],
        "findings": findings,
        "checklist": [
            "google_business_profile",
            "nap_consistency",
            "localbusiness_jsonld",
            "maps_citation",
        ],
    }
