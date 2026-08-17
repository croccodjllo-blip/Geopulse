"""Map low-level crawl/network exceptions to actionable user messages."""

from __future__ import annotations

import re

import requests


def classify_analyze_error(exc: BaseException | str | None) -> dict[str, str]:
    """
    Return {code, title, message, hint} for dashboard / job failure UX.
    Never expose stack traces or internal host details beyond the URL host.
    """
    raw = "" if exc is None else (exc if isinstance(exc, str) else str(exc))
    text = (raw or "").strip()
    low = text.lower()

    def pack(code: str, title: str, message: str, hint: str) -> dict[str, str]:
        return {
            "code": code,
            "title": title,
            "message": message,
            "hint": hint,
            "detail": text[:280] if text else "",
        }

    if not text:
        return pack(
            "unknown",
            "Analisi non riuscita",
            "Si è verificato un errore durante l’analisi.",
            "Riprova tra poco. Se persiste, scrivi a info@centropic.ai con l’URL.",
        )

    if isinstance(exc, requests.Timeout) or "timed out" in low or "timeout" in low:
        return pack(
            "timeout",
            "Timeout di rete",
            "Il sito non ha risposto in tempo utile.",
            "Verifica che il dominio sia online e raggiungibile pubblicamente, poi riprova.",
        )

    if "name or service not known" in low or "nodename nor servname" in low or "getaddrinfo" in low:
        return pack(
            "dns",
            "Dominio non risolvibile",
            "Non riusciamo a risolvere il DNS di questo URL.",
            "Controlla typo nel dominio (es. https://tuosito.com) e che il DNS sia propagato.",
        )

    if "certificate" in low or "ssl" in low or "tls" in low:
        return pack(
            "ssl",
            "Problema certificato SSL",
            "La connessione HTTPS non è risultata affidabile.",
            "Controlla il certificato sul dominio e riprova con https:// corretto.",
        )

    if "robots" in low and ("disallow" in low or "blocked" in low):
        return pack(
            "robots_blocked",
            "Accesso limitato da robots.txt",
            "Il sito blocca i crawler su percorsi rilevanti per l’analisi.",
            "Consenti i bot di diagnosi o ripubblica robots.txt meno restrittivo, poi ri-analizza.",
        )

    if "non-html" in low or "content-type" in low:
        return pack(
            "non_html",
            "Risposta non HTML",
            "L’URL non restituisce una pagina HTML analizzabile.",
            "Usa la homepage pubblica del sito (non un PDF, JSON o asset statico).",
        )

    m = re.search(r"\bHTTP\s+(\d{3})\b", text, flags=re.I)
    if m:
        code = m.group(1)
        return pack(
            f"http_{code}",
            f"Risposta HTTP {code}",
            f"Il server ha risposto con status {code} sulla URL di partenza.",
            "Apri l’URL in browser in modalità anonima: deve essere pubblico e senza login.",
        )

    if "connection refused" in low or "connection reset" in low:
        return pack(
            "connection",
            "Connessione rifiutata",
            "Il server ha chiuso la connessione durante il crawl.",
            "Verifica firewall/WAF e che l’host accetti traffico HTTPS pubblico.",
        )

    if "redirect" in low and ("loop" in low or "too many" in low):
        return pack(
            "redirect_loop",
            "Troppi redirect",
            "L’URL entra in un loop di redirect.",
            "Correggi www/non-www e http→https, poi punta direttamente alla URL finale.",
        )

    if "ssrf" in low or "non consentito" in low or "private" in low:
        return pack(
            "unsafe_url",
            "URL non consentito",
            "L’URL non è analizzabile per policy di sicurezza.",
            "Usa solo URL pubblici https:// (niente localhost, IP privati o file://).",
        )

    if "addebito parziale" in low or "doppia fatturazione" in low:
        return pack(
            "billing_reclaim_partial",
            "Job interrotto dopo addebito parziale",
            "Il job è stato interrotto per un problema tecnico dopo un addebito parziale; "
            "non è stato rieseguito per evitare una doppia fatturazione.",
            "Il credito addebitato viene rimborsato automaticamente. Se non lo vedi in "
            "bacheca entro pochi minuti, scrivi a info@centropic.ai con l’ID del job.",
        )

    if isinstance(exc, requests.RequestException) or "request" in low:
        return pack(
            "unreachable",
            "Sito non raggiungibile",
            "Impossibile completare la richiesta HTTP verso il dominio.",
            "Verifica che l’URL sia pubblico e riprova. Se usi un CDN, controlla le regole geo/bot.",
        )

    return pack(
        "analyze_failed",
        "Analisi non riuscita",
        "L’analisi si è interrotta prima di produrre il report.",
        "Riprova. Se ripeti l’errore, contatta info@centropic.ai con l’URL analizzato.",
    )


def format_job_error(exc: BaseException | str | None) -> str:
    """Compact single-line string stored on AnalysisJob.error."""
    info = classify_analyze_error(exc)
    detail = info.get("detail") or ""
    base = f"{info['title']}: {info['message']}"
    if detail and detail.lower() not in base.lower():
        return f"{base} ({detail})"[:500]
    return base[:500]
