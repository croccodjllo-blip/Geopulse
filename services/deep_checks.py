"""Check AIO/GEO estesi: content, GEO, tecnico, coverage, checklist."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from services.rating import compute_rating


def _host_key(netloc: str) -> str:
    host = (netloc or "").lower().split("@")[-1]
    if host.startswith("www."):
        host = host[4:]
    return host


def same_host(url_a: str, url_b: str) -> bool:
    return _host_key(urlparse(url_a).netloc) == _host_key(urlparse(url_b).netloc)


PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?)?\d{3,4}[\s\-.]?\d{3,4}"
)
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
DATE_RE = re.compile(
    r"\b(?:20\d{2}|19\d{2})[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b"
    r"|\b(?:0?[1-9]|[12]\d|3[01])[-/.](?:0?[1-9]|1[0-2])[-/.](?:20\d{2}|19\d{2})\b"
    r"|\b(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
    r"|january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{1,2},?\s+20\d{2}\b",
    re.I,
)
ADDRESS_RE = re.compile(
    r"\b(?:via|viale|piazza|corso|strada|via\.|v\.)\s+[A-ZÀ-Üa-zà-ü0-9'\.\s]{4,40}\d{1,4}\b",
    re.I,
)
ABOUT_HREF_RE = re.compile(r"(about|chi[-_]?siamo|company|team|mission)", re.I)
CONTACT_HREF_RE = re.compile(r"(contact|contatti|support)", re.I)
AUTHOR_RE = re.compile(r"(author|autore|by\s+[A-Z][a-z]+)", re.I)


def enrich_jsonld_entities(jsonld_meta: dict[str, Any]) -> dict[str, Any]:
    """Estrae campi brand da nodi Organization/LocalBusiness/WebSite."""
    name = ""
    url = ""
    telephone = ""
    email = ""
    address = ""
    same_as: list[str] = []
    has_article = False
    org_complete = 0

    # blocks aren't stored in meta currently — use flags + types
    # Caller should pass organization_nodes if available
    for node in jsonld_meta.get("org_nodes") or []:
        if not name and isinstance(node.get("name"), str):
            name = node["name"].strip()
        if not url and isinstance(node.get("url"), str):
            url = node["url"].strip()
        if not telephone and isinstance(node.get("telephone"), str):
            telephone = node["telephone"].strip()
        if not email and isinstance(node.get("email"), str):
            email = node["email"].strip()
        addr = node.get("address")
        if not address and isinstance(addr, dict):
            parts = [
                addr.get("streetAddress"),
                addr.get("addressLocality"),
                addr.get("postalCode"),
                addr.get("addressCountry"),
            ]
            address = ", ".join(str(p) for p in parts if p)
        elif not address and isinstance(addr, str):
            address = addr.strip()
        for item in node.get("sameAs") or []:
            if isinstance(item, str):
                same_as.append(item)

    if name:
        org_complete += 1
    if url:
        org_complete += 1
    if telephone or email:
        org_complete += 1
    if address:
        org_complete += 1
    if same_as:
        org_complete += 1

    types = set(jsonld_meta.get("types") or [])
    has_article = bool(types & {"Article", "NewsArticle", "BlogPosting"})

    return {
        "brand_name": name,
        "brand_url": url,
        "telephone": telephone,
        "email": email,
        "address": address,
        "same_as": same_as[:8],
        "org_completeness": org_complete,
        "has_article_schema": has_article,
    }


def analyze_heading_hierarchy(page: dict[str, Any]) -> dict[str, Any]:
    h1_count = int(page.get("h1_count") or (1 if page.get("has_h1") else 0))
    h2_count = int(page.get("h2_count") or 0)
    findings: list[dict[str, str]] = []
    aio = 0.0
    if h1_count == 1:
        aio += 3
    elif h1_count == 0:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "H1 assente",
                "detail": "Serve un H1 unico che dichiari il topic della pagina.",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "H1 multipli",
                "detail": f"Trovati {h1_count} H1: preferisci un solo H1 per pagina.",
            }
        )
    if h2_count >= 2:
        aio += 2
    elif h1_count == 1 and h2_count == 0:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Nessun H2",
                "detail": "Aggiungi H2 per strutturare sezioni leggibili da AI crawler.",
            }
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_content_quality(page: dict[str, Any]) -> dict[str, Any]:
    words = int(page.get("word_count") or 0)
    link_count = int(page.get("internal_link_count") or 0) + int(
        page.get("external_link_count") or 0
    )
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0

    if words >= 400:
        aio += 4
        geo += 2
    elif words >= 180:
        aio += 2
    elif words > 0:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Contenuto sottile",
                "detail": f"Solo ~{words} parole: rischio thin content per AIO/GEO.",
            }
        )

    # densità: troppi link rispetto al testo = boilerplate/nav heavy
    if words > 80 and link_count > 0:
        density = link_count / max(words / 100, 1)
        if density > 18:
            findings.append(
                {
                    "category": "aio",
                    "severity": "warn",
                    "title": "Boilerplate/link pesanti",
                    "detail": "Molti link rispetto al testo utile: riduci nav ripetitiva nella pagina.",
                }
            )
        elif density < 8 and words >= 250:
            aio += 2

    dates = int(page.get("date_hits") or 0)
    cite_links = int(page.get("citation_link_count") or 0)
    if dates >= 1 or cite_links >= 1:
        aio += 2
        geo += 2
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Segnali citabili",
                "detail": f"Date rilevate: {dates}, link esterni/fonte: {cite_links}.",
            }
        )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Poche prove verificabili",
                "detail": "Aggiungi date, fonti o link a riferimenti per claim più citabili.",
            }
        )

    if page.get("has_about_link") or page.get("has_contact_link"):
        geo += 2
        aio += 1
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Manca About/Contatti in evidenza",
                "detail": "Link a chi siamo / contatti rafforzano entità brand e E-E-A-T.",
            }
        )

    if page.get("has_author_signal"):
        aio += 2
        geo += 1
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Segnale author/E-E-A-T",
                "detail": "Rilevati meta/rel author o byline.",
            }
        )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Author/E-E-A-T debole",
                "detail": "Aggiungi autore, bio o Organization completa per fiducia.",
            }
        )

    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_brand_nap(page: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    phones = page.get("phones") or []
    emails = page.get("emails") or []
    addresses = page.get("addresses") or []

    completeness = int(entity.get("org_completeness") or 0)
    if completeness >= 3:
        aio += 4
        geo += 4
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "Entità brand chiara",
                "detail": f"JSON-LD brand con {completeness}/5 campi utili (name/url/contatti/indirizzo/sameAs).",
            }
        )
    elif entity.get("brand_name") or phones or emails:
        aio += 1
        geo += 1
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Entità brand incompleta",
                "detail": "Completa Organization con name, url, telephone/email e sameAs.",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Brand poco identificabile",
                "detail": "Nome, contatti e about non emergono chiaramente.",
            }
        )

    nap_bits = sum(1 for x in (phones, emails, addresses) if x)
    if nap_bits >= 2:
        geo += 3
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "NAP locale presente",
                "detail": f"Telefono/email/indirizzo rilevati in pagina ({nap_bits} segnali).",
            }
        )
    elif nap_bits == 1:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "NAP parziale",
                "detail": "Per LocalBusiness aggiungi telefono + indirizzo coerenti.",
            }
        )

    # consistency jsonld vs page
    if entity.get("telephone") and phones:
        norm_e = re.sub(r"\D", "", entity["telephone"])[-8:]
        if norm_e and any(norm_e in re.sub(r"\D", "", p) for p in phones):
            geo += 2
            findings.append(
                {
                    "category": "geo",
                    "severity": "ok",
                    "title": "NAP coerente",
                    "detail": "Telefono JSON-LD allineato al contenuto pagina.",
                }
            )

    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_geo_discoverability(page: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0

    hreflang = page.get("hreflang") or []
    lang = (page.get("lang") or "").lower()
    if hreflang:
        geo += 3
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "hreflang presente",
                "detail": f"{len(hreflang)} alternate: " + ", ".join(hreflang[:5]),
            }
        )
        if lang and not any(lang[:2] in h.lower() for h in hreflang):
            findings.append(
                {
                    "category": "geo",
                    "severity": "warn",
                    "title": "hreflang non allineato a lang",
                    "detail": f'html lang="{page.get("lang")}" assente tra gli hreflang.',
                }
            )
    elif lang:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "hreflang assente",
                "detail": "Utile se hai varianti lingua/mercato; altrimenti ok su sito mono-lingua.",
            }
        )

    if page.get("twitter_card") or page.get("twitter_title"):
        geo += 2
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "Twitter/X cards",
                "detail": page.get("twitter_card") or "twitter:title presente",
            }
        )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Twitter/X cards assenti",
                "detail": "Aggiungi twitter:card e twitter:title oltre Open Graph.",
            }
        )

    imgs = int(page.get("img_count") or 0)
    alt_ok = int(page.get("img_with_alt") or 0)
    dims_ok = int(page.get("img_with_dims") or 0)
    lazy = int(page.get("img_lazy") or 0)
    if imgs:
        alt_ratio = alt_ok / imgs
        if alt_ratio >= 0.8:
            geo += 2
            aio += 1
        elif alt_ratio < 0.5:
            findings.append(
                {
                    "category": "geo",
                    "severity": "warn",
                    "title": "Alt immagini insufficienti",
                    "detail": f"{alt_ok}/{imgs} immagini con alt utile.",
                }
            )
        if dims_ok / imgs < 0.4:
            findings.append(
                {
                    "category": "technical",
                    "severity": "warn",
                    "title": "Dimensioni immagini mancanti",
                    "detail": f"Solo {dims_ok}/{imgs} con width/height: rischio CLS.",
                }
            )
        if lazy >= max(3, int(imgs * 0.85)) and imgs >= 4:
            findings.append(
                {
                    "category": "technical",
                    "severity": "warn",
                    "title": "Lazy-load eccessivo",
                    "detail": f"{lazy}/{imgs} lazy: evita lazy sull’immagine LCP/hero.",
                }
            )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Nessuna immagine rilevata",
                "detail": "Un visual brand aiuta citazioni e anteprime.",
            }
        )

    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_technical_page(page: dict[str, Any], seed_url: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0

    status = page.get("status_code")
    if status and status >= 400:
        aio -= 8
        geo -= 8
        findings.append(
            {
                "category": "technical",
                "severity": "critical",
                "title": f"HTTP {status}",
                "detail": page.get("final_url") or page.get("requested_url") or "",
            }
        )

    ms = page.get("response_ms")
    if isinstance(ms, (int, float)):
        if ms > 3000:
            findings.append(
                {
                    "category": "technical",
                    "severity": "warn",
                    "title": "Risposta lenta",
                    "detail": f"~{int(ms)} ms: i crawler AI possono abbandonare.",
                }
            )
        elif ms < 800:
            geo += 1

    redirects = int(page.get("redirect_count") or 0)
    if redirects >= 3:
        findings.append(
            {
                "category": "technical",
                "severity": "warn",
                "title": "Redirect chain lunga",
                "detail": f"{redirects} hop: accorcia i redirect.",
            }
        )

    final = page.get("final_url") or ""
    req = page.get("requested_url") or seed_url
    if req.startswith("https://") and final.startswith("http://"):
        findings.append(
            {
                "category": "technical",
                "severity": "critical",
                "title": "HTTPS misto/declassato",
                "detail": "Richiesta HTTPS ma risposta finale HTTP.",
            }
        )
        aio -= 6
        geo -= 6

    robots = page.get("robots") or ""
    if re.search(r"nofollow", robots, re.I):
        findings.append(
            {
                "category": "technical",
                "severity": "warn",
                "title": "nofollow a livello pagina",
                "detail": "meta robots nofollow riduce la scoperta dei link.",
            }
        )

    canon = page.get("canonical") or ""
    if canon and not same_host(canon, seed_url):
        findings.append(
            {
                "category": "technical",
                "severity": "critical",
                "title": "Canonical cross-domain",
                "detail": f"Canonical punta fuori dominio: {canon}",
            }
        )
        aio -= 8
        geo -= 8

    if page.get("soft_404"):
        findings.append(
            {
                "category": "technical",
                "severity": "critical",
                "title": "Possibile soft-404",
                "detail": "La pagina sembra un errore ma restituisce 200.",
            }
        )
        aio -= 6
        geo -= 6

    html_kb = float(page.get("html_kb") or 0)
    blocking = int(page.get("blocking_scripts") or 0)
    if html_kb > 800:
        findings.append(
            {
                "category": "technical",
                "severity": "warn",
                "title": "HTML pesante",
                "detail": f"~{html_kb:.0f} KB: riduci markup per crawl più efficiente.",
            }
        )
    if blocking >= 6:
        findings.append(
            {
                "category": "technical",
                "severity": "warn",
                "title": "Script bloccanti",
                "detail": f"{blocking} script senza async/defer.",
            }
        )
    elif blocking <= 2 and html_kb and html_kb < 350:
        geo += 1
        aio += 1

    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_aux_files(probes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    for key, label in (("ai", "ai.txt"), ("humans", "humans.txt")):
        probe = probes.get(key) or {}
        if probe.get("ok"):
            aio += 2
            geo += 1
            findings.append(
                {
                    "category": "aio",
                    "severity": "ok",
                    "title": f"{label} presente",
                    "detail": probe.get("url") or f"/{label}",
                }
            )
        else:
            findings.append(
                {
                    "category": "aio",
                    "severity": "warn",
                    "title": f"{label} assente",
                    "detail": f"Opzionale ma utile: pubblica /{label} per agenti/crawler.",
                }
            )
    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_crawl_aggregate(
    pages: list[dict[str, Any]],
    *,
    sitemap_urls: list[str],
    seed_url: str,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    if not pages:
        return {"aio": aio, "geo": geo, "findings": findings, "coverage": 0.0}

    titles = [(p.get("title") or "").strip().lower() for p in pages]
    descs = [(p.get("description") or "").strip().lower() for p in pages]
    title_dupes = [t for t, n in Counter(titles).items() if t and n > 1]
    desc_dupes = [d for d, n in Counter(descs).items() if d and n > 1]
    if title_dupes:
        findings.append(
            {
                "category": "crawl",
                "severity": "warn",
                "title": "Title duplicati",
                "detail": f"{len(title_dupes)} title ripetuti tra pagine del campione.",
            }
        )
    else:
        aio += 2
    if desc_dupes:
        findings.append(
            {
                "category": "crawl",
                "severity": "warn",
                "title": "Description duplicate",
                "detail": f"{len(desc_dupes)} meta description ripetute nel campione.",
            }
        )

    thin = [p for p in pages if int(p.get("word_count") or 0) < 150]
    if thin:
        findings.append(
            {
                "category": "crawl",
                "severity": "warn" if len(thin) < len(pages) / 2 else "critical",
                "title": f"{len(thin)} thin pages",
                "detail": "Pagine con poco testo nel campione crawl.",
            }
        )

    # link graph orphans: pages never targeted by others' internal hrefs
    url_set = {p.get("url") for p in pages if p.get("url")}
    inbound: set[str] = set()
    for p in pages:
        for href in p.get("internal_hrefs") or []:
            if href in url_set:
                inbound.add(href)
    seed = pages[0].get("url")
    orphans = [u for u in url_set if u != seed and u not in inbound]
    if orphans:
        findings.append(
            {
                "category": "crawl",
                "severity": "warn",
                "title": "Pagine isolate nel campione",
                "detail": f"{len(orphans)} URL poco collegate internamente (es. {orphans[0][:70]}).",
            }
        )
    else:
        geo += 2

    # coverage sitemap
    coverage = 0.0
    if sitemap_urls:
        sm = set(sitemap_urls)
        crawled = {p.get("url") for p in pages if p.get("url")}
        # normalize rough
        hit = len([u for u in crawled if u in sm])
        coverage = round(100.0 * hit / max(len(sm), 1), 1)
        # also: how much of sitemap we sampled
        sample_cov = round(100.0 * min(len(pages), len(sm)) / max(len(sm), 1), 1)
        findings.append(
            {
                "category": "crawl",
                "severity": "ok" if sample_cov >= 20 or len(sm) <= len(pages) else "warn",
                "title": "Coverage sitemap",
                "detail": (
                    f"Sitemap {len(sm)} URL · campione {len(pages)} pagine "
                    f"(~{sample_cov}% della sitemap nel budget crawl)."
                ),
            }
        )
        # depth proxy: path segments
        depths = []
        for u in list(sm)[:200]:
            path = urlparse(u).path or "/"
            depths.append(path.count("/") - (1 if path.endswith("/") and path != "/" else 0))
        if depths:
            deep = sum(1 for d in depths if d >= 4)
            if deep > len(depths) * 0.35:
                findings.append(
                    {
                        "category": "crawl",
                        "severity": "warn",
                        "title": "Sitemap molto profonda",
                        "detail": f"{deep} URL con depth ≥4: verifica orphan e priorità.",
                    }
                )
    else:
        findings.append(
            {
                "category": "crawl",
                "severity": "warn",
                "title": "Coverage sitemap non calcolabile",
                "detail": "Sitemap assente o vuota: la scoperta resta limitata ai link.",
            }
        )

    errors = [p for p in pages if (p.get("status_code") or 200) >= 400]
    slow = [p for p in pages if (p.get("response_ms") or 0) > 3000]
    if errors:
        findings.append(
            {
                "category": "technical",
                "severity": "critical",
                "title": f"{len(errors)} URL con errore HTTP",
                "detail": "Correggi 4xx/5xx nel campione crawl.",
            }
        )
    if slow:
        findings.append(
            {
                "category": "technical",
                "severity": "warn",
                "title": f"{len(slow)} URL lente",
                "detail": "Tempo risposta >3s su parte del campione.",
            }
        )

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "coverage": coverage,
        "thin_count": len(thin),
        "orphan_count": len(orphans),
        "title_dupes": len(title_dupes),
        "desc_dupes": len(desc_dupes),
        "error_count": len(errors),
        "slow_count": len(slow),
        "sitemap_count": len(sitemap_urls),
    }


def build_fix_checklist(findings: list[dict[str, Any]]) -> str:
    crit = [f for f in findings if str(f.get("severity")).lower() == "critical"]
    warn = [f for f in findings if str(f.get("severity")).lower() == "warn"]
    lines = [
        "# Fix this week — GeoPulse",
        "",
        "Priorità consigliata per i prossimi 7 giorni.",
        "",
        "## Critical",
    ]
    if crit:
        for i, f in enumerate(crit[:12], 1):
            lines.append(f"{i}. **{f.get('title')}** — {f.get('detail')}")
    else:
        lines.append("- Nessun critical aperto.")
    lines.extend(["", "## Warn"])
    if warn:
        for i, f in enumerate(warn[:16], 1):
            lines.append(f"{i}. **{f.get('title')}** — {f.get('detail')}")
    else:
        lines.append("- Nessun warn aperto.")
    lines.extend(
        [
            "",
            "## Done when",
            "- Critical chiusi",
            "- llms.txt / robots bot policy pubblicati",
            "- Re-scan con score in crescita",
            "",
        ]
    )
    return "\n".join(lines)


def build_before_after_report(
    *,
    current: dict[str, Any],
    previous: Any | None,
    diff: dict[str, Any] | None,
) -> str:
    cur_aio = current.get("aio_score")
    cur_geo = current.get("geo_score")
    rating = compute_rating(cur_aio, cur_geo, current.get("findings"))
    lines = [
        "# Before / After — GeoPulse",
        "",
        f"## After (questa run)",
        f"- AIO: {cur_aio}",
        f"- GEO: {cur_geo}",
        f"- Rating: {rating.get('code')} ({rating.get('score')}/100)",
        "",
    ]
    if previous is None:
        lines.append("_Nessuna run precedente: questo è il baseline._\n")
        return "\n".join(lines)

    lines.extend(
        [
            "## Before",
            f"- AIO: {previous.aio_score}",
            f"- GEO: {previous.geo_score}",
            f"- Rating: {previous.rating.get('code') if hasattr(previous, 'rating') else '—'}",
            "",
        ]
    )
    if diff:
        lines.append("## Delta")
        if diff.get("delta_aio") is not None:
            lines.append(f"- AIO: {diff['delta_aio']:+d}")
        if diff.get("delta_geo") is not None:
            lines.append(f"- GEO: {diff['delta_geo']:+d}")
        if diff.get("improved"):
            lines.append("- Critical risolti: " + ", ".join(diff["improved"][:8]))
        if diff.get("regressed"):
            lines.append("- Nuovi critical: " + ", ".join(diff["regressed"][:8]))
        lines.append("")
    return "\n".join(lines)


def analyze_monitoring_alerts(
    *,
    probes: dict[str, dict[str, Any]],
    rating: dict[str, Any],
    previous: Any | None,
    diff: dict[str, Any] | None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    llms_ok = bool((probes.get("llms") or {}).get("ok"))
    if previous is not None:
        prev_findings = []
        try:
            prev_findings = previous.findings or []
        except Exception:
            prev_findings = []
        prev_had_llms = any(
            "llms.txt disponibile" in str(f.get("title") or "")
            or "llms.txt di buona" in str(f.get("title") or "")
            for f in prev_findings
        )
        prev_missing = any(
            "llms.txt assente" in str(f.get("title") or "") for f in prev_findings
        )
        if prev_had_llms and not llms_ok:
            findings.append(
                {
                    "category": "diff",
                    "severity": "critical",
                    "title": "Alert: llms.txt sparito",
                    "detail": "Era presente nella run precedente e ora non è raggiungibile.",
                }
            )
        if prev_missing and llms_ok:
            findings.append(
                {
                    "category": "diff",
                    "severity": "ok",
                    "title": "llms.txt ripristinato",
                    "detail": "Il file è di nuovo disponibile rispetto alla run precedente.",
                }
            )

        try:
            prev_rating = previous.rating
            if (
                isinstance(prev_rating, dict)
                and rating.get("index", 0) < prev_rating.get("index", 0)
            ):
                findings.append(
                    {
                        "category": "diff",
                        "severity": "critical",
                        "title": "Alert: rating in calo",
                        "detail": (
                            f"{prev_rating.get('code')} → {rating.get('code')} "
                            f"({prev_rating.get('score')}→{rating.get('score')})."
                        ),
                    }
                )
        except Exception:
            pass

        if diff and (
            (diff.get("delta_aio") is not None and diff["delta_aio"] <= -8)
            or (diff.get("delta_geo") is not None and diff["delta_geo"] <= -8)
        ):
            findings.append(
                {
                    "category": "diff",
                    "severity": "critical",
                    "title": "Alert: regressione score",
                    "detail": (
                        f"AIO {diff.get('delta_aio'):+d}, GEO {diff.get('delta_geo'):+d} "
                        "vs run precedente."
                    ),
                }
            )

    return {"aio": 0.0, "geo": 0.0, "findings": findings}


def summarize_competitor(result: dict[str, Any]) -> dict[str, Any]:
    rating = compute_rating(
        result.get("aio_score"), result.get("geo_score"), result.get("findings")
    )
    return {
        "url": (result.get("scraped") or {}).get("final_url")
        or (result.get("pages") or [{}])[0].get("url"),
        "domain": (result.get("scraped") or {}).get("domain"),
        "aio_score": result.get("aio_score"),
        "geo_score": result.get("geo_score"),
        "rating": rating.get("code"),
        "pages_analyzed": result.get("pages_analyzed"),
        "critical": sum(
            1
            for f in (result.get("findings") or [])
            if str(f.get("severity")).lower() == "critical"
        ),
    }
