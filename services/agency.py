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
        "primary_color": normalize_primary_color(data.get("primary_color")),
        "footer_note": str(data.get("footer_note") or "")[:200],
    }
    return json.dumps(clean, ensure_ascii=False)


_HEX_COLOR_RE = __import__("re").compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_primary_color(raw: Any, *, default: str = "#0B3D2E") -> str:
    """Allowlist CSS color to #RGB / #RRGGBB only (blocks CSS injection)."""
    value = str(raw or "").strip()
    if _HEX_COLOR_RE.fullmatch(value):
        return value.upper() if len(value) == 7 else value
    return default


def build_whitelabel_markdown(
    *,
    site: Any,
    agency: dict[str, Any] | None = None,
    sov_series: list[dict[str, Any]] | None = None,
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
    if sov_series:
        lines.extend(["", "## SoV measured (serie)", ""])
        for pt in sov_series[-12:]:
            rate = pt.get("rate")
            rate_s = f"{float(rate):.0f}%" if rate is not None else "n/d"
            lines.append(f"- {pt.get('t', '')[:19]} — brand mention {rate_s}")
    note = agency.get("footer_note") or "Score diagnostici (probe/euristiche) salvo badge Misurato."
    lines.extend(["", f"_{note}_", ""])
    return "\n".join(lines)


def build_whitelabel_html(
    *,
    site: Any,
    agency: dict[str, Any] | None = None,
    sov_series: list[dict[str, Any]] | None = None,
) -> str:
    """Client-ready HTML report (no Centropic chrome)."""
    agency = agency or {}
    brand = agency.get("brand_name") or "Centropic"
    color = normalize_primary_color(agency.get("primary_color"))
    logo = agency.get("logo_url") or ""
    domain = getattr(site, "domain", "") or ""
    url = getattr(site, "url", "") or ""
    aio = getattr(site, "aio_score", None)
    geo = getattr(site, "geo_score", None)
    findings = getattr(site, "findings", None) or []
    if callable(findings):
        findings = findings()
    items = []
    for f in list(findings)[:20]:
        if str(f.get("severity")).lower() in {"critical", "warn"}:
            items.append(
                f"<li><strong>{_esc(f.get('title'))}</strong> — {_esc(f.get('detail'))}</li>"
            )
    sov_rows = ""
    if sov_series:
        cells = []
        for pt in sov_series[-12:]:
            rate = pt.get("rate")
            rate_s = f"{float(rate):.0f}%" if rate is not None else "n/d"
            cells.append(f"<tr><td>{_esc(str(pt.get('t', ''))[:19])}</td><td>{rate_s}</td></tr>")
        sov_rows = (
            "<h2>SoV measured</h2><table><thead><tr><th>Quando</th><th>Brand</th></tr></thead>"
            f"<tbody>{''.join(cells)}</tbody></table>"
        )
    logo_html = f'<img src="{_esc(logo)}" alt="" style="max-height:48px" />' if logo else ""
    note = agency.get("footer_note") or "Score diagnostici salvo badge Misurato."
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8" />
<title>Report AIO/GEO — {_esc(domain)}</title>
<style>
body{{font-family:Georgia,serif;margin:0;background:#f7f5f0;color:#1a1a1a}}
.wrap{{max-width:720px;margin:0 auto;padding:2.5rem 1.25rem}}
.brand{{color:{color};font-size:1.4rem;font-weight:700;margin:0 0 .5rem}}
h1{{font-size:1.75rem;margin:.25rem 0 1rem}}
.meta{{color:#444;margin-bottom:1.5rem}}
ul{{padding-left:1.2rem}}
table{{width:100%;border-collapse:collapse;margin:1rem 0}}
td,th{{border-bottom:1px solid #ddd;padding:.4rem .2rem;text-align:left}}
footer{{margin-top:2rem;font-size:.9rem;color:#555}}
</style>
</head>
<body>
<div class="wrap">
{logo_html}
<p class="brand">{_esc(brand)}</p>
<h1>Report AIO/GEO — {_esc(domain)}</h1>
<p class="meta">URL: {_esc(url)} · AIO {aio if aio is not None else 'n/d'} · GEO {geo if geo is not None else 'n/d'}</p>
<h2>Findings prioritari</h2>
<ul>{''.join(items) or '<li>Nessun finding critico.</li>'}</ul>
{sov_rows}
<footer>{_esc(note)}</footer>
</div>
</body>
</html>
"""


def _esc(value: Any) -> str:
    s = "" if value is None else str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
