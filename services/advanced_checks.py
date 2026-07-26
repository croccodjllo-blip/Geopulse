"""Suite analisi avanzate AIO/GEO: schema, CWV proxy, indexabilità, E-E-A-T, pack."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from services.rating import compute_rating

RICH_SCHEMA_TYPES = {
    "Product",
    "Offer",
    "Review",
    "AggregateRating",
    "HowTo",
    "BreadcrumbList",
    "VideoObject",
    "Recipe",
    "Event",
    "SoftwareApplication",
}

YMYL_HINTS = re.compile(
    r"\b(salute|health|medical|medicina|farmac|finance|finanza|invest|assicur|"
    r"legal|avvocato|notar|crypto|bitcoin|prestito|mutuo|diagnos|terapia)\b",
    re.I,
)
AUTHOR_PAGE_RE = re.compile(r"/(author|autore|team|chi-siamo|about)(/|$)", re.I)
PUBDATE_META = (
    "article:published_time",
    "article:modified_time",
    "og:updated_time",
    "date",
    "publishdate",
    "last-modified",
)


def _push(
    findings: list[dict[str, str]],
    category: str,
    severity: str,
    title: str,
    detail: str,
) -> None:
    findings.append(
        {
            "category": category,
            "severity": severity,
            "title": title,
            "detail": detail,
        }
    )


def _host(url: str) -> str:
    host = urlparse(url or "").netloc.lower().split("@")[-1]
    return host[4:] if host.startswith("www.") else host


def analyze_rich_schema(jsonld_meta: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    types = set(jsonld_meta.get("types") or [])
    rich = sorted(types & RICH_SCHEMA_TYPES)
    if rich:
        aio += 6
        geo += 4
        _push(
            findings,
            "aio",
            "ok",
            "Schema rich results",
            "Tipi avanzati: " + ", ".join(rich[:8]),
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Schema avanzato assente",
            "Mancano Product/HowTo/Breadcrumb/Review/VideoObject utili ai rich result.",
        )

    if "BreadcrumbList" in types:
        geo += 2
    else:
        _push(
            findings,
            "geo",
            "warn",
            "BreadcrumbList assente",
            "Aggiungi BreadcrumbList JSON-LD per navigazione e citazioni.",
        )

    if "HowTo" in types:
        aio += 2
    if "Product" in types or "Offer" in types:
        aio += 2
        geo += 1
    if "Review" in types or "AggregateRating" in types:
        aio += 2
    if "VideoObject" in types:
        geo += 1

    return {"aio": aio, "geo": geo, "findings": findings, "rich_types": rich}


def analyze_ai_txt_quality(probes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    ai = probes.get("ai") or {}
    text = (ai.get("snippet") or "").strip()
    if not ai.get("ok") or not text:
        _push(
            findings,
            "aio",
            "warn",
            "ai.txt assente o vuoto",
            "Pubblica /ai.txt con policy per agenti e link a llms.txt.",
        )
        return {"aio": aio, "geo": geo, "findings": findings, "quality": "missing"}

    score = 0
    lower = text.lower()
    if "llms.txt" in lower or "/llms" in lower:
        score += 1
    if re.search(r"allow|disallow|prefer|contact|policy", lower):
        score += 1
    if len(text) >= 120:
        score += 1
    if re.search(r"https?://", text):
        score += 1

    if score >= 3:
        aio += 4
        geo += 2
        quality = "good"
        _push(
            findings,
            "aio",
            "ok",
            "ai.txt di buona qualità",
            f"Segnali policy/link rilevati ({score}/4).",
        )
    elif score >= 2:
        aio += 2
        quality = "ok"
        _push(
            findings,
            "aio",
            "warn",
            "ai.txt migliorabile",
            "Aggiungi policy esplicite e link a llms.txt / contatti.",
        )
    else:
        quality = "poor"
        _push(
            findings,
            "aio",
            "warn",
            "ai.txt povero",
            "Il file esiste ma non guida gli agenti AI in modo utile.",
        )
    return {"aio": aio, "geo": geo, "findings": findings, "quality": quality}


def analyze_content_freshness(
    scraped: dict[str, Any], pages: list[dict[str, Any]]
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    seed_dates = int(scraped.get("date_hits") or 0)
    meta_dates = scraped.get("date_meta") or []
    pages_with_dates = sum(
        1
        for p in pages
        if int((p.get("scraped") or p).get("date_hits") or 0) > 0
        or (p.get("scraped") or p).get("date_meta")
    )
    total = max(len(pages), 1)

    if meta_dates or seed_dates >= 2:
        aio += 3
        geo += 2
        _push(
            findings,
            "aio",
            "ok",
            "Freshness contenuti",
            "Date di pubblicazione/aggiornamento rilevate sulla seed o nel body.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Freshness debole",
            "Poche date visibili: aggiungi date articolo e lastmod nelle pagine chiave.",
        )

    if total > 1 and pages_with_dates / total < 0.25:
        _push(
            findings,
            "crawl",
            "warn",
            "Poche pagine datate",
            f"Solo {pages_with_dates}/{total} pagine con segnali data nel campione.",
        )
    elif total > 1 and pages_with_dates / total >= 0.4:
        aio += 2

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "pages_with_dates": pages_with_dates,
    }


def analyze_near_duplicates(pages: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    fingerprints: dict[str, list[str]] = defaultdict(list)
    for p in pages:
        sc = p.get("scraped") or p
        snippet = (sc.get("snippet") or sc.get("title") or "")[:400].lower()
        words = re.findall(r"[a-zà-ü0-9]{4,}", snippet)
        if len(words) < 12:
            continue
        key = hashlib.md5(" ".join(sorted(words[:40])).encode()).hexdigest()[:12]
        url = p.get("url") or sc.get("final_url") or ""
        if url:
            fingerprints[key].append(url)

    clusters = [urls for urls in fingerprints.values() if len(urls) >= 2]
    near_n = sum(len(c) for c in clusters)
    if clusters:
        sample = ", ".join(clusters[0][:2])
        _push(
            findings,
            "crawl",
            "warn" if near_n < 6 else "critical",
            "Possibili near-duplicate",
            f"{len(clusters)} cluster sospetti (~{near_n} URL). Esempio: {sample}",
        )
        aio -= 2
        geo -= 1
    elif len(pages) >= 3:
        aio += 1
        _push(
            findings,
            "crawl",
            "ok",
            "Nessun near-duplicate evidente",
            "Fingerprint contenuti distinti nel campione crawl.",
        )

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "clusters": len(clusters),
        "near_duplicate_urls": near_n,
    }


def build_brand_knowledge_graph(
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    entity = scraped.get("entity") or {}
    jsonld = scraped.get("jsonld") or {}
    brand = (
        entity.get("brand_name")
        or (scraped.get("domain") or "").replace("www.", "")
        or "Brand"
    )
    offerings: list[str] = []
    for h in scraped.get("headings") or []:
        if h and h not in offerings:
            offerings.append(h)
    faq_n = int(jsonld.get("faq_questions") or 0)
    same_as = list(entity.get("same_as") or [])
    pages_urls = [p.get("url") for p in pages if p.get("url")][:30]
    graph = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand,
        "url": scraped.get("final_url") or scraped.get("requested_url"),
        "description": scraped.get("description") or "",
        "telephone": entity.get("telephone") or (scraped.get("phones") or [None])[0],
        "email": entity.get("email") or (scraped.get("emails") or [None])[0],
        "address": entity.get("address") or None,
        "sameAs": same_as,
        "knowsAbout": offerings[:12],
        "hasPart": [{"@type": "WebPage", "url": u} for u in pages_urls[:12] if u],
        "potentialAction": {
            "@type": "ReadAction",
            "target": (scraped.get("final_url") or "") + "/llms.txt",
        },
        "additionalProperty": [
            {
                "@type": "PropertyValue",
                "name": "llms_txt",
                "value": "present" if (probes.get("llms") or {}).get("ok") else "missing",
            },
            {
                "@type": "PropertyValue",
                "name": "faq_questions",
                "value": faq_n,
            },
        ],
    }
    # drop nulls
    graph = {k: v for k, v in graph.items() if v not in (None, "", [], {})}
    completeness = sum(
        1
        for k in ("name", "url", "description", "telephone", "email", "sameAs", "knowsAbout")
        if graph.get(k)
    )
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    if completeness >= 5:
        aio += 4
        geo += 2
        _push(
            findings,
            "aio",
            "ok",
            "Knowledge graph brand",
            f"Entità {brand} con {completeness}/7 campi chiave ricostruibili.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Knowledge graph incompleto",
            f"Solo {completeness}/7 campi brand: arricchisci Organization + sameAs + FAQ.",
        )
    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "graph": graph,
        "completeness": completeness,
    }


def analyze_cwv_proxy(scraped: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Proxy Core Web Vitals da TTFB/HTML/script/immagini (senza Lighthouse)."""
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    samples = [scraped] + [(p.get("scraped") or {}) for p in pages if p.get("scraped")]
    if not samples:
        samples = [scraped]
    ms_vals = [int(s.get("response_ms") or 0) for s in samples if s.get("response_ms")]
    html_vals = [float(s.get("html_kb") or 0) for s in samples if s.get("html_kb")]
    blocking = [int(s.get("blocking_scripts") or 0) for s in samples]
    img_total = sum(int(s.get("img_count") or 0) for s in samples)
    img_dims = sum(int(s.get("img_with_dims") or 0) for s in samples)

    avg_ms = sum(ms_vals) / len(ms_vals) if ms_vals else 0
    avg_html = sum(html_vals) / len(html_vals) if html_vals else 0
    avg_block = sum(blocking) / len(blocking) if blocking else 0
    cls_proxy = (img_dims / img_total) if img_total else 1.0

    lcp_proxy = "good" if avg_ms < 1200 and avg_html < 400 else (
        "needs_improvement" if avg_ms < 2500 else "poor"
    )
    inp_proxy = "good" if avg_block <= 2 else ("needs_improvement" if avg_block <= 5 else "poor")
    cls_label = "good" if cls_proxy >= 0.7 else ("needs_improvement" if cls_proxy >= 0.4 else "poor")

    if lcp_proxy == "good":
        geo += 3
    elif lcp_proxy == "poor":
        geo -= 2
        _push(
            findings,
            "technical",
            "critical" if avg_ms > 3000 else "warn",
            "CWV proxy: LCP a rischio",
            f"TTFB medio ~{avg_ms:.0f}ms, HTML ~{avg_html:.0f}KB (proxy senza Lighthouse).",
        )
    else:
        _push(
            findings,
            "technical",
            "warn",
            "CWV proxy: LCP migliorabile",
            f"TTFB medio ~{avg_ms:.0f}ms · HTML ~{avg_html:.0f}KB.",
        )

    if inp_proxy == "poor":
        _push(
            findings,
            "technical",
            "warn",
            "CWV proxy: INP/script",
            f"Media {avg_block:.1f} script sync bloccanti nel campione.",
        )
    elif inp_proxy == "good":
        geo += 1

    if cls_label == "poor" and img_total:
        _push(
            findings,
            "technical",
            "warn",
            "CWV proxy: CLS immagini",
            f"Solo {img_dims}/{img_total} immagini con width/height.",
        )
    elif cls_label == "good" and img_total:
        geo += 1
        _push(
            findings,
            "technical",
            "ok",
            "CWV proxy accettabile",
            f"LCP={lcp_proxy}, INP={inp_proxy}, CLS={cls_label} (stima GeoPulse).",
        )

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "proxy": {
            "lcp": lcp_proxy,
            "inp": inp_proxy,
            "cls": cls_label,
            "avg_ttfb_ms": round(avg_ms),
            "avg_html_kb": round(avg_html, 1),
            "avg_blocking_scripts": round(avg_block, 1),
        },
    }


def analyze_indexability(
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    robots_txt = (probes.get("robots") or {}).get("snippet") or ""
    x_robots = (scraped.get("headers") or {}).get("x-robots-tag") or ""
    meta_robots = scraped.get("robots") or ""

    disallow_paths = re.findall(r"(?im)^\s*Disallow:\s*(\S+)", robots_txt)
    broad = [d for d in disallow_paths if d in {"/", "/*"}]
    if broad:
        geo -= 4
        _push(
            findings,
            "technical",
            "critical",
            "robots.txt blocca tutto",
            f"Disallow ampio: {', '.join(broad[:3])}.",
        )
    elif disallow_paths:
        geo += 1
        _push(
            findings,
            "technical",
            "ok",
            "robots.txt con path policy",
            f"{len(disallow_paths)} regole Disallow rilevate.",
        )

    if re.search(r"noindex", x_robots, re.I):
        aio -= 8
        geo -= 8
        _push(
            findings,
            "technical",
            "critical",
            "X-Robots-Tag noindex",
            "Header HTTP blocca l’indicizzazione.",
        )

    sitemap_urls = list((probes.get("sitemap") or {}).get("urls") or [])
    lastmod_hits = len(
        re.findall(r"<lastmod>", (probes.get("sitemap") or {}).get("snippet") or "", re.I)
    )
    if sitemap_urls and lastmod_hits == 0:
        _push(
            findings,
            "geo",
            "warn",
            "Sitemap senza lastmod",
            "Aggiungi <lastmod> per segnalare freshness ai crawler.",
        )
    elif lastmod_hits:
        geo += 2

    noindex_pages = sum(
        1
        for p in pages
        if "noindex" in (p.get("issues") or [])
        or re.search(
            r"noindex",
            str((p.get("scraped") or {}).get("robots") or ""),
            re.I,
        )
    )
    if noindex_pages:
        _push(
            findings,
            "crawl",
            "warn" if noindex_pages < 3 else "critical",
            "Pagine noindex nel crawl",
            f"{noindex_pages} URL con noindex nel campione.",
        )

    if meta_robots and not re.search(r"noindex", meta_robots, re.I):
        geo += 1

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "disallow_count": len(disallow_paths),
        "sitemap_lastmod": lastmod_hits,
    }


def analyze_broken_and_orphans(
    pages: list[dict[str, Any]],
    *,
    seed_url: str,
    check_limit: int = 16,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    crawled = {
        (p.get("url") or (p.get("scraped") or {}).get("final_url") or "").rstrip("/")
        for p in pages
    }
    crawled.discard("")
    candidates: list[str] = []
    inbound: Counter[str] = Counter()
    for p in pages:
        sc = p.get("scraped") or {}
        for href in sc.get("internal_hrefs") or []:
            clean = href.rstrip("/")
            inbound[clean] += 1
            if clean not in crawled and clean not in candidates:
                candidates.append(href)

    broken: list[str] = []
    checked = 0
    session = requests.Session()
    session.headers["User-Agent"] = "GeoPulse/1.0 (+https://geopulse.it; link-check)"
    for href in candidates[:check_limit]:
        checked += 1
        try:
            resp = session.head(href, timeout=4, allow_redirects=True)
            code = resp.status_code
            if code >= 400 or code == 405:
                resp = session.get(href, timeout=5, allow_redirects=True, stream=True)
                code = resp.status_code
                resp.close()
            if code >= 400:
                broken.append(f"{href} ({code})")
        except Exception:
            broken.append(f"{href} (errore)")

    if broken:
        geo -= 2
        _push(
            findings,
            "technical",
            "warn" if len(broken) < 3 else "critical",
            "Link interni rotti",
            f"{len(broken)}/{checked} campionati falliti. Es: {broken[0][:90]}",
        )
    elif checked:
        geo += 2
        _push(
            findings,
            "technical",
            "ok",
            "Link interni campione ok",
            f"{checked} URL interni non crawati verificati senza errori HTTP.",
        )

    orphans = [
        p.get("url")
        for p in pages
        if p.get("url")
        and inbound[(p.get("url") or "").rstrip("/")] == 0
        and _host(p.get("url") or "") == _host(seed_url)
        and (p.get("url") or "").rstrip("/") != (seed_url or "").rstrip("/")
    ]
    if orphans and len(pages) >= 4:
        _push(
            findings,
            "crawl",
            "warn",
            "Pagine orphan nel campione",
            f"{len(orphans)} URL senza inbound interno. Es: {orphans[0][:80]}",
        )
        geo -= 1

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "broken": broken[:12],
        "checked": checked,
        "orphan_count": len(orphans),
    }


def analyze_hreflang_complete(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    pairs = scraped.get("hreflang_pairs") or []
    langs = scraped.get("hreflang") or []
    page_lang = (scraped.get("lang") or "").split("-")[0].lower()
    codes = {
        str(p.get("lang") or "").lower()
        for p in pairs
        if isinstance(p, dict) and p.get("lang")
    } or {str(x).lower() for x in langs}

    if not codes:
        _push(
            findings,
            "geo",
            "warn",
            "hreflang assente",
            "Nessun link alternate hreflang: ok solo se sito mono-lingua.",
        )
        return {"aio": aio, "geo": geo, "findings": findings}

    has_x_default = "x-default" in codes
    if has_x_default:
        geo += 2
    else:
        _push(
            findings,
            "geo",
            "warn",
            "hreflang senza x-default",
            "Aggiungi hreflang=\"x-default\" per il fallback internazionale.",
        )

    if page_lang and page_lang not in codes and f"{page_lang}" not in {
        c.split("-")[0] for c in codes
    }:
        _push(
            findings,
            "geo",
            "warn",
            "hreflang non allineato a lang",
            f'html lang="{scraped.get("lang")}" non compare negli alternate.',
        )
    else:
        geo += 2
        _push(
            findings,
            "geo",
            "ok",
            "hreflang strutturato",
            f"{len(codes)} lingue/alternate rilevati"
            + (" · x-default ok" if has_x_default else "")
            + ".",
        )

    # reciprocity heuristic: at least 2 pairs with href
    hrefs = [p.get("href") for p in pairs if isinstance(p, dict) and p.get("href")]
    if len(hrefs) >= 2:
        geo += 1
    return {"aio": aio, "geo": geo, "findings": findings, "langs": sorted(codes)}


def analyze_security_headers(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    headers = {k.lower(): v for k, v in (scraped.get("headers") or {}).items()}
    hsts = headers.get("strict-transport-security")
    csp = headers.get("content-security-policy")
    xfo = headers.get("x-frame-options")
    final = scraped.get("final_url") or ""

    if final.startswith("https://"):
        geo += 1
    if hsts:
        geo += 2
        _push(findings, "technical", "ok", "HSTS attivo", hsts[:80])
    else:
        _push(
            findings,
            "technical",
            "warn",
            "HSTS assente",
            "Imposta Strict-Transport-Security su HTTPS.",
        )
    if csp:
        geo += 1
        _push(findings, "technical", "ok", "CSP presente", "Content-Security-Policy rilevata.")
    else:
        _push(
            findings,
            "technical",
            "warn",
            "CSP assente",
            "Una Content-Security-Policy riduce rischio XSS e mix content.",
        )
    if xfo:
        geo += 0.5
    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_mobile_rendering(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    viewport = scraped.get("viewport") or ""
    word_count = int(scraped.get("word_count") or 0)
    blocking = int(scraped.get("blocking_scripts") or 0)
    html_kb = float(scraped.get("html_kb") or 0)

    if viewport and "width" in viewport.lower():
        geo += 2
        _push(findings, "technical", "ok", "Viewport mobile", viewport[:90])
    else:
        _push(
            findings,
            "technical",
            "critical",
            "Viewport assente",
            "Manca meta viewport: rischio layout non mobile-friendly.",
        )

    # SPA shell heuristic
    if word_count < 80 and (blocking >= 3 or html_kb > 200):
        aio -= 3
        geo -= 2
        _push(
            findings,
            "aio",
            "warn",
            "Possibile shell SPA",
            "Poco testo HTML e molti script: i crawler AI possono vedere contenuti vuoti.",
        )
    elif word_count >= 180:
        aio += 1
        _push(
            findings,
            "aio",
            "ok",
            "Contenuto SSR/HTML utile",
            f"{word_count} parole nel HTML iniziale: buono per AIO.",
        )

    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_eeat_ymyl(
    scraped: dict[str, Any], pages: list[dict[str, Any]]
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    text_blob = " ".join(
        [
            scraped.get("title") or "",
            scraped.get("description") or "",
            scraped.get("snippet") or "",
        ]
    )
    ymyl = bool(YMYL_HINTS.search(text_blob))
    author_pages = [
        p.get("url")
        for p in pages
        if p.get("url") and AUTHOR_PAGE_RE.search(p.get("url") or "")
    ]
    has_author = bool(scraped.get("has_author_signal"))
    has_about = bool(scraped.get("has_about_link"))
    has_person = "Person" in set((scraped.get("jsonld") or {}).get("types") or [])

    if author_pages or has_person:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Pagine author / Person",
            (author_pages[0][:80] if author_pages else "Schema Person rilevato."),
        )
    elif has_author:
        aio += 1
        _push(
            findings,
            "aio",
            "warn",
            "Author segnale debole",
            "Meta/byline presente ma manca pagina author dedicata o Person schema.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "E-E-A-T author assente",
            "Aggiungi autore, bio e link a pagina credenziali.",
        )

    if ymyl:
        _push(
            findings,
            "aio",
            "warn" if (has_author or has_about) else "critical",
            "Contesto YMYL",
            "Topic sensibili rilevati: servi prove, author expertise e contatti chiari.",
        )
        if not (has_author and has_about):
            aio -= 3
        else:
            aio += 1
            _push(
                findings,
                "aio",
                "ok",
                "YMYL con segnali trust",
                "About/author presenti: rafforza con credenziali e fonti.",
            )

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "ymyl": ymyl,
        "author_pages": author_pages[:5],
    }


def analyze_nap_consistency(pages: list[dict[str, Any]], scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    phones: Counter[str] = Counter()
    emails: Counter[str] = Counter()
    for src in [scraped] + [(p.get("scraped") or {}) for p in pages if p.get("scraped")]:
        for ph in src.get("phones") or []:
            norm = re.sub(r"\D", "", ph)[-10:]
            if len(norm) >= 8:
                phones[norm] += 1
        for em in src.get("emails") or []:
            emails[em.lower()] += 1
    entity = scraped.get("entity") or {}
    if entity.get("telephone"):
        phones[re.sub(r"\D", "", entity["telephone"])[-10:]] += 2
    if entity.get("email"):
        emails[entity["email"].lower()] += 2

    phone_variants = len(phones)
    email_variants = len(emails)
    if phone_variants > 2:
        _push(
            findings,
            "geo",
            "warn",
            "NAP telefono inconsistente",
            f"{phone_variants} varianti telefono nel sito/schema (allinea a GBP).",
        )
        geo -= 1
    elif phone_variants == 1:
        geo += 2
        _push(
            findings,
            "geo",
            "ok",
            "NAP telefono coerente",
            "Un solo telefono dominante su pagine/schema (proxy vs Google Business).",
        )
    if email_variants > 2:
        _push(
            findings,
            "geo",
            "warn",
            "NAP email inconsistente",
            f"{email_variants} email diverse: unifica il contatto ufficiale.",
        )
    elif email_variants == 1:
        geo += 1

    if not phones and not emails:
        _push(
            findings,
            "geo",
            "warn",
            "NAP assente",
            "Nessun telefono/email chiaro: utile per LocalBusiness e directory.",
        )

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "phone_variants": phone_variants,
        "email_variants": email_variants,
    }


def analyze_answer_engine_readiness(
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Readiness proxy (non misura citazioni live senza API esterne)."""
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    score = 0
    checks = []
    if (probes.get("llms") or {}).get("ok"):
        score += 2
        checks.append("llms.txt")
    if (scraped.get("jsonld") or {}).get("has_organization"):
        score += 2
        checks.append("Organization")
    if (scraped.get("jsonld") or {}).get("has_faq_page"):
        score += 1
        checks.append("FAQ")
    if scraped.get("citation_link_count", 0) >= 2:
        score += 1
        checks.append("citazioni outbound")
    if scraped.get("has_author_signal"):
        score += 1
        checks.append("author")
    bots = (signals or {}).get("bot_policies") or {}
    if any(str(v).lower() in {"allow", "allowed", "implicit_allow"} for v in bots.values()):
        score += 1
        checks.append("bot allow")

    label = "alta" if score >= 6 else ("media" if score >= 3 else "bassa")
    if score >= 6:
        aio += 4
        geo += 3
        _push(
            findings,
            "aio",
            "ok",
            "Readiness answer engine alta",
            "Segnali: " + ", ".join(checks) + ". (proxy GeoPulse, non citazioni live)",
        )
    elif score >= 3:
        aio += 1
        _push(
            findings,
            "aio",
            "warn",
            "Readiness answer engine media",
            "Presenti: "
            + (", ".join(checks) if checks else "pochi segnali")
            + ". Rafforza llms.txt, schema e prove citabili.",
        )
    else:
        _push(
            findings,
            "aio",
            "critical",
            "Readiness answer engine bassa",
            "Mancano llms.txt/schema/FAQ/author: scarsa probabilità di citazione AI.",
        )
    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "readiness": label,
        "score": score,
        "checks": checks,
    }


def build_competitor_benchmark(
    own: dict[str, Any], competitors: list[dict[str, Any]]
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    if not competitors:
        return {"aio": aio, "geo": geo, "findings": findings, "rows": []}

    own_aio = int(own.get("aio_score") or 0)
    own_geo = int(own.get("geo_score") or 0)
    rows = []
    gaps = []
    for c in competitors:
        if c.get("error"):
            rows.append({**c, "gap_aio": None, "gap_geo": None})
            continue
        gap_aio = own_aio - int(c.get("aio_score") or 0)
        gap_geo = own_geo - int(c.get("geo_score") or 0)
        rows.append({**c, "gap_aio": gap_aio, "gap_geo": gap_geo})
        if gap_aio < -5 or gap_geo < -5:
            gaps.append(c.get("domain") or c.get("url") or "competitor")

    if gaps:
        _push(
            findings,
            "aio",
            "warn",
            "Gap vs competitor",
            "Dietro su: " + ", ".join(gaps[:3]) + ". Chiudi schema/llms/critical prima.",
        )
    else:
        valid = [r for r in rows if r.get("gap_aio") is not None]
        if valid:
            aio += 2
            geo += 1
            _push(
                findings,
                "aio",
                "ok",
                "Benchmark competitor solido",
                "Score in linea o sopra i rivali analizzati.",
            )

    md = [
        "# Competitor benchmark — GeoPulse",
        "",
        f"Tu: AIO {own_aio} · GEO {own_geo}",
        "",
        "| Dominio | AIO | GEO | Rating | Critical | Δ AIO | Δ GEO |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for r in rows:
        if r.get("error"):
            md.append(f"| {r.get('url')} | — | — | err | — | — | — |")
            continue
        md.append(
            f"| {r.get('domain') or r.get('url')} | {r.get('aio_score')} | "
            f"{r.get('geo_score')} | {r.get('rating')} | {r.get('critical')} | "
            f"{r.get('gap_aio'):+d} | {r.get('gap_geo'):+d} |"
        )
    md.append("")
    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "rows": rows,
        "markdown": "\n".join(md),
    }


def analyze_pack_regression(
    *,
    probes: dict[str, dict[str, Any]],
    scraped: dict[str, Any],
    previous: Any | None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if previous is None:
        return {"aio": 0.0, "geo": 0.0, "findings": findings}

    prev_findings = []
    try:
        prev_findings = list(previous.findings or [])
    except Exception:
        prev_findings = []

    def had(title_sub: str) -> bool:
        return any(title_sub in str(f.get("title") or "") for f in prev_findings)

    has_org = bool((scraped.get("jsonld") or {}).get("has_organization"))
    if had("Organization/LocalBusiness") and not has_org:
        _push(
            findings,
            "diff",
            "critical",
            "Alert: schema Organization sparito",
            "Era presente nella run precedente.",
        )
    noindex_now = bool(re.search(r"noindex", scraped.get("robots") or "", re.I))
    if noindex_now and not had("noindex attivo"):
        _push(
            findings,
            "diff",
            "critical",
            "Alert: noindex nuovo",
            "Compare noindex non segnalato nella run precedente.",
        )
    faq_now = bool((scraped.get("jsonld") or {}).get("has_faq_page"))
    if had("FAQ schema") and not faq_now:
        _push(
            findings,
            "diff",
            "warn",
            "Alert: FAQ schema sparito",
            "FAQPage non più rilevata rispetto alla run precedente.",
        )
    robots_ok = bool((probes.get("robots") or {}).get("ok"))
    if had("robots.txt raggiungibile") and not robots_ok:
        _push(
            findings,
            "diff",
            "critical",
            "Alert: robots.txt sparito",
            "robots.txt non raggiungibile dopo essere stato ok.",
        )
    return {"aio": 0.0, "geo": 0.0, "findings": findings}


def build_page_checklist(pages: list[dict[str, Any]], *, limit: int = 40) -> str:
    from services.analyzer import PAGE_ISSUE_DETAILS, prioritize_crawl_pages

    ranked = prioritize_crawl_pages(list(pages))
    lines = [
        "# Checklist per pagina — GeoPulse",
        "",
        "Priorità sulle URL critiche/warn del crawl.",
        "",
    ]
    n = 0
    for p in ranked:
        if p.get("severity") not in {"critical", "warn"} and not p.get("issues"):
            continue
        n += 1
        if n > limit:
            break
        url = p.get("url") or ""
        sev = p.get("severity") or "warn"
        lines.append(f"## {n}. [{sev}] {url}")
        title = p.get("title") or ""
        if title:
            lines.append(f"- Title: {title}")
        lines.append(
            f"- Score: AIO {p.get('aio_score')} · GEO {p.get('geo_score')}"
        )
        issues = p.get("issues") or []
        problems = p.get("problems") or []
        if problems:
            for pr in problems:
                lines.append(f"- [ ] {pr}")
        elif issues:
            for code in issues:
                label = PAGE_ISSUE_DETAILS.get(code) or PAGE_ISSUE_DETAILS.get(
                    str(code), str(code)
                )
                lines.append(f"- [ ] {label}")
        else:
            lines.append("- [ ] Rivedi contenuti e schema")
        lines.append("")
    if n == 0:
        lines.append("_Nessuna pagina critica nel campione._\n")
    return "\n".join(lines)


def build_html_patches(scraped: dict[str, Any], findings: list[dict[str, Any]]) -> str:
    brand = (scraped.get("domain") or "example.com").replace("www.", "")
    url = scraped.get("final_url") or scraped.get("requested_url") or f"https://{brand}"
    title = scraped.get("title") or brand
    description = scraped.get("description") or f"{brand} — docs and services."
    if len(description) > 160:
        description = description[:157].rstrip() + "..."
    lang = scraped.get("lang") or "it"
    crit = [
        f
        for f in findings
        if str(f.get("severity")).lower() in {"critical", "warn"}
    ][:12]
    patches = [
        "<!-- GeoPulse HTML patches (top critical) -->",
        f"<!-- Target: {url} -->",
        "",
    ]
    titles = {str(f.get("title") or "") for f in crit}
    if any("Title" in t for t in titles) or len(title) < 10:
        patches.append(f"<title>{title if len(title) >= 10 else brand + ' — Official site'}</title>")
    if any("description" in t.lower() for t in titles) or len(description) < 50:
        patches.append(f'<meta name="description" content="{description}">')
    if any("Canonical" in t for t in titles) or not scraped.get("canonical"):
        patches.append(f'<link rel="canonical" href="{url}">')
    if any("Open Graph" in t or "og:" in t.lower() for t in titles) or not scraped.get(
        "og_title"
    ):
        patches.extend(
            [
                f'<meta property="og:title" content="{title}">',
                f'<meta property="og:description" content="{description}">',
                f'<meta property="og:url" content="{url}">',
                '<meta property="og:type" content="website">',
            ]
        )
    if any("lang" in t.lower() for t in titles) or not scraped.get("lang"):
        patches.append(f'<!-- set <html lang="{lang}"> -->')
    if any("Viewport" in t for t in titles) or not scraped.get("viewport"):
        patches.append(
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
        )
    if any("Organization" in t or "JSON-LD" in t or "Manca JSON" in t for t in titles):
        org = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": brand,
            "url": url,
            "description": description,
        }
        patches.append(
            '<script type="application/ld+json">\n'
            + json.dumps(org, ensure_ascii=False, indent=2)
            + "\n</script>"
        )
    if any("H1" in t for t in titles) or not scraped.get("has_h1"):
        patches.append(f"<h1>{title}</h1>")
    if len(patches) <= 3:
        patches.append("<!-- Nessuna patch automatica urgente: vedi fix-this-week.md -->")
    patches.append("")
    return "\n".join(patches)


def build_executive_report_html(
    *,
    domain: str,
    url: str,
    aio: Any,
    geo: Any,
    findings: list[dict[str, Any]],
    rating: dict[str, Any],
    competitors: list[dict[str, Any]] | None = None,
    cwv: dict[str, Any] | None = None,
    readiness: str = "",
) -> str:
    crit = [f for f in findings if str(f.get("severity")).lower() == "critical"]
    warn = [f for f in findings if str(f.get("severity")).lower() == "warn"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cwv = cwv or {}
    rows = ""
    for f in (crit + warn)[:15]:
        rows += (
            f"<tr><td>{f.get('severity')}</td><td>{f.get('title')}</td>"
            f"<td>{f.get('detail')}</td></tr>"
        )
    comp_rows = ""
    for c in competitors or []:
        if c.get("error"):
            continue
        comp_rows += (
            f"<tr><td>{c.get('domain')}</td><td>{c.get('aio_score')}</td>"
            f"<td>{c.get('geo_score')}</td><td>{c.get('rating')}</td>"
            f"<td>{c.get('gap_aio', '—')}</td><td>{c.get('gap_geo', '—')}</td></tr>"
        )
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>GeoPulse report — {domain}</title>
<style>
body{{font-family:Georgia,serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#111}}
h1,h2{{font-family:system-ui,sans-serif}}
.meta{{color:#555;font-size:0.95rem}}
.score{{display:flex;gap:1rem;flex-wrap:wrap;margin:1.2rem 0}}
.score div{{border:1px solid #ddd;padding:0.8rem 1rem;min-width:6rem}}
table{{border-collapse:collapse;width:100%;font-size:0.92rem}}
td,th{{border:1px solid #ddd;padding:0.4rem 0.5rem;text-align:left;vertical-align:top}}
@media print{{body{{margin:0}}}}
</style>
</head>
<body>
<p class="meta">GeoPulse executive report · {now}</p>
<h1>{domain}</h1>
<p><a href="{url}">{url}</a></p>
<div class="score">
  <div><strong>Rating</strong><br>{rating.get('code')} ({rating.get('score')}/100)</div>
  <div><strong>AIO</strong><br>{aio}</div>
  <div><strong>GEO</strong><br>{geo}</div>
  <div><strong>Answer readiness</strong><br>{readiness or '—'}</div>
  <div><strong>CWV proxy</strong><br>LCP {cwv.get('lcp','—')} · INP {cwv.get('inp','—')} · CLS {cwv.get('cls','—')}</div>
</div>
<h2>Priorità ({len(crit)} critical · {len(warn)} warn)</h2>
<table><thead><tr><th>Sev</th><th>Finding</th><th>Dettaglio</th></tr></thead>
<tbody>{rows or '<tr><td colspan="3">Nessuna criticità</td></tr>'}</tbody></table>
{('<h2>Competitor</h2><table><thead><tr><th>Dominio</th><th>AIO</th><th>GEO</th><th>Rating</th><th>ΔAIO</th><th>ΔGEO</th></tr></thead><tbody>' + comp_rows + '</tbody></table>') if comp_rows else ''}
<p class="meta">Generato da GeoPulse · geopulse.it · stampa → PDF</p>
</body></html>
"""


def build_executive_pdf_bytes(html_title: str, lines: list[str]) -> bytes:
    """PDF testo minimo senza dipendenze esterne."""

    def esc(text: str) -> str:
        return (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("\r", "")
        )

    content_lines = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
    content_lines.append(f"({esc(html_title[:90])}) Tj")
    content_lines.append("T*")
    content_lines.append("/F1 9 Tf")
    y_lines = 0
    for raw in lines[:90]:
        line = raw[:95]
        content_lines.append(f"({esc(line)}) Tj")
        content_lines.append("T*")
        y_lines += 1
        if y_lines > 60:
            break
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objs: list[bytes] = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(
        b"4 0 obj<< /Length "
        + str(len(stream)).encode()
        + b" >>stream\n"
        + stream
        + b"\nendstream endobj\n"
    )
    objs.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def run_advanced_suite(
    *,
    url: str,
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    page_reports: list[dict[str, Any]],
    competitors: list[dict[str, Any]] | None = None,
    previous: Any | None = None,
    base_signals: dict[str, Any] | None = None,
    aio_score: int | None = None,
    geo_score: int | None = None,
    findings_so_far: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Esegue tutta la suite avanzata e produce findings + artifact + signals."""
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    pages = page_reports or []

    blocks = [
        analyze_rich_schema(scraped.get("jsonld") or {}),
        analyze_ai_txt_quality(probes),
        analyze_content_freshness(scraped, pages),
        analyze_near_duplicates(pages),
        analyze_cwv_proxy(scraped, pages),
        analyze_indexability(scraped, probes, pages),
        analyze_broken_and_orphans(pages, seed_url=url),
        analyze_hreflang_complete(scraped),
        analyze_security_headers(scraped),
        analyze_mobile_rendering(scraped),
        analyze_eeat_ymyl(scraped, pages),
        analyze_nap_consistency(pages, scraped),
    ]
    kg = build_brand_knowledge_graph(scraped, probes, pages)
    blocks.append(kg)
    readiness = analyze_answer_engine_readiness(scraped, probes, base_signals)
    blocks.append(readiness)
    regression = analyze_pack_regression(
        probes=probes, scraped=scraped, previous=previous
    )
    blocks.append(regression)

    cwv_proxy = {}
    for block in blocks:
        aio += float(block.get("aio") or 0)
        geo += float(block.get("geo") or 0)
        findings.extend(block.get("findings") or [])
        if block.get("proxy"):
            cwv_proxy = block["proxy"]

    own_scores = {
        "aio_score": aio_score,
        "geo_score": geo_score,
    }
    bench = build_competitor_benchmark(own_scores, competitors or [])
    aio += float(bench.get("aio") or 0)
    geo += float(bench.get("geo") or 0)
    findings.extend(bench.get("findings") or [])

    all_findings = list(findings_so_far or []) + findings
    rating = compute_rating(aio_score, geo_score, all_findings)
    page_checklist = build_page_checklist(pages)
    html_patches = build_html_patches(scraped, all_findings)
    kg_json = json.dumps(kg.get("graph") or {}, ensure_ascii=False, indent=2) + "\n"
    exec_html = build_executive_report_html(
        domain=scraped.get("domain") or _host(url),
        url=scraped.get("final_url") or url,
        aio=aio_score,
        geo=geo_score,
        findings=all_findings,
        rating=rating,
        competitors=bench.get("rows") or competitors,
        cwv=cwv_proxy,
        readiness=str(readiness.get("readiness") or ""),
    )
    pdf_lines = [
        f"Domain: {scraped.get('domain')}",
        f"AIO: {aio_score}  GEO: {geo_score}  Rating: {rating.get('code')}",
        f"Answer readiness: {readiness.get('readiness')}",
        f"CWV proxy: {cwv_proxy}",
        "",
        "Top findings:",
    ]
    for f in all_findings:
        if str(f.get("severity")).lower() in {"critical", "warn"}:
            pdf_lines.append(f"- [{f.get('severity')}] {f.get('title')}: {f.get('detail')}")
    exec_pdf = build_executive_pdf_bytes(
        f"GeoPulse — {scraped.get('domain')}", pdf_lines
    )

    artifacts = {
        "page-checklist.md": page_checklist,
        "html-patches.html": html_patches,
        "brand-knowledge-graph.json": kg_json,
        "competitor-benchmark.md": bench.get("markdown")
        or "# Competitor benchmark\n\n_Nessun competitor._\n",
        "executive-report.html": exec_html,
    }

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "artifacts": artifacts,
        "executive_pdf": exec_pdf,
        "signals": {
            "rich_schema": (blocks[0] or {}).get("rich_types")
            if blocks
            else [],
            "ai_txt_quality": next(
                (b.get("quality") for b in blocks if "quality" in b), None
            ),
            "cwv_proxy": cwv_proxy,
            "answer_readiness": readiness.get("readiness"),
            "answer_readiness_score": readiness.get("score"),
            "kg_completeness": kg.get("completeness"),
            "broken_links": next(
                (b.get("broken") for b in blocks if "broken" in b), []
            ),
            "near_duplicate_clusters": next(
                (b.get("clusters") for b in blocks if "clusters" in b), 0
            ),
            "ymyl": next((b.get("ymyl") for b in blocks if "ymyl" in b), False),
            "competitor_benchmark": bench.get("rows") or [],
        },
    }
