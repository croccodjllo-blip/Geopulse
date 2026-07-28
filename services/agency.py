"""Agency / white-label helpers."""

from __future__ import annotations

import json
from typing import Any


def parse_agency_brand(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def dump_agency_brand(data: dict[str, Any]) -> str:
    clean = {
        "brand_name": str(data.get("brand_name") or "")[:80],
        "logo_url": str(data.get("logo_url") or "")[:300],
        "primary_color": str(data.get("primary_color") or "")[:20],
        "footer_note": str(data.get("footer_note") or "")[:200],
    }
    return json.dumps(clean, ensure_ascii=False)


def build_whitelabel_markdown(
    *,
    site: Any,
    agency: dict[str, Any] | None = None,
) -> str:
    agency = agency or {}
    brand = agency.get("brand_name") or "Centropic"
    lines = [
        f"# Report AIO/GEO — {getattr(site, 'domain', '')}",
        "",
        f"Preparato da **{brand}**",
        "",
        f"- URL: {getattr(site, 'url', '')}",
        f"- AIO: {getattr(site, 'aio_score', 'n/d')}",
        f"- GEO: {getattr(site, 'geo_score', 'n/d')}",
        f"- Rating: {(getattr(site, 'rating', None) or {}).get('code', 'n/d') if hasattr(site, 'rating') else 'n/d'}",
        "",
        "## Findings prioritari",
    ]
    findings = getattr(site, "findings", None) or []
    if callable(findings):
        findings = findings()
    for f in list(findings)[:20]:
        if str(f.get("severity")).lower() in {"critical", "warn"}:
            lines.append(f"- **{f.get('title')}** — {f.get('detail')}")
    note = agency.get("footer_note") or "Score diagnostici (probe/euristiche) salvo badge Misurato."
    lines.extend(["", f"_{note}_", ""])
    return "\n".join(lines)
