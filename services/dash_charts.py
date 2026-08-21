"""Graphic instruments for the dashboard atelier.

Every series is derived from the current analysis. No fabricated
deltas, ranks, or sparklines — a trend appears only when SovSnapshot
rows exist; a run delta only when compare_with_previous produced one.
"""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urlparse


_CAT_ORDER = ("aio", "geo", "technical", "other")
_CAT_LABELS = {
    "aio": "AIO",
    "geo": "GEO",
    "technical": "Tech",
    "other": "Altro",
}
_SUITE_KEYS = (
    ("entity_graph", "Entity"),
    ("citability", "Citability"),
    ("schema_quality", "Schema"),
    ("publish_verify", "Publish"),
    ("llms_lint", "llms.txt"),
    ("locales", "Locales"),
)


def _clamp(n: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, n))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sev(raw: Any) -> str:
    s = str(raw or "").lower()
    if s == "critical":
        return "critical"
    if s in {"warn", "warning"}:
        return "warn"
    if s == "ok":
        return "ok"
    return "info"


def _cat(raw: Any) -> str:
    c = str(raw or "").lower()
    if c in {"aio", "geo", "technical"}:
        return c
    return "other"


def _path_of(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return "/"
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path[:64]


def _radar_nodes(breakdown: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not breakdown:
        return []
    radar = breakdown.get("radar") or {}
    labels = list(radar.get("labels") or [])
    engines = list(breakdown.get("engines") or [])
    nodes: list[dict[str, Any]] = []
    for i, eng in enumerate(engines):
        if str(eng.get("evidence") or "") == "pending":
            continue
        lbl = labels[i] if i < len(labels) else {}
        share = _as_float(eng.get("share")) or 0.0
        prop = _as_float(eng.get("propensity"))
        if prop is None:
            prop = share
        nodes.append(
            {
                "id": str(eng.get("id") or f"e{i}"),
                "label": str(eng.get("label") or ""),
                "share": int(round(share)),
                "propensity": int(round(_clamp(prop))),
                "evidence": str(eng.get("evidence") or "proxy"),
                "accent": str(eng.get("accent") or ""),
                "x": lbl.get("x"),
                "y": lbl.get("y"),
            }
        )
    return nodes


def _findings_mosaic(findings: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, int]] = {
        key: {"critical": 0, "warn": 0, "ok": 0, "info": 0} for key in _CAT_ORDER
    }
    cells: list[dict[str, str]] = []
    for finding in findings or []:
        if not isinstance(finding, dict):
            continue
        sev = _sev(finding.get("severity"))
        cat = _cat(finding.get("category"))
        buckets[cat][sev] = buckets[cat].get(sev, 0) + 1
        cells.append({"cat": cat, "sev": sev})

    rows: list[dict[str, Any]] = []
    totals = {"critical": 0, "warn": 0, "ok": 0, "info": 0, "all": 0}
    for key in _CAT_ORDER:
        b = buckets[key]
        total = sum(b.values())
        if total == 0:
            continue
        for sev in ("critical", "warn", "ok", "info"):
            totals[sev] += b[sev]
        totals["all"] += total
        open_n = b["critical"] + b["warn"]
        rows.append(
            {
                "id": key,
                "label": _CAT_LABELS[key],
                "critical": b["critical"],
                "warn": b["warn"],
                "ok": b["ok"],
                "info": b["info"],
                "total": total,
                "open": open_n,
                "crit_w": int(round(100 * b["critical"] / total)) if total else 0,
                "warn_w": int(round(100 * b["warn"] / total)) if total else 0,
                "ok_w": int(round(100 * b["ok"] / total)) if total else 0,
            }
        )
    return {"rows": rows, "totals": totals, "cells": cells[:48]}


def _suite_score(block: Any, key: str) -> int | None:
    if not isinstance(block, dict) or not block:
        return None
    if key == "locales":
        if block.get("score") is not None:
            return int(round(_clamp(_as_float(block.get("score")) or 0)))
        if block.get("lang"):
            extra = min(40, 10 * len(block.get("hreflang") or []))
            return int(_clamp(55 + extra))
        return 0
    score = _as_float(block.get("score"))
    if score is None:
        return None
    return int(round(_clamp(score)))


def _geo_petals(geo_suite: dict[str, Any] | None) -> list[dict[str, Any]]:
    suite = geo_suite or {}
    n = len(_SUITE_KEYS)
    cx, cy, radius = 90.0, 90.0, 62.0
    petals: list[dict[str, Any]] = []
    for i, (key, label) in enumerate(_SUITE_KEYS):
        score = _suite_score(suite.get(key), key)
        if score is None:
            continue
        angle = (i * (360.0 / n)) - 90.0
        rad = math.radians(angle)
        length = radius * (score / 100.0)
        petals.append(
            {
                "id": key,
                "label": label,
                "score": score,
                "x2": round(cx + length * math.cos(rad), 1),
                "y2": round(cy + length * math.sin(rad), 1),
                "lx": round(cx + (radius + 18) * math.cos(rad), 1),
                "ly": round(cy + (radius + 18) * math.sin(rad), 1),
            }
        )
    return petals


def _page_field(pages: list[dict[str, Any]] | None, *, aio: float, geo: float) -> dict[str, Any]:
    dots: list[dict[str, Any]] = []
    origin_x, origin_y = 22.0, 178.0
    scale = 1.56
    for page in (pages or [])[:40]:
        if not isinstance(page, dict):
            continue
        px = _as_float(page.get("aio_score"))
        py = _as_float(page.get("geo_score"))
        if px is None and py is None:
            continue
        ax = _clamp(px if px is not None else 0)
        gy = _clamp(py if py is not None else 0)
        dots.append(
            {
                "x": round(origin_x + ax * scale, 1),
                "y": round(origin_y - gy * scale, 1),
                "aio": int(round(ax)),
                "geo": int(round(gy)),
                "sev": _sev(page.get("severity")),
                "path": _path_of(str(page.get("url") or "")),
            }
        )
    brand = {
        "x": round(origin_x + _clamp(aio) * scale, 1),
        "y": round(origin_y - _clamp(geo) * scale, 1),
    }
    return {"dots": dots, "brand": brand, "n": len(dots)}


def _sov_spark(series: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    pts: list[tuple[float, float]] = []
    values: list[int] = []
    for row in series or []:
        rate = _as_float((row or {}).get("rate"))
        if rate is None:
            continue
        values.append(int(round(_clamp(rate))))
    if len(values) < 2:
        return None
    width, height, pad = 200.0, 52.0, 4.0
    span = max(1, len(values) - 1)
    inner_w = width - pad * 2
    inner_h = height - pad * 2
    coords: list[str] = []
    for i, val in enumerate(values):
        x = pad + (inner_w * i / span)
        y = pad + inner_h * (1.0 - val / 100.0)
        coords.append(f"{x:.1f},{y:.1f}")
        pts.append((x, y))
    first, last = values[0], values[-1]
    return {
        "points": " ".join(coords),
        "last_x": round(pts[-1][0], 1),
        "last_y": round(pts[-1][1], 1),
        "first": first,
        "last": last,
        "n": len(values),
        "delta": last - first,
    }


def _stave(score: float | None) -> list[dict[str, Any]]:
    n = int(round(_clamp(score or 0)))
    return [{"on": 1 if (i + 1) * 5 <= n else 0, "at": (i + 1) * 5} for i in range(20)]


def build_dash_charts(
    *,
    aio_score: int | float | None,
    geo_score: int | float | None,
    findings: list[dict[str, Any]] | None,
    crawl_pages: list[dict[str, Any]] | None,
    geo_suite: dict[str, Any] | None,
    engine_breakdown: dict[str, Any] | None,
    run_diff: dict[str, Any] | None = None,
    sov_trend: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the atelier payload for one site analysis."""
    aio = _as_float(aio_score) or 0.0
    geo = _as_float(geo_score) or 0.0
    mosaic = _findings_mosaic(list(findings or []))
    spark = _sov_spark(sov_trend)
    delta = None
    if isinstance(run_diff, dict) and run_diff.get("has_previous"):
        da = run_diff.get("delta_aio")
        dg = run_diff.get("delta_geo")
        if da is not None or dg is not None:
            delta = {"aio": da, "geo": dg}

    breakdown = engine_breakdown or {}
    return {
        "aio": int(round(aio)),
        "geo": int(round(geo)),
        "stave_aio": _stave(aio),
        "stave_geo": _stave(geo),
        "engines": _radar_nodes(breakdown),
        "radar": breakdown.get("radar") or {},
        "brand_sov": breakdown.get("brand_sov"),
        "rivals_sov": breakdown.get("rivals_sov"),
        "other_sov": breakdown.get("other_sov"),
        "has_competitors": bool(breakdown.get("has_competitors")),
        "evidence": breakdown.get("evidence") or "proxy",
        "mosaic": mosaic,
        "petals": _geo_petals(geo_suite),
        "field": _page_field(crawl_pages, aio=aio, geo=geo),
        "spark": spark,
        "delta": delta,
    }
