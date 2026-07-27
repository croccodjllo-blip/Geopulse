"""Publish Verify Loop — controlla se il pack suggerito è online."""

from __future__ import annotations

from typing import Any


def verify_published_pack(
    *,
    probes: dict[str, Any],
    previous_run: Any | None,
    scraped: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    llms = probes.get("llms") or {}
    robots = probes.get("robots") or {}
    ai = probes.get("ai") or {}
    sitemap = probes.get("sitemap") or {}

    checks = {
        "llms.txt": bool(llms.get("ok")),
        "robots.txt": bool(robots.get("ok")),
        "ai.txt": bool(ai.get("ok")),
        "sitemap.xml": bool(sitemap.get("ok")),
    }
    published = sum(1 for v in checks.values() if v)
    total = len(checks)

    # Had pack before?
    had_pack = False
    if previous_run is not None:
        had_pack = bool(
            (getattr(previous_run, "llms_txt", None) or "").strip()
            or (getattr(previous_run, "robots_artifact", None) or "").strip()
        )

    jsonld = bool((scraped or {}).get("has_json_ld"))
    checks["json-ld"] = jsonld
    published = sum(1 for v in checks.values() if v)
    total = len(checks)

    if published == total:
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Publish verify: pack online",
                "detail": "llms.txt, robots, ai.txt, sitemap e JSON-LD rilevati sul dominio.",
                "evidence": "measured",
            }
        )
    elif published >= 3:
        missing = [k for k, v in checks.items() if not v]
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Publish verify: pack parziale",
                "detail": "Mancano ancora: " + ", ".join(missing) + ". Pubblica gli artifact del ZIP.",
                "evidence": "measured",
            }
        )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn" if not had_pack else "critical",
                "title": "Pack non pubblicato",
                "detail": (
                    "Pochi asset AI online rispetto al pack generato. "
                    "Carica llms.txt / robots / schema dal download ZIP."
                ),
                "evidence": "measured",
            }
        )

    # Regression: previously had llms, now missing
    if previous_run is not None:
        try:
            blob = getattr(previous_run, "_crawl_blob", None)
            if callable(blob):
                pass
            prev_probes = {}
            raw = getattr(previous_run, "crawl_pages_json", None)
            if raw:
                import json

                data = json.loads(raw)
                if isinstance(data, dict):
                    prev_probes = data.get("probes") or {}
            prev_llms = bool((prev_probes.get("llms") or {}).get("ok"))
            if prev_llms and not checks["llms.txt"]:
                findings.append(
                    {
                        "category": "diff",
                        "severity": "critical",
                        "title": "Alert: llms.txt sparito dopo publish",
                        "detail": "Era online nella run precedente; ora il probe fallisce.",
                        "evidence": "measured",
                    }
                )
        except Exception:
            pass

    return {
        "checks": checks,
        "published": published,
        "total": total,
        "score": round(100.0 * published / max(total, 1)),
        "findings": findings,
    }
