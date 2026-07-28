"""Schema.org quality validator (presence ≠ validity)."""

from __future__ import annotations

from typing import Any


def _as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def validate_schema_quality(*, scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    jsonld = scraped.get("jsonld") or {}
    types = set(jsonld.get("types") or [])
    org_nodes = jsonld.get("org_nodes") or []
    issues: list[str] = []
    score = 40 if types else 10

    if not types:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Schema assente",
                "detail": "Nessun JSON-LD tipizzato rilevato.",
                "evidence": "measured",
            }
        )
        return {"score": score, "issues": ["no_jsonld"], "types": [], "findings": findings}

    if "Organization" in types or "LocalBusiness" in types:
        score += 15
        if org_nodes:
            node = org_nodes[0] if isinstance(org_nodes[0], dict) else {}
            if not node.get("name"):
                issues.append("org_missing_name")
            if not node.get("url"):
                issues.append("org_missing_url")
            if not (node.get("email") or node.get("telephone")):
                issues.append("org_missing_contact")
            logo = node.get("logo")
            if not logo:
                issues.append("org_missing_logo")
            same = [s for s in _as_list(node.get("sameAs")) if isinstance(s, str)]
            if same and all(
                (scraped.get("domain") or "") in s for s in same if scraped.get("domain")
            ):
                issues.append("sameAs_self_only")
    else:
        issues.append("missing_organization")

    if "WebSite" in types:
        score += 10
    else:
        issues.append("missing_website")

    if jsonld.get("has_faq_page"):
        n = int(jsonld.get("faq_questions") or 0)
        score += 10 if n >= 2 else 4
        if n < 2:
            issues.append("faq_too_thin")
        html_faq = scraped.get("html_faq") or {}
        if html_faq.get("html_faq_likely") and n == 0:
            issues.append("faq_html_without_schema")

    if "SoftwareApplication" in types or "Product" in types:
        score += 8

    score = max(0, min(100, score - len(issues) * 6))

    if not issues:
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "Schema quality OK",
                "detail": f"Tipi: {', '.join(sorted(types)[:8])}.",
                "evidence": "measured",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Schema quality issues",
                "detail": "; ".join(issues[:6]),
                "evidence": "estimated",
            }
        )

    return {
        "score": score,
        "issues": issues,
        "types": sorted(types),
        "findings": findings,
    }
