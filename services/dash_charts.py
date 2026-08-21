"""Graphic instruments for the dashboard atelier.

Every series is derived from the current analysis. No fabricated
deltas, ranks, or sparklines — a trend appears only when SovSnapshot
rows exist; a run delta only when compare_with_previous produced one.
"""

from __future__ import annotations

import math
from datetime import datetime
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
        node: dict[str, Any] = {
            "id": str(eng.get("id") or f"e{i}"),
            "label": str(eng.get("label") or ""),
            "share": int(round(share)),
            "propensity": int(round(_clamp(prop))),
            "evidence": str(eng.get("evidence") or "proxy"),
            "accent": str(eng.get("accent") or ""),
            "x": lbl.get("x"),
            "y": lbl.get("y"),
        }
        rate = _as_float(eng.get("mention_rate"))
        if rate is not None:
            node["mention_rate"] = int(round(_clamp(rate)))
        if eng.get("samples") is not None:
            try:
                node["samples"] = int(eng.get("samples") or 0)
            except (TypeError, ValueError):
                pass
        if eng.get("access"):
            node["access"] = str(eng.get("access"))
        if eng.get("band"):
            node["band"] = str(eng.get("band"))
        nodes.append(node)
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
                "url": str(page.get("url") or ""),
            }
        )
    brand = {
        "x": round(origin_x + _clamp(aio) * scale, 1),
        "y": round(origin_y - _clamp(geo) * scale, 1),
    }
    return {"dots": dots, "brand": brand, "n": len(dots)}


def _parse_spark_when(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sov_spark(series: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    pts: list[tuple[float, float]] = []
    values: list[int] = []
    dates: list[datetime | None] = []
    for row in series or []:
        rate = _as_float((row or {}).get("rate"))
        if rate is None:
            continue
        values.append(int(round(_clamp(rate))))
        dates.append(
            _parse_spark_when((row or {}).get("t") or (row or {}).get("created_at"))
        )
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
    labels = _audit_axis_labels(dates) if any(d is not None for d in dates) else [""] * len(values)
    # Dates live in HTML under the SVG; keep a tight plot so labels stay small.
    aw, ah, al, ar, at, ab = 320.0, 120.0, 8.0, 8.0, 8.0, 8.0
    a_w = aw - al - ar
    a_h = ah - at - ab
    marks: list[dict[str, Any]] = []
    line_bits: list[str] = []
    for i, val in enumerate(values):
        x = al + (a_w * i / span)
        y = at + a_h * (1.0 - val / 100.0)
        cmd = "M" if i == 0 else "L"
        line_bits.append(f"{cmd}{x:.1f},{y:.1f}")
        marks.append({"x": round(x, 1), "y": round(y, 1), "v": val})
    first_x, first_y = marks[0]["x"], marks[0]["y"]
    last_x_a, last_y_a = marks[-1]["x"], marks[-1]["y"]
    baseline = at + a_h
    area = (
        f"M{first_x:.1f},{baseline:.1f} "
        + " ".join(f"L{m['x']:.1f},{m['y']:.1f}" for m in marks)
        + f" L{last_x_a:.1f},{baseline:.1f} Z"
    )
    show_every = 1 if len(marks) <= 6 else 2
    ticks_x: list[dict[str, Any]] = []
    for i, (mark, label) in enumerate(zip(marks, labels)):
        show = i == 0 or i == len(marks) - 1 or i % show_every == 0
        ticks_x.append({"x": mark["x"], "label": label if show else ""})
    return {
        "points": " ".join(coords),
        "last_x": round(pts[-1][0], 1),
        "last_y": round(pts[-1][1], 1),
        "first": first,
        "last": last,
        "n": len(values),
        "delta": last - first,
        "area": area,
        "line": " ".join(line_bits),
        "marks": marks,
        "ticks_x": ticks_x,
        "baseline": baseline,
        "left": al,
        "right_x": aw - ar,
        "grid_y": [
            {"y": round(at, 1), "v": 100},
            {"y": round(at + a_h * 0.5, 1), "v": 50},
            {"y": round(baseline, 1), "v": 0},
        ],
        "width": 320,
        "height": 120,
    }


def _stave(score: float | None) -> list[dict[str, Any]]:
    n = int(round(_clamp(score or 0)))
    return [{"on": 1 if (i + 1) * 5 <= n else 0, "at": (i + 1) * 5} for i in range(20)]


def _orbit(engines: list[dict[str, Any]]) -> dict[str, Any]:
    """Aerospace ellipse: brand at the nucleus, engines as satellites.

    Inspired by mission-control scopes (NASA/SpaceX telemetry) rather than
    a spider radar. Node radius tracks share; angle is evenly spaced.
    """
    cx, cy = 160.0, 100.0
    rx, ry = 124.0, 72.0
    nodes: list[dict[str, Any]] = []
    live = [e for e in engines if isinstance(e, dict)]
    n = len(live)
    for i, eng in enumerate(live):
        angle = (i / max(n, 1)) * 2.0 * math.pi - math.pi / 2.0
        ox = round(cx + rx * math.cos(angle), 1)
        oy = round(cy + ry * math.sin(angle), 1)
        share = float(eng.get("share") or 0)
        node_r = round(4.2 + (_clamp(share) / 100.0) * 9.5, 1)
        outward = 1.2
        lx = round(cx + rx * outward * math.cos(angle), 1)
        ly = round(cy + ry * outward * math.sin(angle), 1)
        cosine = math.cos(angle)
        if cosine > 0.28:
            anchor = "start"
        elif cosine < -0.28:
            anchor = "end"
        else:
            anchor = "middle"
        nodes.append(
            {
                "id": str(eng.get("id") or f"e{i}"),
                "label": str(eng.get("label") or ""),
                "share": int(eng.get("share") or 0),
                "propensity": int(eng.get("propensity") or 0),
                "accent": str(eng.get("accent") or ""),
                "ox": ox,
                "oy": oy,
                "or": node_r,
                "lx": lx,
                "ly": ly,
                "anchor": anchor,
                "dy": -3 if math.sin(angle) < -0.15 else 11,
            }
        )
    return {"cx": cx, "cy": cy, "rx": rx, "ry": ry, "nodes": nodes}


def _meridian(field: dict[str, Any], *, aio: float) -> dict[str, Any]:
    """Horizontal AIO axis with page ticks — FT/Bloomberg baseline, not a scatter."""
    ticks: list[dict[str, Any]] = []
    for i, dot in enumerate(list(field.get("dots") or [])[:24]):
        ticks.append(
            {
                "id": i,
                "x": int(dot.get("aio") or 0),
                "aio": int(dot.get("aio") or 0),
                "geo": int(dot.get("geo") or 0),
                "sev": str(dot.get("sev") or "info"),
                "path": str(dot.get("path") or "/"),
                "url": str(dot.get("url") or ""),
            }
        )
    return {
        "ticks": ticks,
        "brand_x": int(round(_clamp(aio))),
        "n": int(field.get("n") or len(ticks)),
    }


def _sov_split(breakdown: dict[str, Any] | None) -> dict[str, Any]:
    raw = breakdown or {}
    brand = int(round(_as_float(raw.get("brand_sov")) or 0))
    rivals = int(round(_as_float(raw.get("rivals_sov")) or 0))
    other = int(round(_as_float(raw.get("other_sov")) or 0))
    total = brand + rivals + other
    if total <= 0:
        return {"brand": 0, "rivals": 0, "other": 0, "total": 0}
    # Keep visual widths summing to 100 without inventing mass.
    return {"brand": brand, "rivals": rivals, "other": other, "total": total}


def _suite_rows(geo_suite: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, label in _SUITE_KEYS:
        score = _suite_score((geo_suite or {}).get(key), key)
        if score is None:
            continue
        rows.append({"id": key, "label": label, "score": score})
    return rows


def _page_hist(pages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    bins = [
        {"id": "0-19", "lo": 0, "hi": 19, "n": 0},
        {"id": "20-39", "lo": 20, "hi": 39, "n": 0},
        {"id": "40-59", "lo": 40, "hi": 59, "n": 0},
        {"id": "60-79", "lo": 60, "hi": 79, "n": 0},
        {"id": "80-100", "lo": 80, "hi": 100, "n": 0},
    ]
    counted = 0
    for page in pages or []:
        if not isinstance(page, dict):
            continue
        aio = _as_float(page.get("aio_score"))
        if aio is None:
            continue
        score = int(round(_clamp(aio)))
        counted += 1
        for bucket in bins:
            if bucket["lo"] <= score <= bucket["hi"]:
                bucket["n"] += 1
                break
    peak = max((b["n"] for b in bins), default=0) or 1
    for bucket in bins:
        bucket["w"] = int(round(100 * bucket["n"] / peak)) if counted else 0
    return bins if counted else []


def _page_stats(pages: list[dict[str, Any]] | None) -> dict[str, Any]:
    aios: list[float] = []
    geos: list[float] = []
    words: list[float] = []
    latencies: list[float] = []
    rows: list[dict[str, Any]] = []
    for page in pages or []:
        if not isinstance(page, dict):
            continue
        aio = _as_float(page.get("aio_score"))
        geo = _as_float(page.get("geo_score"))
        if aio is not None:
            aios.append(_clamp(aio))
        if geo is not None:
            geos.append(_clamp(geo))
        wc = _as_float(page.get("word_count"))
        if wc is not None:
            words.append(wc)
        ms = _as_float(page.get("response_ms"))
        if ms is not None:
            latencies.append(ms)
        if len(rows) < 12:
            status = page.get("status_code")
            try:
                status_n = int(status) if status is not None else None
            except (TypeError, ValueError):
                status_n = None
            rows.append(
                {
                    "path": _path_of(str(page.get("url") or "")),
                    "url": str(page.get("url") or ""),
                    "title": str(page.get("title") or "")[:72],
                    "aio": int(round(_clamp(aio))) if aio is not None else None,
                    "geo": int(round(_clamp(geo))) if geo is not None else None,
                    "words": int(wc) if wc is not None else None,
                    "ms": int(ms) if ms is not None else None,
                    "status": status_n,
                    "sev": _sev(page.get("severity")),
                }
            )

    def _avg(vals: list[float]) -> int | None:
        if not vals:
            return None
        return int(round(sum(vals) / len(vals)))

    return {
        "n": len(pages or []),
        "scored": len(aios),
        "avg_aio": _avg(aios),
        "avg_geo": _avg(geos),
        "min_aio": int(round(min(aios))) if aios else None,
        "max_aio": int(round(max(aios))) if aios else None,
        "min_geo": int(round(min(geos))) if geos else None,
        "max_geo": int(round(max(geos))) if geos else None,
        "avg_words": _avg(words),
        "avg_ms": _avg(latencies),
        "rows": rows,
    }


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
    engines = _radar_nodes(breakdown)
    field = _page_field(crawl_pages, aio=aio, geo=geo)
    pages = _page_stats(crawl_pages)
    suite = _suite_rows(geo_suite)
    ranked = sorted(engines, key=lambda e: int(e.get("share") or 0), reverse=True)
    return {
        "aio": int(round(aio)),
        "geo": int(round(geo)),
        "stave_aio": _stave(aio),
        "stave_geo": _stave(geo),
        "engines": engines,
        "ranked": ranked,
        "radar": breakdown.get("radar") or {},
        "orbit": _orbit(engines),
        "meridian": _meridian(field, aio=aio),
        "split": _sov_split(breakdown),
        "brand_sov": breakdown.get("brand_sov"),
        "rivals_sov": breakdown.get("rivals_sov"),
        "other_sov": breakdown.get("other_sov"),
        "has_competitors": bool(breakdown.get("has_competitors")),
        "evidence": breakdown.get("evidence") or "proxy",
        "label": breakdown.get("label") or "",
        "top_engine": breakdown.get("top_engine"),
        "mosaic": mosaic,
        "suite": suite,
        "petals": _geo_petals(geo_suite),
        "hist": _page_hist(crawl_pages),
        "pages": pages,
        "field": field,
        "spark": spark,
        "delta": delta,
    }


def _audit_axis_labels(dates: list[Any]) -> list[str]:
    """Short axis ticks; include time when two audits share a calendar day."""
    live = [d for d in dates if d is not None]
    days = [d.strftime("%Y-%m-%d") for d in live]
    same_day = len(days) != len(set(days))
    multi_year = len({d.year for d in live}) > 1
    labels: list[str] = []
    for created in dates:
        if created is None:
            labels.append("—")
        elif same_day:
            labels.append(created.strftime("%d/%m %H:%M"))
        elif multi_year:
            labels.append(created.strftime("%d/%m/%y"))
        else:
            labels.append(created.strftime("%d/%m"))
    return labels


def build_history_trend(
    items: list[Any] | None,
    *,
    limit: int = 12,
) -> dict[str, Any] | None:
    """Line chart of the latest scored audits (newest first in, chrono out)."""
    scored: list[Any] = []
    for item in list(items or []):
        aio = _as_float(getattr(item, "aio_score", None))
        geo = _as_float(getattr(item, "geo_score", None))
        if aio is None and geo is None:
            continue
        scored.append(item)
        if len(scored) >= max(2, int(limit)):
            break
    if len(scored) < 2:
        return None

    chronological = list(reversed(scored))
    dates = [getattr(item, "created_at", None) for item in chronological]
    labels = _audit_axis_labels(dates)
    series: list[dict[str, Any]] = []
    for item, created, label in zip(chronological, dates, labels):
        aio = _as_float(getattr(item, "aio_score", None))
        geo = _as_float(getattr(item, "geo_score", None))
        series.append(
            {
                "aio": int(round(_clamp(aio))) if aio is not None else None,
                "geo": int(round(_clamp(geo))) if geo is not None else None,
                "label": label,
                "when": created.strftime("%d/%m/%Y %H:%M") if created is not None else "—",
                "domain": str(getattr(item, "domain", "") or ""),
            }
        )

    width, height = 720.0, 268.0
    left, right, top, bottom = 40.0, 22.0, 20.0, 52.0
    inner_w = width - left - right
    inner_h = height - top - bottom
    span = max(1, len(series) - 1)
    baseline = top + inner_h

    def _xy(index: int, value: float) -> tuple[float, float]:
        x = left + inner_w * index / span
        y = top + inner_h * (1.0 - _clamp(value) / 100.0)
        return round(x, 1), round(y, 1)

    def _path(key: str) -> tuple[str, list[dict[str, Any]]]:
        bits: list[str] = []
        marks: list[dict[str, Any]] = []
        for i, row in enumerate(series):
            val = row.get(key)
            if val is None:
                continue
            x, y = _xy(i, float(val))
            bits.append(f"{'M' if not bits else 'L'}{x:.1f},{y:.1f}")
            marks.append(
                {
                    "x": x,
                    "y": y,
                    "v": int(val),
                    "label": row["label"],
                    "latest": i == len(series) - 1,
                }
            )
        return " ".join(bits), marks

    aio_line, aio_marks = _path("aio")
    geo_line, geo_marks = _path("geo")
    show_every = 1 if len(series) <= 8 else 2
    ticks_x = []
    for i, row in enumerate(series):
        x, _y = _xy(i, 0)
        show = i == 0 or i == len(series) - 1 or i % show_every == 0
        ticks_x.append({"x": x, "label": row["label"] if show else ""})

    grid_y = []
    for v in (100, 75, 50, 25, 0):
        _x, y = _xy(0, float(v))
        grid_y.append({"y": y, "v": v, "x1": left, "x2": width - right})

    aios = [int(r["aio"]) for r in series if r.get("aio") is not None]
    geos = [int(r["geo"]) for r in series if r.get("geo") is not None]
    return {
        "n": len(series),
        "width": 720,
        "height": 268,
        "left": left,
        "baseline": baseline,
        "aio_line": aio_line,
        "geo_line": geo_line,
        "aio_marks": aio_marks,
        "geo_marks": geo_marks,
        "ticks_x": ticks_x,
        "grid_y": grid_y,
        "rows": series,
        "first_aio": aios[0] if aios else None,
        "last_aio": aios[-1] if aios else None,
        "first_geo": geos[0] if geos else None,
        "last_geo": geos[-1] if geos else None,
        "delta_aio": (aios[-1] - aios[0]) if len(aios) >= 2 else None,
        "delta_geo": (geos[-1] - geos[0]) if len(geos) >= 2 else None,
        "latest_when": series[-1]["when"],
    }
