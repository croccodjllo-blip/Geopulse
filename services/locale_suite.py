"""Locale / hreflang AIO suite."""

from __future__ import annotations

from typing import Any


def analyze_locales(
    *,
    scraped: dict[str, Any],
    pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    lang = (scraped.get("lang") or "").lower()
    hreflang = list(scraped.get("hreflang") or [])
    page_langs = []
    for p in pages or []:
        # pages storage may not include lang; skip soft
        pl = (p.get("lang") or "").lower()
        if pl:
            page_langs.append(pl)

    locales = sorted({*(hreflang or []), *([lang] if lang else []), *page_langs})
    score = 30
    if lang:
        score += 25
    if hreflang:
        score += min(35, 10 + len(hreflang) * 5)
    if lang and hreflang and not any(lang[:2] in str(h).lower() for h in hreflang):
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "hreflang non allineato a lang",
                "detail": f'html lang="{lang}" ma alternate: {", ".join(hreflang[:6])}.',
                "evidence": "measured",
            }
        )
        score -= 10
    elif hreflang:
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Locale suite: hreflang presente",
                "detail": f"{len(hreflang)} alternate · lang={lang or 'n/d'}.",
                "evidence": "measured",
            }
        )
    elif lang:
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Lingua dichiarata (mono-locale)",
                "detail": f'lang="{lang}". Per mercati multipli aggiungi hreflang + pack localizzati.',
                "evidence": "measured",
            }
        )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Locale non dichiarata",
                "detail": "Imposta html lang e, se serve, hreflang per answer engine multi-lingua.",
                "evidence": "measured",
            }
        )

    return {
        "score": max(0, min(100, score)),
        "lang": lang,
        "hreflang": hreflang,
        "locales": locales,
        "findings": findings,
        "recommendation": (
            "Genera llms.txt / FAQ per ogni lingua target; le risposte IA sono language-specific."
        ),
    }
