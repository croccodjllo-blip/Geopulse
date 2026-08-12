"""SaaS growth helpers: sample report, referral, lifecycle email copy."""

from __future__ import annotations

import secrets
from typing import Any


REFERRAL_BONUS_CENTS = 200  # 20 GEO token
SAMPLE_DOMAIN = "example-brand.com"


def new_referral_code() -> str:
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10].lower()


def sample_report_payload() -> dict[str, Any]:
    """Public anonymized demo report for /esempio-report (no auth)."""
    return {
        "domain": SAMPLE_DOMAIN,
        "url": f"https://{SAMPLE_DOMAIN}/",
        "aio_score": 62,
        "geo_score": 58,
        "rating": "CCC",
        "brand_sov": 18,
        "evidence": "proxy",
        "summary": (
            "Il brand è parzialmente leggibile dai modelli: mancano llms.txt, "
            "Organization JSON-LD completo e robots apre solo in parte i crawler IA."
        ),
        "critical_findings": [
            {
                "title": "llms.txt assente",
                "detail": "Nessun file root machine-readable: i modelli non hanno un’ancora di citazione chiara.",
                "fix": "Pubblica /llms.txt (o attiva Edge Signals).",
            },
            {
                "title": "robots.txt blocca GPTBot",
                "detail": "Policy corrente impedisce a crawler IA utili di indicizzare pagine chiave.",
                "fix": "Apri GPTBot / ClaudeBot / PerplexityBot sulle sezioni pubbliche.",
            },
            {
                "title": "JSON-LD Organization incompleto",
                "detail": "Mancano sameAs e contatto: entity ambigua per answer engine.",
                "fix": "Aggiungi Organization con sameAs (LinkedIn, Wikipedia, Crunchbase).",
            },
        ],
        "pack": [
            "centropic-fix.html",
        ],
        "next_steps": [
            "Attiva Edge Signals e scarica il CMS connector",
            "Chiudi i 3 finding critici",
            "Su Plus: SoV measured per verificare menzioni reali",
        ],
    }


def build_analysis_complete_email(
    *,
    to_email: str,
    name: str,
    domain: str,
    aio_score: int | None,
    geo_score: int | None,
    rating: str | None,
    findings: list[dict[str, Any]],
    dashboard_url: str,
    pricing_url: str,
    edge_hint: bool = True,
) -> tuple[str, str, str]:
    """Return (to, subject, body) for post-analysis lifecycle email."""
    crit = [
        f
        for f in (findings or [])
        if str((f or {}).get("severity") or "").lower() in {"critical", "warn"}
    ][:3]
    lines = [
        f"Ciao {name.split()[0] if name else 'ciao'},",
        "",
        f"Analisi Centropic pronta per {domain}.",
        f"Score: AIO {aio_score if aio_score is not None else '—'} · "
        f"GEO {geo_score if geo_score is not None else '—'} · Indice {rating or '—'}.",
        "",
        "3 azioni da fare ora:",
    ]
    if crit:
        for i, f in enumerate(crit, 1):
            title = (f.get("title") or "Finding").strip()
            detail = (f.get("detail") or f.get("fix") or "").strip()
            lines.append(f"{i}. {title}")
            if detail:
                lines.append(f"   {detail[:180]}")
    else:
        lines.append("1. Pubblica llms.txt in root (o attiva Edge Signals).")
        lines.append("2. Verifica Organization JSON-LD nel <head>.")
        lines.append("3. Controlla robots.txt per i crawler IA.")
    if edge_hint:
        lines.extend(
            [
                "",
                "Suggerimento: attiva Edge Signals in dashboard per servire "
                "llms.txt/robots aggiornati senza ricopiare file a ogni run.",
            ]
        )
    lines.extend(
        [
            "",
            f"Apri il report: {dashboard_url}",
            f"Passa a Plus (più domini, re-scan, SoV Misurato): {pricing_url}",
            "",
            "— Team Centropic",
            "https://centropic.ai",
        ]
    )
    subject = f"Report Centropic: {domain} · {rating or 'score'} pronto"
    return to_email, subject, "\n".join(lines)


def build_low_balance_email(
    *, to_email: str, name: str, balance_tokens: float, topup_url: str, pricing_url: str
) -> tuple[str, str, str]:
    subject = "Centropic: copertura in esaurimento"
    body = (
        f"Ciao {name.split()[0] if name else 'ciao'},\n\n"
        f"La copertura residua sta per esaurirsi (saldo ≈ {balance_tokens:g}).\n"
        f"Amplia la copertura: {topup_url}\n"
        f"Oppure passa a Plus (più domini, re-scan, SoV Misurato): {pricing_url}\n\n"
        "— Team Centropic\n"
    )
    return to_email, subject, body


def build_free_exhausted_email(
    *, to_email: str, name: str, pricing_url: str
) -> tuple[str, str, str]:
    subject = "Hai usato le analisi Free — continua con Plus"
    body = (
        f"Ciao {name.split()[0] if name else 'ciao'},\n\n"
        "Hai completato le analisi Free iniziali. Puoi ancora ri-analizzare lo stesso sito. "
        "Per più domini, re-scan schedulato, SoV Misurato e crawl più ampio:\n"
        f"{pricing_url}\n\n"
        "— Team Centropic\n"
    )
    return to_email, subject, body
