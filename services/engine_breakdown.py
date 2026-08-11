"""Proxy Share-of-Voice per AI engine (stimato, non measured).

Deriva propensity e composizione SoV da AIO/GEO, policy bot e findings,
finché non esiste polling multi-LLM reale. Sempre etichettato evidence=proxy.
"""

from __future__ import annotations

import math
from typing import Any

from services.signals import _bot_policy

# id → bot robots correlato (None = nessun mapping diretto)
ENGINES: tuple[dict[str, Any], ...] = (
    {
        "id": "openai",
        "label": "ChatGPT",
        "vendor": "OpenAI",
        "bot": "GPTBot",
        "accent": "#10A37F",
        "weight": 1.15,  # peso relativo nel mercato answer-engine
    },
    {
        "id": "google",
        "label": "Gemini",
        "vendor": "Google Gemini (API)",
        "bot": "Google-Extended",
        "accent": "#4285F4",
        "weight": 1.05,
    },
    {
        "id": "anthropic",
        "label": "Claude",
        "vendor": "Anthropic",
        "bot": "ClaudeBot",
        "accent": "#D4A27F",
        "weight": 0.95,
    },
    {
        "id": "perplexity",
        "label": "Perplexity",
        "vendor": "Perplexity",
        "bot": "PerplexityBot",
        "accent": "#20B8CD",
        "weight": 1.0,
    },
    {
        "id": "xai",
        "label": "Grok",
        "vendor": "xAI",
        "bot": None,
        "accent": "#E8E8E8",
        "weight": 0.9,
    },
    {
        "id": "bing",
        "label": "Azure AI",
        "vendor": "Microsoft Azure",
        "bot": None,
        "accent": "#5B6B7A",
        "weight": 0.85,
    },
)


def _clamp(n: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(round(max(lo, min(hi, n))))


def _finding_hits(findings: list[dict[str, Any]], *needles: str) -> int:
    blob = " ".join(
        f"{(f or {}).get('title', '')} {(f or {}).get('detail', '')}".lower()
        for f in findings or []
    )
    return sum(1 for n in needles if n.lower() in blob)


def _severity_penalty(findings: list[dict[str, Any]]) -> float:
    pen = 0.0
    for f in findings or []:
        sev = str((f or {}).get("severity") or "").lower()
        if sev == "critical":
            pen += 4.5
        elif sev == "warn":
            pen += 2.0
    return min(pen, 28.0)


def _column_geometry(
    engines: list[dict[str, Any]],
    *,
    width: float = 280.0,
    height: float = 168.0,
    pad_x: float = 18.0,
    pad_top: float = 22.0,
    pad_bottom: float = 34.0,
) -> dict[str, Any]:
    """Precompute a vertical column chart from per-engine propensity.

    Server-rendered SVG bars — clearer than a spider/radar when many engines
    sit near the same high band (the old radar looked like a filled blob).
    """
    n = len(engines)
    if n < 1:
        return {"bars": [], "width": width, "height": height, "baseline": height - pad_bottom}

    plot_w = width - (2 * pad_x)
    plot_h = height - pad_top - pad_bottom
    gap = 10.0 if n <= 6 else 6.0
    bar_w = max(12.0, (plot_w - gap * (n - 1)) / n)
    baseline = pad_top + plot_h
    bars: list[dict[str, Any]] = []
    for i, eng in enumerate(engines):
        value = max(0.0, min(100.0, float(eng.get("propensity", 0) or 0)))
        h = plot_h * (value / 100.0)
        x = pad_x + i * (bar_w + gap)
        y = baseline - h
        cx = x + bar_w / 2.0
        bars.append(
            {
                "x": round(x, 1),
                "y": round(y, 1),
                "w": round(bar_w, 1),
                "h": round(max(h, 1.5 if value > 0 else 0.0), 1),
                "cx": round(cx, 1),
                "label": eng.get("label", ""),
                "value": int(round(value)),
                "accent": eng.get("accent") or "var(--plan-accent)",
                "ly": round(height - 12, 1),
                "vy": round(max(10.0, y - 6), 1),
            }
        )

    return {
        "bars": bars,
        "width": width,
        "height": height,
        "baseline": round(baseline, 1),
        "pad_x": pad_x,
        "plot_h": round(plot_h, 1),
    }


def _radar_geometry(
    engines: list[dict[str, Any]],
    *,
    center: float = 100.0,
    radius: float = 78.0,
) -> dict[str, Any]:
    """Legacy spider helper (kept for tests/import stability; UI uses columns)."""
    n = len(engines)
    if n < 3:
        return {"points": "", "rings": [], "axes": [], "labels": []}

    def _point(angle_deg: float, r: float) -> tuple[float, float]:
        rad = math.radians(angle_deg - 90)
        return (center + r * math.cos(rad), center + r * math.sin(rad))

    step = 360.0 / n
    data_points: list[str] = []
    axes: list[str] = []
    labels: list[dict[str, Any]] = []
    for i, eng in enumerate(engines):
        angle = i * step
        value = max(0.0, min(100.0, float(eng.get("propensity", 0) or 0)))
        x, y = _point(angle, radius * (value / 100.0))
        data_points.append(f"{x:.1f},{y:.1f}")
        ax, ay = _point(angle, radius)
        axes.append(f"{center:.1f},{center:.1f} {ax:.1f},{ay:.1f}")
        lx, ly = _point(angle, radius + 20)
        cos_a = math.cos(math.radians(angle - 90))
        sin_a = math.sin(math.radians(angle - 90))
        anchor = "middle" if abs(cos_a) < 0.35 else ("start" if cos_a > 0 else "end")
        dy = "0.32em" if sin_a <= 0.35 else "0.9em"
        labels.append(
            {
                "x": round(lx, 1),
                "y": round(ly, 1),
                "anchor": anchor,
                "dy": dy,
                "label": eng.get("label", ""),
                "value": value,
            }
        )

    ring_polygons: list[str] = []
    for pct in (0.25, 0.5, 0.75, 1.0):
        ring_pts = []
        for i in range(n):
            rx, ry = _point(i * step, radius * pct)
            ring_pts.append(f"{rx:.1f},{ry:.1f}")
        ring_polygons.append(" ".join(ring_pts))

    return {
        "points": " ".join(data_points),
        "ring_polygons": ring_polygons,
        "axes": axes,
        "labels": labels,
        "center": center,
    }


def compute_engine_breakdown(
    *,
    aio_score: int | None,
    geo_score: int | None,
    findings: list[dict[str, Any]] | None = None,
    robots_text: str | None = None,
    competitors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Ritorna breakdown SoV stimato per max 5 engine."""
    aio = float(aio_score if aio_score is not None else 0)
    geo = float(geo_score if geo_score is not None else 0)
    findings = list(findings or [])
    robots_text = robots_text or ""
    competitors = list(competitors or [])

    base = aio * 0.62 + geo * 0.28
    pen = _severity_penalty(findings)
    has_llms = _finding_hits(findings, "llms.txt") == 0 or any(
        "llms" in str((f or {}).get("title", "")).lower()
        and str((f or {}).get("severity", "")).lower() == "ok"
        for f in findings
    )
    # Boost leggero se non ci sono warn/critical su llms; penalità se criticità llms
    llms_crit = any(
        "llms" in f"{(f or {}).get('title', '')} {(f or {}).get('detail', '')}".lower()
        and str((f or {}).get("severity", "")).lower() in {"critical", "warn"}
        for f in findings
    )
    schema_hit = _finding_hits(findings, "json-ld", "schema", "structured data")
    faq_hit = _finding_hits(findings, "faq")

    # Competitor pressure: media AIO rivali alza il "campo" e riduce SoV relativo
    rival_aios: list[float] = []
    for c in competitors:
        if c.get("error"):
            continue
        try:
            rival_aios.append(float(c.get("aio_score") or 0))
        except (TypeError, ValueError):
            continue
    rival_avg = sum(rival_aios) / len(rival_aios) if rival_aios else None
    field_pressure = 0.0
    if rival_avg is not None:
        field_pressure = max(0.0, (rival_avg - aio) * 0.35)

    engines_out: list[dict[str, Any]] = []
    raw_voice: list[float] = []

    for eng in ENGINES:
        score = base - pen - field_pressure
        bot = eng.get("bot")
        policy = _bot_policy(robots_text, bot) if bot else "default"

        if policy == "block":
            score -= 22
            access = "blocked"
        elif policy == "allow":
            score += 8
            access = "allow"
        elif policy == "missing":
            score -= 6
            access = "unknown"
        else:
            score += 2
            access = "default"

        # Engine-specific nudges from content signals
        if eng["id"] == "openai":
            score += 3 if has_llms and not llms_crit else 0
            score -= 5 if llms_crit else 0
        elif eng["id"] == "google":
            score += 4 if schema_hit == 0 else -min(6, schema_hit * 2)
            score += 2 if faq_hit == 0 else 0
        elif eng["id"] == "perplexity":
            score += 4 if has_llms and not llms_crit else -3
            score += geo * 0.04
        elif eng["id"] == "anthropic":
            score += geo * 0.05
            score -= 3 if llms_crit else 0
        elif eng["id"] == "bing":
            score += schema_hit == 0 and 2 or 0
            score += aio * 0.03

        # Soft variance so bars aren't identical
        score *= float(eng["weight"])
        propensity = _clamp(score)

        # Voice mass ≈ propensity × market weight (for stacked SoV)
        voice = max(0.5, propensity * float(eng["weight"]))
        raw_voice.append(voice)

        band = (
            "high"
            if propensity >= 70
            else "mid"
            if propensity >= 45
            else "low"
            if propensity >= 25
            else "crit"
        )
        engines_out.append(
            {
                "id": eng["id"],
                "label": eng["label"],
                "vendor": eng["vendor"],
                "accent": eng["accent"],
                "propensity": propensity,
                "band": band,
                "access": access,
                "bot": bot,
                "evidence": "proxy",
            }
        )

    total_voice = sum(raw_voice) or 1.0
    for i, eng in enumerate(engines_out):
        share = round(100.0 * raw_voice[i] / total_voice, 1)
        eng["share"] = share

    # Fix rounding drift on last share
    drift = round(100.0 - sum(e["share"] for e in engines_out), 1)
    if engines_out:
        engines_out[-1]["share"] = round(engines_out[-1]["share"] + drift, 1)

    # Brand vs field (proxy): your voice share in a competitive set
    if rival_avg is not None and rival_aios:
        # You + rivals + residual "other"
        you = max(1.0, aio)
        rivals_mass = sum(max(1.0, r) for r in rival_aios)
        other = max(8.0, (100 - aio) * 0.35)
        denom = you + rivals_mass + other
        brand_sov = round(100.0 * you / denom, 1)
        rivals_sov = round(100.0 * rivals_mass / denom, 1)
        other_sov = round(100.0 - brand_sov - rivals_sov, 1)
    else:
        # Solo brand: estimated share of answer slots vs "unclaimed"
        brand_sov = _clamp(aio * 0.55 + geo * 0.15)
        other_sov = round(100.0 - brand_sov, 1)
        rivals_sov = 0.0

    top = max(engines_out, key=lambda e: e["propensity"]) if engines_out else None

    return {
        "evidence": "proxy",
        "label": "Stimato (proxy)",
        "engines": engines_out,
        "columns": _column_geometry(engines_out),
        "radar": _radar_geometry(engines_out),  # legacy; UI prefers columns
        "composition": engines_out,  # same order for stacked bar
        "brand_sov": brand_sov,
        "rivals_sov": rivals_sov,
        "other_sov": other_sov,
        "has_competitors": bool(rival_aios),
        "top_engine": top["label"] if top else None,
        "measured": None,
        "note": (
            "Stima derivata da score AIO/GEO, policy robots osservata in probe e findings. "
            "Non è polling live su ChatGPT/Perplexity/Claude."
        ),
    }


def apply_measured_sov(
    breakdown: dict[str, Any],
    measured: dict[str, Any] | None,
) -> dict[str, Any]:
    """Sovrappone SoV measured (LLM probe) sul breakdown proxy.

    P0: never let empty/near-zero measured probes wipe a healthy proxy SoV.
    - ``mention_rate == 0`` keeps proxy propensity (annotates measured-zero).
    - If no engine has a positive measured rate, return proxy unchanged.
    - Weak brand_mention_rate does not replace a solid proxy brand_sov.
    """
    if not measured or not measured.get("available"):
        return breakdown

    measured_engines = {
        str(e.get("id")): e for e in (measured.get("engines") or []) if isinstance(e, dict)
    }
    positive_rates: list[float] = []
    for m in measured_engines.values():
        rate = m.get("mention_rate")
        if rate is None:
            continue
        try:
            rate_f = float(rate)
        except (TypeError, ValueError):
            continue
        if rate_f > 0:
            positive_rates.append(rate_f)

    # Full fallback: measured available but no positive mentions → keep proxy.
    if not positive_rates:
        out = dict(breakdown)
        out["measured"] = measured
        out["note"] = (
            (measured.get("note") or "").strip()
            or "Probe measured senza menzioni positive: mostriamo SoV stimato (proxy)."
        )
        if out.get("evidence") == "proxy":
            out["label"] = "Stimato (proxy) — measured senza hit"
        return out

    out = dict(breakdown)
    engines = [dict(e) for e in (out.get("engines") or [])]
    for eng in engines:
        m = measured_engines.get(str(eng.get("id")))
        if not m:
            continue
        rate = m.get("mention_rate")
        if rate is None:
            # Preserve unavailable/pending reason from measured probe
            if m.get("evidence") in {"unavailable", "pending"}:
                eng["evidence"] = m.get("evidence")
                if m.get("reason"):
                    eng["reason"] = m.get("reason")
            continue
        try:
            rate_f = float(rate)
        except (TypeError, ValueError):
            continue
        if rate_f <= 0:
            # Zero hit is observed, but do not erase proxy propensity/share.
            eng["evidence"] = "measured"
            eng["mention_rate"] = 0
            eng["measured_zero"] = True
            if m.get("samples") is not None:
                eng["samples"] = m.get("samples")
            continue
        eng["propensity"] = _clamp(rate_f)
        eng["evidence"] = "measured"
        eng["mention_rate"] = eng["propensity"]
        eng.pop("measured_zero", None)
        if m.get("samples") is not None:
            eng["samples"] = m.get("samples")
        if m.get("label"):
            eng["label"] = m.get("label")
        if m.get("vendor"):
            eng["vendor"] = m.get("vendor")
        eng["band"] = (
            "high"
            if eng["propensity"] >= 70
            else "mid"
            if eng["propensity"] >= 45
            else "low"
            if eng["propensity"] >= 25
            else "crit"
        )
    # Pending connectors are configuration placeholders, not observed engines.
    # Keep explicit unavailable engines (and their reason) visible to the UI.
    engines = [e for e in engines if e.get("evidence") != "pending"]
    # Ricalcola share se abbiamo almeno un measured positivo.
    if any(
        e.get("evidence") == "measured" and float(e.get("mention_rate") or 0) > 0
        for e in engines
    ):
        raw = [max(0.5, float(e.get("propensity") or 0) * 1.0) for e in engines]
        total = sum(raw) or 1.0
        for i, eng in enumerate(engines):
            eng["share"] = round(100.0 * raw[i] / total, 1)
        drift = round(100.0 - sum(e["share"] for e in engines), 1)
        if engines:
            engines[-1]["share"] = round(engines[-1]["share"] + drift, 1)

        proxy_brand = float(out.get("brand_sov") or 0)
        brand_rate = measured.get("brand_mention_rate")
        brand_f: float | None
        try:
            brand_f = float(brand_rate) if brand_rate is not None else None
        except (TypeError, ValueError):
            brand_f = None

        positive_n = sum(
            1
            for e in engines
            if e.get("evidence") == "measured" and float(e.get("mention_rate") or 0) > 0
        )
        # Weak measured brand must not collapse a healthy proxy SoV.
        weak_brand = (
            brand_f is None
            or brand_f <= 0
            or (
                brand_f < 5
                and positive_n < 2
                and proxy_brand >= 15
            )
        )
        if brand_f is not None and not weak_brand:
            out["brand_sov"] = _clamp(brand_f)
            out["other_sov"] = round(100.0 - out["brand_sov"], 1)
            out["rivals_sov"] = 0.0
            out["evidence"] = "mixed"
            out["label"] = "Misto (proxy + measured)"
        else:
            out["evidence"] = "mixed"
            out["label"] = "Misto — brand SoV da proxy"
            out["note"] = measured.get("note") or (
                "Probe measured con pochi hit: brand SoV resta sulla stima proxy; "
                "gli engine con menzioni positive restano evidenza measured."
            )
        if not out.get("note"):
            out["note"] = measured.get("note") or (
                "Engine con menzioni LLM: evidence measured. "
                "Altri engine restano proxy euristico."
            )
    out["engines"] = engines
    out["composition"] = engines
    out["columns"] = _column_geometry(engines)
    out["radar"] = _radar_geometry(engines)
    out["measured"] = measured
    top = max(engines, key=lambda e: e.get("propensity") or 0) if engines else None
    out["top_engine"] = top["label"] if top else out.get("top_engine")
    return out
