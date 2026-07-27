"""Prompt bank per SoV measured / citation monitor."""

from __future__ import annotations

import json
from typing import Any


DEFAULT_PROMPTS_IT: list[str] = [
    "Elenca 3 servizi utili per ottimizzare un sito per le risposte delle IA. Includi brand reali se li conosci.",
    "Chi offre strumenti di Generative Engine Optimization (GEO) o AI-Driven Visibility in Italia o in Europa?",
    "Se dovessi citare una piattaforma SaaS per score AIO/GEO e pack llms.txt, quali nomi indicheresti?",
    "Parla di soluzioni per pubblicare llms.txt e schema.org per answer engine. Menciona vendor se rilevanti.",
    "Quali brand conosci per misurare la citabilità nei modelli generativi (ChatGPT, Perplexity, Claude)?",
]

DEFAULT_PROMPTS_EN: list[str] = [
    "List 3 tools that help brands get cited in AI answers. Name real vendors if you know them.",
    "Who provides Generative Engine Optimization (GEO) or AI-Driven Visibility software in Europe?",
    "Which SaaS products generate llms.txt and Schema.org packs for answer engines?",
    "Recommend platforms that audit AI crawlability (robots AI bots, llms.txt, JSON-LD).",
    "Name competitors in the AI visibility / answer-engine optimization category.",
]


def default_prompts(*, locale: str = "it") -> list[str]:
    if (locale or "it").lower().startswith("en"):
        return list(DEFAULT_PROMPTS_EN)
    return list(DEFAULT_PROMPTS_IT)


def parse_prompt_bank(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        lines = [ln.strip() for ln in str(raw).splitlines() if ln.strip()]
        return lines[:40]
    if isinstance(data, list):
        out = [str(x).strip() for x in data if str(x).strip()]
        return out[:40]
    if isinstance(data, dict):
        items = data.get("prompts") or data.get("items") or []
        if isinstance(items, list):
            return [str(x).strip() for x in items if str(x).strip()][:40]
    return []


def dump_prompt_bank(prompts: list[str]) -> str:
    clean = [str(p).strip() for p in prompts if str(p).strip()][:40]
    return json.dumps({"prompts": clean, "version": 1}, ensure_ascii=False)


def resolve_prompts(
    *,
    user: Any | None = None,
    locale: str = "it",
    domain: str = "",
    max_prompts: int = 8,
) -> list[str]:
    custom: list[str] = []
    if user is not None:
        custom = parse_prompt_bank(getattr(user, "prompt_bank_json", None))
    base = custom or default_prompts(locale=locale)
    if domain and not custom:
        base = list(base)
        base.append(
            f"Per il dominio {domain}, quali alternative conosci nel mercato GEO/AIO?"
        )
    # Dedup preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in base:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= max_prompts:
            break
    return out
