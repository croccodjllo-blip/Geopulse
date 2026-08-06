"""Citability audit — claim/stat/quote/date/author signals."""

from __future__ import annotations

import re
from typing import Any

STAT_RE = re.compile(
    r"\b\d{1,3}(?:[.,]\d+)?\s*%|\b\d{2,4}\s*(?:utenti|clienti|siti|pagine|analisi)\b",
    re.I,
)
QUOTE_RE = re.compile(r"[«\"].{12,180}[»\"]")
# Evita falsi positivi su disclaimers: "non ranking garantito", "non garantiamo", ecc.
# Bare "sempre" is too noisy on honest methodology copy ("sempre etichettati…").
# Keep absolute-claim stems that imply superiority / certainty.
CLAIM_RE = re.compile(
    r"(?<!\bnon\s)(?<!\bnon\suna\s)(?<!\bnessun\s)"
    r"\b(garantiamo|il migliore|n[°o]\s*1|100%\s*accurat|(?<!\bnon\s)ranking\s+garantito)\b",
    re.I,
)


def _count_risky_claims(text: str) -> int:
    """Conta claim assoluti escludendo negazioni tipiche da disclaimer onesto."""
    risky = 0
    for m in CLAIM_RE.finditer(text or ""):
        start = max(0, m.start() - 24)
        window = text[start : m.end()].lower()
        if re.search(r"\bnon\s+(?:è\s+|un\s+|una\s+)?(?:ranking\s+)?garant", window):
            continue
        if "non ranking garantito" in window or "non garant" in window:
            continue
        if "diagnostica, non" in window or "diagnostici, non" in window:
            continue
        risky += 1
    return risky
DATE_RE = re.compile(
    r"\b(?:20\d{2}|19\d{2})[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b"
    r"|\b(?:0?[1-9]|[12]\d|3[01])[-/.](?:0?[1-9]|1[0-2])[-/.](?:20\d{2}|19\d{2})\b"
)
SOURCE_HINT_RE = re.compile(
    r"\b(secondo|fonte|studio|ricerca|report|schema\.org|llmstxt)\b", re.I
)


def analyze_citability(
    *,
    scraped: dict[str, Any],
    pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    text = (scraped.get("snippet") or "")[:8000]
    dates = len(DATE_RE.findall(text))
    stats = len(STAT_RE.findall(text))
    quotes = len(QUOTE_RE.findall(text))
    risky = _count_risky_claims(text)
    sources = len(SOURCE_HINT_RE.findall(text))
    cite_links = int(scraped.get("citation_link_count") or 0)
    author = bool(scraped.get("has_author_signal"))

    # Aggregate light signals from crawl titles (dates in titles rare)
    page_words = sum(int(p.get("word_count") or 0) for p in (pages or [])[:20])

    score = 20
    score += min(20, dates * 8)
    score += min(15, stats * 5)
    score += min(10, quotes * 5)
    score += min(15, cite_links * 5)
    score += min(10, sources * 4)
    score += 10 if author else 0
    score -= min(20, risky * 8)
    score = max(0, min(100, score))

    if dates or cite_links or sources:
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Citability signals presenti",
                "detail": (
                    f"Date {dates} · stats {stats} · quote {quotes} · "
                    f"link fonte {cite_links} · author {'sì' if author else 'no'}."
                ),
                "evidence": "measured",
            }
        )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Citability audit debole",
                "detail": "Aggiungi date, fonti esterne, dati quotabili e byline/author.",
                "evidence": "estimated",
            }
        )

    if risky:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Claim assoluti rischiosi",
                "detail": (
                    f"{risky} formulazioni tipo 'garantito/migliore/100%'. "
                    "Preferisci claim verificabili con badge Stimato/Misurato."
                ),
                "evidence": "estimated",
            }
        )

    return {
        "score": score,
        "dates": dates,
        "stats": stats,
        "quotes": quotes,
        "risky_claims": risky,
        "source_hints": sources,
        "citation_links": cite_links,
        "has_author": author,
        "page_words_sampled": page_words,
        "findings": findings,
    }
