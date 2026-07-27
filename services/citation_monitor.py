"""Multi-engine citation / measured SoV monitor.

OpenAI / Perplexity / Anthropic (Claude) = measured when the matching API key is set.
Other engines remain proxy placeholders with explicit evidence labels.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from services.prompt_bank import default_prompts

logger = logging.getLogger(__name__)

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
PERPLEXITY_API_KEY = (os.getenv("PERPLEXITY_API_KEY") or "").strip()
PERPLEXITY_MODEL = (os.getenv("PERPLEXITY_MODEL") or "sonar").strip()
ANTHROPIC_API_KEY = (
    (os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY") or "").strip()
)
ANTHROPIC_MODEL = (
    os.getenv("ANTHROPIC_MODEL") or os.getenv("CLAUDE_MODEL") or "claude-haiku-4-5-20251001"
).strip()
ANTHROPIC_API_VERSION = (os.getenv("ANTHROPIC_API_VERSION") or "2023-06-01").strip()


def citation_monitor_available() -> bool:
    return bool(OPENAI_API_KEY or PERPLEXITY_API_KEY or ANTHROPIC_API_KEY)


def _needles(brand: str, domain: str) -> set[str]:
    return {n for n in {(brand or "").lower(), (domain or "").lower()} if n and len(n) > 2}


def _mentioned(text: str, needles: set[str]) -> bool:
    return any(re.search(re.escape(n), text, re.I) for n in needles)


def _probe_openai(prompts: list[str], needles: set[str]) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"available": False, "reason": "OPENAI_API_KEY assente", "details": []}
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    client = OpenAI(api_key=OPENAI_API_KEY)
    hits = 0
    details: list[dict[str, Any]] = []
    for prompt in prompts:
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.2,
                max_tokens=350,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Rispondi in modo fattuale. Cita brand solo se li conosci; "
                            "non inventare URL."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.exception("openai citation probe failed")
            details.append({"prompt": prompt, "error": str(exc)[:160]})
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {"prompt": prompt, "mentioned": ok, "excerpt": text[:280], "engine": "openai"}
        )
    total = max(1, len([d for d in details if "error" not in d]))
    rate = round(100.0 * hits / total) if details else 0
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
    }


def _probe_perplexity(prompts: list[str], needles: set[str]) -> dict[str, Any]:
    if not PERPLEXITY_API_KEY:
        return {"available": False, "reason": "PERPLEXITY_API_KEY assente", "details": []}
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    hits = 0
    details: list[dict[str, Any]] = []
    # Limit cost: max 3 prompts on Perplexity
    for prompt in prompts[:3]:
        try:
            res = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": PERPLEXITY_MODEL,
                    "temperature": 0.2,
                    "max_tokens": 350,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Be factual. Cite real brands only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=45,
            )
            res.raise_for_status()
            data = res.json()
            text = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                or ""
            ).strip()
        except Exception as exc:
            logger.exception("perplexity citation probe failed")
            details.append({"prompt": prompt, "error": str(exc)[:160]})
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {
                "prompt": prompt,
                "mentioned": ok,
                "excerpt": text[:280],
                "engine": "perplexity",
            }
        )
    total = max(1, len([d for d in details if "error" not in d]))
    rate = round(100.0 * hits / total) if details else 0
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
    }


def _probe_anthropic(prompts: list[str], needles: set[str]) -> dict[str, Any]:
    """Claude Messages API — SoV measured probe."""
    if not ANTHROPIC_API_KEY:
        return {"available": False, "reason": "ANTHROPIC_API_KEY assente", "details": []}
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    hits = 0
    details: list[dict[str, Any]] = []
    system = (
        "Rispondi in modo fattuale. Cita brand solo se li conosci realmente; "
        "non inventare URL o menzioni."
    )
    # Cost control: max 3 prompts
    for prompt in prompts[:3]:
        try:
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 350,
                    "temperature": 0.2,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=45,
            )
            res.raise_for_status()
            data = res.json()
            parts = data.get("content") or []
            text_bits: list[str] = []
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_bits.append(str(part.get("text") or ""))
            text = "\n".join(text_bits).strip()
        except Exception as exc:
            logger.exception("anthropic citation probe failed")
            details.append({"prompt": prompt, "error": str(exc)[:160]})
            continue
        ok = _mentioned(text, needles)
        if ok:
            hits += 1
        details.append(
            {
                "prompt": prompt,
                "mentioned": ok,
                "excerpt": text[:280],
                "engine": "anthropic",
            }
        )
    total = max(1, len([d for d in details if "error" not in d]))
    rate = round(100.0 * hits / total) if details else 0
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": ANTHROPIC_MODEL,
    }


def _competitor_pressure(competitors: list[dict[str, Any]]) -> float:
    if not competitors:
        return 0.0
    scores = []
    for c in competitors:
        try:
            scores.append(float(c.get("aio_score") or 0) * 0.5 + float(c.get("geo_score") or 0) * 0.5)
        except (TypeError, ValueError):
            continue
    if not scores:
        return 0.0
    return min(25.0, sum(scores) / len(scores) * 0.2)


def run_citation_monitor(
    *,
    brand: str,
    domain: str,
    prompts: list[str] | None = None,
    competitors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prompts = list(prompts or default_prompts(locale="it"))[:8]
    needles = _needles(brand, domain)
    findings: list[dict[str, str]] = []
    engines_out: list[dict[str, Any]] = []
    all_details: list[dict[str, Any]] = []

    openai = _probe_openai(prompts, needles)
    if openai.get("available"):
        engines_out.append(
            {
                "id": "openai",
                "label": "ChatGPT",
                "vendor": "OpenAI",
                "mention_rate": openai["mention_rate"],
                "hits": openai["hits"],
                "samples": openai["samples"],
                "evidence": "measured",
                "accent": "#10A37F",
            }
        )
        all_details.extend(openai.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "openai",
                "label": "ChatGPT",
                "vendor": "OpenAI",
                "mention_rate": None,
                "evidence": "unavailable",
                "reason": openai.get("reason"),
                "accent": "#10A37F",
            }
        )

    pplx = _probe_perplexity(prompts, needles)
    if pplx.get("available"):
        engines_out.append(
            {
                "id": "perplexity",
                "label": "Perplexity",
                "vendor": "Perplexity",
                "mention_rate": pplx["mention_rate"],
                "hits": pplx["hits"],
                "samples": pplx["samples"],
                "evidence": "measured",
                "accent": "#20B8CD",
            }
        )
        all_details.extend(pplx.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "perplexity",
                "label": "Perplexity",
                "vendor": "Perplexity",
                "mention_rate": None,
                "evidence": "unavailable",
                "reason": pplx.get("reason"),
                "accent": "#20B8CD",
            }
        )

    anthropic = _probe_anthropic(prompts, needles)
    if anthropic.get("available"):
        engines_out.append(
            {
                "id": "anthropic",
                "label": "Claude",
                "vendor": "Anthropic",
                "mention_rate": anthropic["mention_rate"],
                "hits": anthropic["hits"],
                "samples": anthropic["samples"],
                "evidence": "measured",
                "accent": "#D4A27F",
                "model": anthropic.get("model") or ANTHROPIC_MODEL,
            }
        )
        all_details.extend(anthropic.get("details") or [])
    else:
        engines_out.append(
            {
                "id": "anthropic",
                "label": "Claude",
                "vendor": "Anthropic",
                "mention_rate": None,
                "evidence": "unavailable",
                "reason": anthropic.get("reason"),
                "accent": "#D4A27F",
            }
        )

    # Placeholders for remaining engines (honest)
    for eng in (
        {"id": "google", "label": "AI Overview", "vendor": "Google", "accent": "#4285F4"},
        {"id": "bing", "label": "Copilot", "vendor": "Microsoft", "accent": "#7B83EB"},
    ):
        engines_out.append(
            {
                **eng,
                "mention_rate": None,
                "evidence": "pending",
                "reason": "Connector non ancora abilitato (API/browser probe).",
            }
        )

    measured_rates = [
        float(e["mention_rate"])
        for e in engines_out
        if e.get("evidence") == "measured" and e.get("mention_rate") is not None
    ]
    brand_rate = round(sum(measured_rates) / len(measured_rates)) if measured_rates else None
    pressure = _competitor_pressure(competitors or [])

    # Competitor SoV benchmark note
    competitor_benchmark = []
    for c in (competitors or [])[:3]:
        competitor_benchmark.append(
            {
                "domain": c.get("domain") or c.get("url"),
                "aio_score": c.get("aio_score"),
                "geo_score": c.get("geo_score"),
                "rating": c.get("rating"),
                "note": "Score snapshot; SoV measured condiviso richiede stessi prompt sul rivale (Plus).",
            }
        )

    if measured_rates:
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Citation monitor attivo",
                "detail": (
                    f"Probe measured su {len(measured_rates)} engine · "
                    f"brand mention rate medio {brand_rate}% · "
                    f"{len(prompts)} prompt."
                ),
                "evidence": "measured",
            }
        )
        if brand_rate is not None and brand_rate < 20:
            findings.append(
                {
                    "category": "geo",
                    "severity": "warn",
                    "title": "SoV measured basso",
                    "detail": (
                        "Poche menzioni brand nei prompt probe. Rafforza entity, "
                        "llms.txt e contenuti citabili; amplia il prompt bank."
                    ),
                    "evidence": "measured",
                }
            )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Citation monitor non configurato",
                "detail": (
                    "Imposta OPENAI_API_KEY, PERPLEXITY_API_KEY e/o ANTHROPIC_API_KEY "
                    "per SoV measured."
                ),
                "evidence": "estimated",
            }
        )

    available = bool(measured_rates)
    return {
        "evidence": "measured" if available else "proxy",
        "available": available,
        "label": "Misurato (multi-engine probe)" if available else "Non disponibile",
        "engines": engines_out,
        "brand_mention_rate": brand_rate,
        "details": all_details[:40],
        "prompts_used": prompts,
        "competitor_benchmark": competitor_benchmark,
        "competitor_pressure": round(pressure, 1),
        "findings": findings,
        "note": (
            "ChatGPT / Perplexity / Claude: mention rate da prompt pack. "
            "AI Overview / Copilot: pending connector. "
            "Non equivale a ranking garantito nelle risposte live."
        ),
    }


# Back-compat alias used by older imports
def run_measured_sov(*, brand: str, domain: str, engines: list[str] | None = None) -> dict[str, Any]:
    return run_citation_monitor(brand=brand, domain=domain, prompts=None, competitors=None)
