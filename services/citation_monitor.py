"""Multi-engine citation / measured SoV monitor.

OpenAI / Perplexity / Anthropic (Claude) = measured when the matching API key is set.
Other engines remain proxy placeholders with explicit evidence labels.

Keys are read at call-time (not only at import) so load_dotenv / systemd env stay in sync.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from services.prompt_bank import default_prompts

logger = logging.getLogger(__name__)


def _env(*names: str, default: str = "") -> str:
    for name in names:
        val = (os.getenv(name) or "").strip()
        if val:
            return val
    return default


def _openai_key() -> str:
    return _env("OPENAI_API_KEY")


def _openai_model() -> str:
    return _env("OPENAI_MODEL", default="gpt-4o-mini") or "gpt-4o-mini"


def _perplexity_key() -> str:
    return _env("PERPLEXITY_API_KEY")


def _perplexity_model() -> str:
    return _env("PERPLEXITY_MODEL", default="sonar") or "sonar"


def _anthropic_key() -> str:
    return _env("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")


def _anthropic_model() -> str:
    return (
        _env("ANTHROPIC_MODEL", "CLAUDE_MODEL", default="claude-haiku-4-5-20251001")
        or "claude-haiku-4-5-20251001"
    )


def _anthropic_version() -> str:
    return _env("ANTHROPIC_API_VERSION", default="2023-06-01") or "2023-06-01"


# Back-compat aliases (may be empty if read before load_dotenv in odd import orders).
OPENAI_API_KEY = _openai_key()
OPENAI_MODEL = _openai_model()
PERPLEXITY_API_KEY = _perplexity_key()
PERPLEXITY_MODEL = _perplexity_model()
ANTHROPIC_API_KEY = _anthropic_key()
ANTHROPIC_MODEL = _anthropic_model()
ANTHROPIC_API_VERSION = _anthropic_version()


def citation_monitor_available() -> bool:
    return bool(_openai_key() or _perplexity_key() or _anthropic_key())


def _normalize_needle(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _needles(brand: str, domain: str) -> set[str]:
    raw = {(brand or "").strip(), (domain or "").strip()}
    out: set[str] = set()
    for item in raw:
        if not item or len(item) < 3:
            continue
        out.add(item.lower())
        compact = _normalize_needle(item)
        if len(compact) >= 3:
            out.add(compact)
        if "." in item:
            apex = item.split(".")[0].lower()
            if len(apex) >= 3:
                out.add(apex)
                out.add(_normalize_needle(apex))
    return out


def _mentioned(text: str, needles: set[str]) -> bool:
    blob = text or ""
    lower = blob.lower()
    compact = _normalize_needle(blob)
    for n in needles:
        if not n:
            continue
        if n in lower or (len(n) >= 3 and n in compact):
            return True
    return False


def _probe_openai(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    api_key = _openai_key()
    model = _openai_model()
    if not api_key:
        return {"available": False, "reason": "OPENAI_API_KEY assente", "details": []}
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    client = OpenAI(api_key=api_key, timeout=45.0)
    hits = 0
    details: list[dict[str, Any]] = []
    for prompt in prompts:
        try:
            resp = client.chat.completions.create(
                model=model,
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
            if hasattr(resp, "usage") and resp.usage and usage_callback:
                usage_callback(
                    provider="openai",
                    model=model,
                    input_tokens=resp.usage.prompt_tokens,
                    output_tokens=resp.usage.completion_tokens,
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
    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        return {
            "available": False,
            "reason": "OpenAI probe fallito su tutti i prompt",
            "details": details,
        }
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": model,
    }


def _probe_perplexity(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    api_key = _perplexity_key()
    model = _perplexity_model()
    if not api_key:
        return {"available": False, "reason": "PERPLEXITY_API_KEY assente", "details": []}
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc), "details": []}

    hits = 0
    details: list[dict[str, Any]] = []
    system = "Be factual. Cite real brands only. Answer briefly."
    for prompt in prompts[:3]:
        try:
            res = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.2,
                    "max_tokens": 350,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"{system}\n\n{prompt}",
                        }
                    ],
                },
                timeout=45,
            )
            if not res.ok:
                err_body = (res.text or "")[:180]
                details.append(
                    {
                        "prompt": prompt,
                        "error": f"HTTP {res.status_code}: {err_body}",
                        "engine": "perplexity",
                    }
                )
                continue
            data = res.json()
            usage = data.get("usage") or {}
            if usage and usage_callback:
                usage_callback(
                    provider="perplexity",
                    model=model,
                    input_tokens=int(usage.get("prompt_tokens", 0)),
                    output_tokens=int(usage.get("completion_tokens", 0)),
                )
            text = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                or ""
            ).strip()
        except Exception as exc:
            logger.exception("perplexity citation probe failed")
            details.append(
                {"prompt": prompt, "error": str(exc)[:160], "engine": "perplexity"}
            )
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
    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        reason = "Perplexity probe fallito su tutti i prompt"
        if details and details[0].get("error"):
            reason = str(details[0]["error"])[:160]
        return {"available": False, "reason": reason, "details": details}
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": model,
    }


def _probe_anthropic(
    prompts: list[str],
    needles: set[str],
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    """Claude Messages API — SoV measured probe."""
    api_key = _anthropic_key()
    model = _anthropic_model()
    version = _anthropic_version()
    if not api_key:
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
    for prompt in prompts[:3]:
        try:
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": version,
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 350,
                    "temperature": 0.2,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=45,
            )
            if not res.ok:
                details.append(
                    {
                        "prompt": prompt,
                        "error": f"HTTP {res.status_code}: {(res.text or '')[:180]}",
                        "engine": "anthropic",
                    }
                )
                continue
            data = res.json()
            usage = data.get("usage") or {}
            if usage and usage_callback:
                usage_callback(
                    provider="anthropic",
                    model=model,
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                )
            parts = data.get("content") or []
            text_bits: list[str] = []
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_bits.append(str(part.get("text") or ""))
            text = "\n".join(text_bits).strip()
        except Exception as exc:
            logger.exception("anthropic citation probe failed")
            details.append(
                {"prompt": prompt, "error": str(exc)[:160], "engine": "anthropic"}
            )
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
    ok_details = [d for d in details if "error" not in d]
    if not ok_details:
        reason = "Anthropic probe fallito su tutti i prompt"
        if details and details[0].get("error"):
            reason = str(details[0]["error"])[:160]
        return {"available": False, "reason": reason, "details": details}
    total = max(1, len(ok_details))
    rate = round(100.0 * hits / total)
    return {
        "available": True,
        "mention_rate": rate,
        "hits": hits,
        "samples": total,
        "details": details,
        "evidence": "measured",
        "model": model,
    }


def _competitor_pressure(competitors: list[dict[str, Any]]) -> float:
    if not competitors:
        return 0.0
    scores = []
    for c in competitors:
        try:
            scores.append(
                float(c.get("aio_score") or 0) * 0.5 + float(c.get("geo_score") or 0) * 0.5
            )
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
    usage_callback: Any | None = None,
) -> dict[str, Any]:
    prompts = list(prompts or default_prompts(locale="it"))[:8]
    needles = _needles(brand, domain)
    findings: list[dict[str, str]] = []
    engines_out: list[dict[str, Any]] = []
    all_details: list[dict[str, Any]] = []

    openai = _probe_openai(prompts, needles, usage_callback=usage_callback)
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

    pplx = _probe_perplexity(prompts, needles, usage_callback=usage_callback)
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
                "model": pplx.get("model") or _perplexity_model(),
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

    anthropic = _probe_anthropic(prompts, needles, usage_callback=usage_callback)
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
                "model": anthropic.get("model") or _anthropic_model(),
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

    competitor_benchmark = []
    for c in (competitors or [])[:3]:
        competitor_benchmark.append(
            {
                "domain": c.get("domain") or c.get("url"),
                "aio_score": c.get("aio_score"),
                "geo_score": c.get("geo_score"),
                "rating": c.get("rating"),
                "note": (
                    "Score snapshot; SoV measured condiviso richiede stessi prompt "
                    "sul rivale (Plus)."
                ),
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


def run_measured_sov(
    *, brand: str, domain: str, engines: list[str] | None = None
) -> dict[str, Any]:
    return run_citation_monitor(
        brand=brand, domain=domain, prompts=None, competitors=None
    )
