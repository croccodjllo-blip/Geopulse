"""Analisi GEO/AIO: crawl dominio (sitemap + link), probe e scoring."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from services.signals import (
    analyze_faq_signals,
    analyze_json_ld_types,
    analyze_llms_txt,
    analyze_robots_bots,
    detect_html_faq,
    extract_json_ld_from_soup,
)

HTTP_TIMEOUT = 12
PROBE_TIMEOUT = 6
PAGE_TIMEOUT = 10
USER_AGENT = "GeoPulse/1.0 (+https://geopulse.it; GEO/AIO optimizer)"
_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
)

SKIP_EXT = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".zip",
    ".gz",
    ".mp4",
    ".mp3",
    ".css",
    ".js",
    ".ico",
    ".woff",
    ".woff2",
    ".xml",
    ".json",
    ".txt",
)
SKIP_PATH_RE = re.compile(
    r"(logout|sign[-_]?out|cart|checkout|wp-admin|admin/|/cdn-cgi/)",
    re.I,
)


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r"^https?://", raw, flags=re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL non valido")
    path = parsed.path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _host_key(netloc: str) -> str:
    host = (netloc or "").lower().split("@")[-1]
    if host.startswith("www."):
        host = host[4:]
    return host


def same_domain(url_a: str, url_b: str) -> bool:
    return _host_key(urlparse(url_a).netloc) == _host_key(urlparse(url_b).netloc)


def canonicalize_page_url(url: str, *, seed: str) -> str | None:
    """Normalizza URL pagina interna; None se da scartare."""
    if not url:
        return None
    absolute = urljoin(seed, url.strip())
    absolute, _frag = urldefrag(absolute)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not same_domain(absolute, seed):
        return None
    path = parsed.path or "/"
    lower = path.lower()
    if any(lower.endswith(ext) for ext in SKIP_EXT):
        return None
    if SKIP_PATH_RE.search(path):
        return None
    # Ignora query lunghe / tracking
    query = parsed.query
    if query and len(query) > 80:
        query = ""
    clean = urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", query, ""))
    return clean


def _extract_meta(soup: BeautifulSoup, *, name: str | None = None, prop: str | None = None) -> str:
    if name:
        tag = soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
    if prop:
        tag = soup.find("meta", attrs={"property": re.compile(f"^{re.escape(prop)}$", re.I)})
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
    return ""


def scrape_page(url: str) -> dict[str, Any]:
    response = _SESSION.get(
        url,
        timeout=HTTP_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    ctype = (response.headers.get("Content-Type") or "").lower()
    if "html" not in ctype and "xml" not in ctype and ctype:
        # Alcuni server non settano content-type; se body sembra HTML ok
        if "<html" not in (response.text[:500] or "").lower():
            raise requests.RequestException(f"Non-HTML content-type: {ctype}")

    html = response.text
    if len(html) > 1_500_000:
        html = html[:1_500_000]
    soup = BeautifulSoup(html, "lxml")

    jsonld_meta = extract_json_ld_from_soup(soup)
    has_json_ld = bool(jsonld_meta.get("block_count") or jsonld_meta.get("types"))
    canonical = ""
    canon = soup.find("link", attrs={"rel": re.compile(r"canonical", re.I)})
    if canon and canon.get("href"):
        canonical = str(canon["href"]).strip()

    html_tag = soup.find("html")
    lang = ""
    if html_tag and html_tag.get("lang"):
        lang = str(html_tag["lang"]).strip()

    title = (soup.title.string or "").strip() if soup.title else ""
    description = _extract_meta(soup, name="description")
    robots = _extract_meta(soup, name="robots")
    og_title = _extract_meta(soup, prop="og:title")
    og_description = _extract_meta(soup, prop="og:description")
    has_h1 = bool(soup.find("h1"))

    clean = BeautifulSoup(html, "lxml")
    for tag in clean(["script", "style", "noscript"]):
        tag.decompose()

    headings = [
        h.get_text(" ", strip=True)
        for h in clean.find_all(["h1", "h2"])
        if h.get_text(strip=True)
    ][:12]

    hrefs: list[str] = []
    links: list[str] = []
    for a in clean.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        hrefs.append(href)
        text = a.get_text(" ", strip=True)
        if text:
            links.append(f"{text} -> {href}")
        if len(links) >= 30:
            break

    body_text = " ".join(clean.get_text(" ", strip=True).split())
    html_faq = detect_html_faq(soup, body_text)
    final_url = str(response.url)
    return {
        "final_url": final_url,
        "requested_url": url,
        "title": title,
        "description": description,
        "headings": headings,
        "links": links,
        "hrefs": hrefs,
        "snippet": body_text[:2500],
        "domain": urlparse(final_url).netloc,
        "has_json_ld": has_json_ld,
        "jsonld": jsonld_meta,
        "html_faq": html_faq,
        "canonical": canonical,
        "lang": lang,
        "robots": robots,
        "og_title": og_title,
        "og_description": og_description,
        "has_h1": has_h1,
    }


# Compat alias
scrape_homepage = scrape_page


def probe_path(base_url: str, path: str) -> dict[str, Any]:
    target = urljoin(base_url if base_url.endswith("/") else base_url + "/", path.lstrip("/"))
    try:
        res = _SESSION.get(
            target,
            timeout=PROBE_TIMEOUT,
            allow_redirects=True,
        )
        body = res.text[:80_000] if res.text else ""
        ok = res.status_code == 200 and bool(body.strip())
        return {
            "url": target,
            "ok": ok,
            "status": res.status_code,
            "snippet": body if ok else "",
        }
    except requests.RequestException:
        return {"url": target, "ok": False, "status": None, "snippet": ""}


def _local_xml_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_sitemap_urls(xml_text: str, *, seed: str, limit: int = 100) -> tuple[list[str], list[str]]:
    """Ritorna (page_urls, child_sitemap_urls)."""
    pages: list[str] = []
    children: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # Fallback regex
        for match in re.findall(r"<loc>\s*([^<]+)\s*</loc>", xml_text, flags=re.I):
            canon = canonicalize_page_url(match.strip(), seed=seed)
            if canon:
                pages.append(canon)
            if len(pages) >= limit:
                break
        return pages, children

    tag = _local_xml_tag(root.tag).lower()
    if tag == "sitemapindex":
        for el in root:
            if _local_xml_tag(el.tag).lower() != "sitemap":
                continue
            for child in el:
                if _local_xml_tag(child.tag).lower() == "loc" and child.text:
                    children.append(child.text.strip())
        return pages, children

    for el in root.iter():
        if _local_xml_tag(el.tag).lower() != "loc" or not el.text:
            continue
        canon = canonicalize_page_url(el.text.strip(), seed=seed)
        if canon:
            pages.append(canon)
        if len(pages) >= limit:
            break
    return pages, children


def collect_sitemap_urls(seed: str, sitemap_probe: dict[str, Any], *, limit: int) -> list[str]:
    if not sitemap_probe.get("ok"):
        return []
    xml_text = sitemap_probe.get("snippet") or ""
    pages, children = parse_sitemap_urls(xml_text, seed=seed, limit=limit)
    # Segui fino a 3 sitemap figlie
    for child in children[:3]:
        if len(pages) >= limit:
            break
        try:
            res = _SESSION.get(child, timeout=PROBE_TIMEOUT, allow_redirects=True)
            if res.status_code != 200 or not res.text:
                continue
            more, _ = parse_sitemap_urls(res.text[:200_000], seed=seed, limit=limit - len(pages))
            pages.extend(more)
        except requests.RequestException:
            continue
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for u in pages:
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out


def discover_domain_urls(
    seed_url: str,
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    *,
    max_pages: int,
) -> list[str]:
    """Scopre URL dello stesso dominio: seed + sitemap + link homepage."""
    max_pages = max(1, min(int(max_pages), 50))
    ordered: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        canon = canonicalize_page_url(raw, seed=seed_url)
        if not canon or canon in seen:
            return
        seen.add(canon)
        ordered.append(canon)

    add(scraped.get("final_url") or seed_url)
    add(seed_url)

    for u in collect_sitemap_urls(
        seed_url, probes.get("sitemap") or {}, limit=max_pages * 3
    ):
        add(u)
        if len(ordered) >= max_pages:
            return ordered[:max_pages]

    for href in scraped.get("hrefs") or []:
        add(href)
        if len(ordered) >= max_pages:
            break

    # Fallback: link testuali "text -> href"
    for item in scraped.get("links") or []:
        if "->" in item:
            add(item.split("->", 1)[1].strip())
        if len(ordered) >= max_pages:
            break

    return ordered[:max_pages]


def _clamp(n: float) -> int:
    return max(0, min(100, int(round(n))))


def score_page_signals(scraped: dict[str, Any]) -> dict[str, Any]:
    """Score locale di una pagina (senza probe di root)."""
    aio = 20.0
    geo = 18.0
    issues: list[str] = []

    title = scraped.get("title") or ""
    if len(title) >= 10:
        aio += 12
        geo += 8
    else:
        issues.append("title")

    description = scraped.get("description") or ""
    if len(description) >= 50:
        aio += 8
        geo += 10
    else:
        issues.append("description")

    if scraped.get("has_json_ld"):
        aio += 10
        geo += 8
    else:
        issues.append("json_ld")

    if scraped.get("canonical"):
        geo += 8
    else:
        issues.append("canonical")

    if scraped.get("og_title") or scraped.get("og_description"):
        geo += 6
    else:
        issues.append("og")

    if scraped.get("has_h1"):
        aio += 8
    else:
        issues.append("h1")

    if scraped.get("lang"):
        geo += 6
    else:
        issues.append("lang")

    robots = scraped.get("robots") or ""
    if robots and re.search(r"noindex", robots, re.I):
        aio -= 30
        geo -= 30
        issues.append("noindex")

    return {
        "aio_score": _clamp(aio),
        "geo_score": _clamp(geo),
        "issues": issues,
        "url": scraped.get("final_url") or scraped.get("requested_url"),
        "title": title[:160],
    }


def score_site(
    url: str,
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    *,
    page_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 28.0
    geo = 26.0

    def push(category: str, severity: str, title: str, detail: str) -> None:
        findings.append(
            {
                "category": category,
                "severity": severity,
                "title": title,
                "detail": detail,
            }
        )

    title = scraped.get("title") or ""
    if len(title) >= 10:
        aio += 10
        geo += 8
        push("aio", "ok", "Title presente", f"Trovato: “{title[:90]}”")
    else:
        push(
            "aio",
            "critical",
            "Title assente o debole",
            "I modelli AI usano il title come segnale primario di entità.",
        )

    description = scraped.get("description") or ""
    if len(description) >= 50:
        aio += 8
        geo += 10
        push("geo", "ok", "Meta description utile", "Buona base per snippet generativi.")
    else:
        push(
            "geo",
            "warn",
            "Meta description insufficiente",
            "Aggiungi una description chiara (120–160 caratteri).",
        )

    jsonld_meta = scraped.get("jsonld") or {}
    jsonld_score = analyze_json_ld_types(jsonld_meta)
    aio += jsonld_score["aio"]
    geo += jsonld_score["geo"]
    findings.extend(jsonld_score["findings"])

    faq_score = analyze_faq_signals(jsonld_meta, scraped.get("html_faq") or {})
    aio += faq_score["aio"]
    geo += faq_score["geo"]
    findings.extend(faq_score["findings"])

    if scraped.get("canonical"):
        geo += 8
        push("technical", "ok", "Canonical impostato", scraped["canonical"])
    else:
        push(
            "technical",
            "warn",
            "Canonical mancante",
            "Un canonical stabile riduce ambiguità tra URL duplicate.",
        )

    if scraped.get("og_title") or scraped.get("og_description"):
        geo += 6
        push("geo", "ok", "Open Graph presente", "Utile per anteprime e citazioni.")
    else:
        push(
            "geo",
            "warn",
            "Open Graph assente",
            "og:title / og:description migliorano la rappresentazione del brand.",
        )

    if scraped.get("has_h1"):
        aio += 6
        push("aio", "ok", "H1 presente", "Gerarchia semantica rilevata.")
    else:
        push(
            "aio",
            "warn",
            "H1 assente",
            "Un H1 chiaro rafforza il topic principale per i crawler AI.",
        )

    if scraped.get("lang"):
        geo += 6
        push("geo", "ok", "Lingua dichiarata", f'lang="{scraped["lang"]}"')
    else:
        push(
            "geo",
            "warn",
            "Attributo lang mancante",
            "Dichiara la lingua primaria per GEO multilingua.",
        )

    robots = scraped.get("robots") or ""
    if robots and re.search(r"noindex", robots, re.I):
        aio -= 25
        geo -= 25
        push(
            "technical",
            "critical",
            "noindex attivo",
            "Il sito blocca l’indicizzazione: AIO/GEO non possono funzionare.",
        )

    llms = probes.get("llms") or {}
    llms_score = analyze_llms_txt(llms.get("snippet") or "", present=bool(llms.get("ok")))
    aio += llms_score["aio"]
    geo += llms_score["geo"]
    findings.extend(llms_score["findings"])

    robots_probe = probes.get("robots") or {}
    bots_score = analyze_robots_bots(
        robots_probe.get("snippet") or "",
        robots_ok=bool(robots_probe.get("ok")),
    )
    aio += bots_score["aio"]
    geo += bots_score["geo"]
    findings.extend(bots_score["findings"])

    sitemap = probes.get("sitemap") or {}
    if sitemap.get("ok"):
        geo += 8
        push("geo", "ok", "sitemap.xml presente", sitemap.get("url") or "/sitemap.xml")
    else:
        push(
            "geo",
            "warn",
            "sitemap.xml assente",
            "Una sitemap aiuta la scoperta delle pagine chiave.",
        )

    pages = page_reports or []
    crawled = len(pages)
    if crawled > 1:
        avg_aio = sum(p["aio_score"] for p in pages) / crawled
        avg_geo = sum(p["geo_score"] for p in pages) / crawled
        # Blend seed signals with domain page average
        aio = aio * 0.55 + avg_aio * 0.45
        geo = geo * 0.55 + avg_geo * 0.45

        weak = [p for p in pages if p["aio_score"] < 55 or p["geo_score"] < 55]
        missing_title = sum(1 for p in pages if "title" in p.get("issues", []))
        missing_h1 = sum(1 for p in pages if "h1" in p.get("issues", []))
        missing_desc = sum(1 for p in pages if "description" in p.get("issues", []))
        with_jsonld = sum(1 for p in pages if "json_ld" not in p.get("issues", []))

        push(
            "crawl",
            "ok",
            f"Crawl dominio: {crawled} pagine",
            f"Media pagine AIO {avg_aio:.0f} / GEO {avg_geo:.0f} "
            f"(seed + sitemap/link interni).",
        )
        if missing_title:
            push(
                "crawl",
                "warn" if missing_title < crawled / 2 else "critical",
                "Title deboli sul dominio",
                f"{missing_title}/{crawled} pagine senza title utile.",
            )
        if missing_h1:
            push(
                "crawl",
                "warn",
                "H1 assenti su più pagine",
                f"{missing_h1}/{crawled} pagine senza H1.",
            )
        if missing_desc:
            push(
                "crawl",
                "warn",
                "Meta description incomplete",
                f"{missing_desc}/{crawled} pagine con description insufficiente.",
            )
        coverage = with_jsonld / crawled
        if coverage < 0.35:
            push(
                "crawl",
                "warn",
                "JSON-LD poco diffuso",
                f"Solo {with_jsonld}/{crawled} pagine con dati strutturati.",
            )
        if weak:
            sample = ", ".join((p.get("url") or "")[:60] for p in weak[:3])
            push(
                "crawl",
                "warn",
                f"{len(weak)} pagine sotto soglia",
                f"Esempi: {sample}",
            )
        notes = (
            f"Analisi dominio {_host_key(urlparse(url).netloc)}: "
            f"{crawled} pagine + JSON-LD tipizzato, FAQ, policy bot, qualità llms.txt."
        )
    else:
        notes = (
            f"Analisi di {urlparse(url).netloc}: "
            "JSON-LD tipizzato, FAQ schema, policy bot AI, qualità llms.txt e probe root."
        )

    return {
        "aio_score": _clamp(aio),
        "geo_score": _clamp(geo),
        "findings": findings,
        "notes": notes,
        "signals": {
            "jsonld": jsonld_meta,
            "llms_quality": llms_score.get("quality"),
            "llms_sections": llms_score.get("sections") or [],
            "bot_policies": bots_score.get("policies") or {},
            "faq": {
                "has_faq_page": bool(jsonld_meta.get("has_faq_page")),
                "faq_questions": jsonld_meta.get("faq_questions") or 0,
                "html_faq_likely": bool((scraped.get("html_faq") or {}).get("html_faq_likely")),
            },
        },
    }


def _crawl_extra_pages(urls: list[str], *, seed_url: str, max_workers: int = 4) -> list[dict[str, Any]]:
    """Scarica e scorea URL aggiuntivi (seed già fatto dal caller)."""
    reports: list[dict[str, Any]] = []
    if not urls:
        return reports

    def job(u: str) -> dict[str, Any] | None:
        try:
            page = scrape_page(u)
            # Se redirect fuori dominio, salta
            if not same_domain(page.get("final_url") or u, seed_url):
                return None
            scored = score_page_signals(page)
            scored["scraped"] = page
            return scored
        except Exception:
            return None

    workers = max(1, min(max_workers, len(urls)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(job, u): u for u in urls}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                reports.append(result)
    return reports


def analyze_site(url: str, *, max_pages: int = 1) -> dict[str, Any]:
    """
    Analizza il dominio a partire da `url`.
    max_pages=1 → solo seed (+ probe root).
    max_pages>1 → seed + altre pagine da sitemap/link stesso dominio.
    """
    max_pages = max(1, min(int(max_pages), 50))
    scraped = scrape_page(url)
    base = scraped.get("final_url") or url
    paths = {
        "llms": "/llms.txt",
        "robots": "/robots.txt",
        "sitemap": "/sitemap.xml",
    }
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            key: pool.submit(probe_path, base, path) for key, path in paths.items()
        }
        probes = {key: fut.result() for key, fut in futures.items()}

    seed_report = score_page_signals(scraped)
    seed_report["scraped"] = scraped
    page_reports = [seed_report]

    discovered = discover_domain_urls(base, scraped, probes, max_pages=max_pages)
    extra_urls = [u for u in discovered if u != canonicalize_page_url(base, seed=base)]
    # Evita di ri-scaricare il seed
    seed_canon = canonicalize_page_url(base, seed=base)
    extra_urls = [u for u in extra_urls if u != seed_canon][: max(0, max_pages - 1)]

    if extra_urls:
        page_reports.extend(_crawl_extra_pages(extra_urls, seed_url=base))

    # Ordina: seed prima, poi per score
    def sort_key(p: dict[str, Any]) -> tuple[int, float]:
        is_seed = 0 if (p.get("url") == seed_canon or p.get("url") == base) else 1
        return (is_seed, -((p.get("aio_score") or 0) + (p.get("geo_score") or 0)) / 2)

    page_reports.sort(key=sort_key)

    scored = score_site(url, scraped, probes, page_reports=page_reports)

    crawl_pages = [
        {
            "url": p.get("url"),
            "title": p.get("title") or "",
            "aio_score": p.get("aio_score"),
            "geo_score": p.get("geo_score"),
            "issues": p.get("issues") or [],
        }
        for p in page_reports
    ]

    # Arricchisci scraped con elenco pagine per llms.txt
    important = []
    for p in crawl_pages[:20]:
        label = p.get("title") or p.get("url") or ""
        href = p.get("url") or ""
        if href:
            important.append(f"{label} -> {href}")
    scraped = {
        **scraped,
        "links": important or scraped.get("links") or [],
        "crawled_pages": crawl_pages,
        "pages_analyzed": len(crawl_pages),
    }

    return {
        "scraped": scraped,
        "probes": probes,
        "pages": crawl_pages,
        "pages_analyzed": len(crawl_pages),
        **scored,
    }
