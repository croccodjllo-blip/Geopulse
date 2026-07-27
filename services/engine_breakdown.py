"""Proxy Share-of-Voice per AI engine (stimato, non measured).

Deriva propensity e composizione SoV da AIO/GEO, policy bot e findings,
finché non esiste polling multi-LLM reale. Sempre etichettato evidence=proxy.
"""

from __future__ import annotations

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
        "label": "AI Overview",
        "vendor": "Google",
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
        "id": "bing",
        "label": "Copilot",
        "vendor": "Microsoft",
        "bot": None,
        "accent": "#7B83EB",
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
    """Sovrappone SoV measured (LLM probe) sul breakdown proxy, senza sostituire gli altri engine."""
    if not measured or not measured.get("available"):
        return breakdown
    out = dict(breakdown)
    engines = [dict(e) for e in (out.get("engines") or [])]
    measured_engines = {
        str(e.get("id")): e for e in (measured.get("engines") or []) if isinstance(e, dict)
    }
    for eng in engines:
        m = measured_engines.get(eng.get("id"))
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
        eng["propensity"] = _clamp(float(rate))
        eng["evidence"] = "measured"
        eng["mention_rate"] = eng["propensity"]
        eng["band"] = (
            "high"
            if eng["propensity"] >= 70
            else "mid"
            if eng["propensity"] >= 45
            else "low"
            if eng["propensity"] >= 25
            else "crit"
        )
    # Ricalcola share solo se almeno un engine è measured
    if any(e.get("evidence") == "measured" for e in engines):
        raw = [max(0.5, float(e.get("propensity") or 0) * 1.0) for e in engines]
        total = sum(raw) or 1.0
        for i, eng in enumerate(engines):
            eng["share"] = round(100.0 * raw[i] / total, 1)
        drift = round(100.0 - sum(e["share"] for e in engines), 1)
        if engines:
            engines[-1]["share"] = round(engines[-1]["share"] + drift, 1)
        brand_rate = measured.get("brand_mention_rate")
        if brand_rate is not None:
            out["brand_sov"] = _clamp(float(brand_rate))
            out["other_sov"] = round(100.0 - out["brand_sov"], 1)
            out["rivals_sov"] = 0.0
        out["evidence"] = "mixed"
        out["label"] = "Misto (proxy + measured)"
        out["note"] = measured.get("note") or (
            "ChatGPT: mention rate da probe LLM. Altri engine restano proxy euristico."
        )
    out["engines"] = engines
    out["composition"] = engines
    out["measured"] = measured
    top = max(engines, key=lambda e: e.get("propensity") or 0) if engines else None
    out["top_engine"] = top["label"] if top else out.get("top_engine")
    return out
