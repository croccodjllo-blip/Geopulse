"""Evidence helpers for findings honesty (measured vs estimated/proxy)."""

from __future__ import annotations

from typing import Any

_MEASURED_TITLE_HINTS = (
    "presente",
    "raggiungibile",
    "disponibile",
    "robots.txt",
    "llms.txt",
    "sitemap",
    "ai.txt",
    "humans.txt",
    "http ",
    "status",
    "title presente",
    "meta description utile",
    "json-ld",
    "organization",
    "website schema",
    "faq schema",
    "coverage sitemap",
    "policy bot",
    "bot ai",
)


def normalize_finding_evidence(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assicura evidence coerente: measured solo per segnali osservati/probe."""
    out: list[dict[str, Any]] = []
    for raw in findings or []:
        if not isinstance(raw, dict):
            continue
        f = dict(raw)
        ev = str(f.get("evidence") or "").lower()
        if ev not in {"measured", "proxy", "estimated"}:
            title = f"{f.get('title', '')} {f.get('detail', '')}".lower()
            if any(h in title for h in _MEASURED_TITLE_HINTS):
                ev = "measured"
            else:
                ev = "estimated"
            f["evidence"] = ev
        out.append(f)
    return out
