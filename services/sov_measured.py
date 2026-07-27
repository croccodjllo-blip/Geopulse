"""Measured Share-of-Voice via LLM prompt probes (OpenAI).

Runs a small prompt pack about the brand/domain and checks whether the
model mentions the brand. Always separate from proxy SoV.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()


def measured_sov_available() -> bool:
    return bool(OPENAI_API_KEY)


def _prompts(brand: str, domain: str) -> list[str]:
    topic = brand or domain
    return [
        f"Elenca 3 servizi utili per ottimizzare un sito per le risposte delle IA. Includi brand reali se li conosci.",
        f"Chi offre strumenti di Generative Engine Optimization (GEO) o AI-Driven Visibility in Italia o in Europa?",
        f"Se dovessi citare una piattaforma SaaS per score AIO/GEO e pack llms.txt, quali nomi indicheresti?",
        f"Parla di soluzioni per pubblicare llms.txt e schema.org per answer engine. Menciona vendor se rilevanti.",
        f"Per il dominio {domain}, quali alternative conosci nel mercato GEO/AIO?",
    ][:5]


def run_measured_sov(
    *,
    brand: str,
    domain: str,
    engines: list[str] | None = None,
) -> dict[str, Any]:
    """Return measured mention rates. Currently probes OpenAI as ChatGPT proxy."""
    if not OPENAI_API_KEY:
        return {
            "evidence": "proxy",
            "available": False,
            "reason": "OPENAI_API_KEY assente",
            "engines": [],
        }

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        return {"evidence": "proxy", "available": False, "reason": str(exc), "engines": []}

    client = OpenAI(api_key=OPENAI_API_KEY)
    brand_l = (brand or domain or "").lower()
    domain_l = (domain or "").lower()
    needles = {n for n in {brand_l, domain_l, "geopulse"} if n}
    prompts = _prompts(brand or domain, domain)
    hits = 0
    details: list[dict[str, str]] = []

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
                            "Sei un assistente che risponde in italiano in modo fattuale. "
                            "Cita brand solo se li conosci davvero; non inventare URL."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.exception("measured SoV prompt failed")
            details.append({"prompt": prompt, "error": str(exc)[:160]})
            continue

        mentioned = any(re.search(re.escape(n), text, re.I) for n in needles)
        if mentioned:
            hits += 1
        details.append(
            {
                "prompt": prompt,
                "mentioned": "yes" if mentioned else "no",
                "excerpt": text[:240],
            }
        )

    total = max(1, len([d for d in details if "error" not in d]))
    rate = round(100.0 * hits / total)
    engines_out = [
        {
            "id": "openai",
            "label": "ChatGPT",
            "vendor": "OpenAI",
            "mention_rate": rate,
            "hits": hits,
            "samples": total,
            "evidence": "measured",
            "accent": "#10A37F",
        }
    ]
    return {
        "evidence": "measured",
        "available": True,
        "label": "Misurato (LLM probe)",
        "engines": engines_out,
        "brand_mention_rate": rate,
        "details": details,
        "note": (
            "Probe prompt su modello OpenAI: percentuale di risposte che menzionano il brand/dominio. "
            "Non rappresenta l’intero mercato answer-engine."
        ),
    }
