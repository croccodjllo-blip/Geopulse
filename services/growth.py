"""SaaS growth helpers: sample report, trial, referral, lifecycle email copy."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


REFERRAL_BONUS_CENTS = 200  # 20 GEO token
TRIAL_DAYS = 7
SAMPLE_DOMAIN = "example-brand.com"


def new_referral_code() -> str:
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10].lower()


def trial_ends_at(*, days: int = TRIAL_DAYS, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now + timedelta(days=max(1, int(days)))


def trial_is_active(user: Any, *, now: datetime | None = None) -> bool:
    ends = getattr(user, "trial_ends_at", None)
    if ends is None:
        return False
    now = now or datetime.now(timezone.utc)
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    return ends > now


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
            "llms.txt",
            "organization.jsonld.html",
            "meta-pack.html",
            "robots.txt",
            "fix-this-week.md",
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
            f"Passa a Plus (SoV measured + 100 token/mese): {pricing_url}",
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
    subject = "Centropic: token in esaurimento"
    body = (
        f"Ciao {name.split()[0] if name else 'ciao'},\n\n"
        f"Il tuo saldo è basso ({balance_tokens:g} token).\n"
        f"Ricarica: {topup_url}\n"
        f"Oppure passa a Plus (100 token/mese): {pricing_url}\n\n"
        "— Team Centropic\n"
    )
    return to_email, subject, body


def build_free_exhausted_email(
    *, to_email: str, name: str, pricing_url: str
) -> tuple[str, str, str]:
    subject = "Hai usato le analisi Free — continua con Plus"
    body = (
        f"Ciao {name.split()[0] if name else 'ciao'},\n\n"
        "Hai completato le analisi Free iniziali. Puoi ancora ri-analizzare lo stesso sito "
        "(consuma token). Per più brand, SoV measured e crawl più ampio:\n"
        f"{pricing_url}\n\n"
        "Prova Plus 7 giorni gratis dal dashboard se non l’hai già attivata.\n\n"
        "— Team Centropic\n"
    )
    return to_email, subject, body


def build_trial_started_email(
    *, to_email: str, name: str, ends_at: datetime, dashboard_url: str
) -> tuple[str, str, str]:
    subject = "Plus trial attivo — 7 giorni"
    ends = ends_at.astimezone(timezone.utc).strftime("%d/%m/%Y")
    body = (
        f"Ciao {name.split()[0] if name else 'ciao'},\n\n"
        f"Hai 7 giorni di Plus trial (fino al {ends}): SoV measured, crawl Plus, Edge completo.\n"
        f"Apri la dashboard: {dashboard_url}\n\n"
        "— Team Centropic\n"
    )
    return to_email, subject, body
