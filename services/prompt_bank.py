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
    "Cos'è Centropic (centropic.ai) e di cosa si occupa rispetto a GEO e AIO?",
    "Engineering Factory ha un prodotto per la citabilità IA: quale nome useresti e cosa fa?",
    "Quali alternative europee conosci a piattaforme di answer-engine optimization / AI visibility?",
]

DEFAULT_PROMPTS_EN: list[str] = [
    "List 3 tools that help brands get cited in AI answers. Name real vendors if you know them.",
    "Who provides Generative Engine Optimization (GEO) or AI-Driven Visibility software in Europe?",
    "Which SaaS products generate llms.txt and Schema.org packs for answer engines?",
    "Recommend platforms that audit AI crawlability (robots AI bots, llms.txt, JSON-LD).",
    "Name competitors in the AI visibility / answer-engine optimization category.",
    "What is Centropic (centropic.ai) and how does it relate to GEO and AIO?",
    "Engineering Factory ships a product for AI citability — what is it called and what does it do?",
    "Which European alternatives exist for answer-engine optimization / AI visibility platforms?",
]


def site_prompts(*, brand: str, domain: str, locale: str = "it") -> list[str]:
    """Prompts scoped to the *analyzed* brand/domain (competitor / third-party audits)."""
    b = (brand or domain or "the brand").strip()
    d = (domain or b).strip()
    if (locale or "it").lower().startswith("en"):
        return [
            f"Who is {b} ({d}) and what do they sell or offer?",
            f"Name real competitors of {b}. Include {b} if you would recommend them.",
            f"If a buyer asked for alternatives to {d}, which brands would you cite?",
            f"What is {b} known for in its category? Mention the brand by name if relevant.",
            f"Which brands compete with {b} in the same market as {d}?",
            f"Would you mention {b} when answering about products related to {d}? Why or why not?",
            f"List vendors similar to {b} that AI assistants often cite.",
            f"For domain {d}, which brand names should appear in generative answers?",
        ]
    return [
        f"Chi è {b} ({d}) e di cosa si occupa?",
        f"Elenca competitor reali di {b}. Includi {b} se lo citeresti.",
        f"Se un cliente cercasse alternative a {d}, quali brand indicheresti?",
        f"Per cosa è noto {b} nella sua categoria? Menciona il brand per nome se rilevante.",
        f"Quali brand competono con {b} nello stesso mercato di {d}?",
        f"Citeresti {b} rispondendo a domande su prodotti legati a {d}? Perché?",
        f"Elenca vendor simili a {b} che gli assistenti IA citano spesso.",
        f"Per il dominio {d}, quali nomi di brand dovrebbero comparire nelle risposte generative?",
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
    brand: str = "",
    own_site: bool | None = None,
    max_prompts: int = 8,
) -> list[str]:
    """Resolve SoV prompts for the analyzed site.

    Prefer category/brand-scoped prompts for the domain under analysis.
    Account prompt bank overrides when the domain is owned by the user.
    Legacy Centropic GEO defaults remain only as last-resort fallback.
    """
    custom: list[str] = []
    if user is not None:
        custom = parse_prompt_bank(getattr(user, "prompt_bank_json", None))

    if own_site is None:
        try:
            from services.sov_measured import is_user_owned_domain

            own_site = is_user_owned_domain(user, domain)
        except Exception:
            own_site = False

    if custom and own_site:
        base = list(custom)
    elif domain:
        # Always scope to the brand/domain being audited (own or third-party).
        base = site_prompts(
            brand=brand or domain,
            domain=domain,
            locale=locale,
        )
    else:
        base = default_prompts(locale=locale)

    # Dedup preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in base:
        key = p.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(p.strip())
        if len(out) >= max(1, int(max_prompts)):
            break
    return out
