"""Analisi GEO/AIO: crawl dominio (sitemap + link), probe e scoring."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from services.deep_checks import (
    ADDRESS_RE,
    AUTHOR_RE,
    ABOUT_HREF_RE,
    CONTACT_HREF_RE,
    DATE_RE,
    EMAIL_RE,
    PHONE_RE,
    analyze_aux_files,
    analyze_brand_nap,
    analyze_content_quality,
    analyze_crawl_aggregate,
    analyze_geo_discoverability,
    analyze_heading_hierarchy,
    analyze_technical_page,
    enrich_jsonld_entities,
    same_host,
    summarize_competitor,
)
from services.evidence import normalize_finding_evidence
from services.signals import (
    analyze_faq_signals,
    analyze_json_ld_types,
    analyze_llms_txt,
    analyze_robots_bots,
    detect_html_faq,
    extract_json_ld_from_soup,
)
from services.ssrf import UnsafeURLError, assert_public_http_url, safe_get

HTTP_TIMEOUT = 12
PROBE_TIMEOUT = 6
PAGE_TIMEOUT = 10
# Tetto di sicurezza operativo (anche per crawl “illimitato” Plus).
ABS_MAX_CRAWL_PAGES = 2000
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
    candidate = f"{parsed.scheme}://{parsed.netloc}{path}"
    # Blocca target privati / metadata prima di qualsiasi fetch
    return assert_public_http_url(candidate, resolve=True)


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
    import time

    t0 = time.perf_counter()
    response = safe_get(
        _SESSION,
        url,
        timeout=HTTP_TIMEOUT,
        max_redirects=5,
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    # Non raise subito su 4xx: servono metriche
    ctype = (response.headers.get("Content-Type") or "").lower()
    html = response.text or ""
    if len(html) > 1_500_000:
        html = html[:1_500_000]
    if response.status_code >= 400:
        # body minimo per soft signals
        pass
    elif "html" not in ctype and "xml" not in ctype and ctype:
        if "<html" not in html[:500].lower():
            response.raise_for_status()
            raise requests.RequestException(f"Non-HTML content-type: {ctype}")

    soup = BeautifulSoup(html, "lxml")
    jsonld_meta = extract_json_ld_from_soup(soup)
    has_json_ld = bool(jsonld_meta.get("block_count") or jsonld_meta.get("types"))
    entity = enrich_jsonld_entities(jsonld_meta)

    canonical = ""
    canon = soup.find("link", attrs={"rel": re.compile(r"canonical", re.I)})
    if canon and canon.get("href"):
        canonical = str(canon["href"]).strip()

    hreflang = []
    for link in soup.find_all("link", attrs={"rel": re.compile(r"alternate", re.I)}):
        hl = link.get("hreflang")
        if hl:
            hreflang.append(str(hl).strip())

    html_tag = soup.find("html")
    lang = ""
    if html_tag and html_tag.get("lang"):
        lang = str(html_tag["lang"]).strip()

    title = (soup.title.string or "").strip() if soup.title else ""
    description = _extract_meta(soup, name="description")
    robots = _extract_meta(soup, name="robots")
    og_title = _extract_meta(soup, prop="og:title")
    og_description = _extract_meta(soup, prop="og:description")
    twitter_card = _extract_meta(soup, name="twitter:card")
    twitter_title = _extract_meta(soup, name="twitter:title")
    author_meta = _extract_meta(soup, name="author")

    h1_tags = soup.find_all("h1")
    h2_tags = soup.find_all("h2")
    h1_count = len(h1_tags)
    h2_count = len(h2_tags)
    has_h1 = h1_count > 0

    imgs = soup.find_all("img")
    img_count = len(imgs)
    img_with_alt = sum(1 for i in imgs if (i.get("alt") or "").strip())
    img_with_dims = sum(1 for i in imgs if i.get("width") and i.get("height"))
    img_lazy = sum(
        1
        for i in imgs
        if str(i.get("loading") or "").lower() == "lazy"
        or "lazy" in str(i.get("class") or "").lower()
    )

    blocking_scripts = 0
    for script in soup.find_all("script"):
        if script.get("src") and not script.get("async") and not script.get("defer"):
            blocking_scripts += 1

    clean = BeautifulSoup(html, "lxml")
    for tag in clean(["script", "style", "noscript"]):
        tag.decompose()

    headings = [
        h.get_text(" ", strip=True)
        for h in clean.find_all(["h1", "h2"])
        if h.get_text(strip=True)
    ][:12]

    final_url = str(response.url)
    hrefs: list[str] = []
    links: list[str] = []
    internal_hrefs: list[str] = []
    internal_link_count = 0
    external_link_count = 0
    citation_link_count = 0
    has_about_link = False
    has_contact_link = False
    for a in clean.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        hrefs.append(href)
        text = a.get_text(" ", strip=True)
        if text and len(links) < 30:
            links.append(f"{text} -> {href}")
        abs_u = canonicalize_page_url(href, seed=final_url)
        if abs_u and same_domain(abs_u, final_url):
            internal_link_count += 1
            internal_hrefs.append(abs_u)
        else:
            external_link_count += 1
            if href.startswith("http"):
                citation_link_count += 1
        if ABOUT_HREF_RE.search(href) or ABOUT_HREF_RE.search(text or ""):
            has_about_link = True
        if CONTACT_HREF_RE.search(href) or CONTACT_HREF_RE.search(text or ""):
            has_contact_link = True

    body_text = " ".join(clean.get_text(" ", strip=True).split())
    words = len(body_text.split())
    html_faq = detect_html_faq(soup, body_text)
    phones = list({m.group(0) for m in PHONE_RE.finditer(body_text[:8000])})[:5]
    emails = list({m.group(0) for m in EMAIL_RE.finditer(body_text[:8000])})[:5]
    addresses = list({m.group(0) for m in ADDRESS_RE.finditer(body_text[:8000])})[:3]
    date_hits = len(DATE_RE.findall(body_text[:8000]))
    has_author_signal = bool(
        author_meta
        or soup.find("a", attrs={"rel": re.compile(r"author", re.I)})
        or AUTHOR_RE.search(body_text[:2500] or "")
    )
    soft_404 = bool(
        response.status_code == 200
        and (
            re.search(r"\b404\b|not found|pagina non trovata", title, re.I)
            or (words < 40 and re.search(r"\b404\b|not found", body_text[:500], re.I))
        )
    )

    redirect_count = max(0, len(response.history))
    return {
        "final_url": final_url,
        "requested_url": url,
        "status_code": response.status_code,
        "response_ms": elapsed_ms,
        "redirect_count": redirect_count,
        "html_kb": round(len(html.encode("utf-8", errors="ignore")) / 1024.0, 1),
        "blocking_scripts": blocking_scripts,
        "title": title,
        "description": description,
        "headings": headings,
        "h1_count": h1_count,
        "h2_count": h2_count,
        "links": links,
        "hrefs": hrefs,
        "internal_hrefs": internal_hrefs[:200],
        "internal_link_count": internal_link_count,
        "external_link_count": external_link_count,
        "citation_link_count": min(citation_link_count, external_link_count),
        "snippet": body_text[:2500],
        "word_count": words,
        "domain": urlparse(final_url).netloc,
        "has_json_ld": has_json_ld,
        "jsonld": jsonld_meta,
        "entity": entity,
        "html_faq": html_faq,
        "canonical": canonical,
        "lang": lang,
        "hreflang": hreflang[:12],
        "robots": robots,
        "og_title": og_title,
        "og_description": og_description,
        "twitter_card": twitter_card,
        "twitter_title": twitter_title,
        "has_h1": has_h1,
        "img_count": img_count,
        "img_with_alt": img_with_alt,
        "img_with_dims": img_with_dims,
        "img_lazy": img_lazy,
        "phones": phones,
        "emails": emails,
        "addresses": addresses,
        "date_hits": date_hits,
        "has_about_link": has_about_link,
        "has_contact_link": has_contact_link,
        "has_author_signal": has_author_signal,
        "soft_404": soft_404,
    }


# Compat alias
scrape_homepage = scrape_page


def probe_path(base_url: str, path: str) -> dict[str, Any]:
    target = urljoin(base_url if base_url.endswith("/") else base_url + "/", path.lstrip("/"))
    try:
        res = safe_get(
            _SESSION,
            target,
            timeout=PROBE_TIMEOUT,
            max_redirects=5,
        )
        body = res.text[:80_000] if res.text else ""
        ok = res.status_code == 200 and bool(body.strip())
        return {
            "url": str(res.url) if getattr(res, "url", None) else target,
            "ok": ok,
            "status": res.status_code,
            "snippet": body if ok else "",
        }
    except (requests.RequestException, UnsafeURLError):
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
            res = safe_get(
                _SESSION,
                child,
                timeout=PROBE_TIMEOUT,
                max_redirects=5,
            )
            if res.status_code != 200 or not res.text:
                continue
            more, _ = parse_sitemap_urls(res.text[:200_000], seed=seed, limit=limit - len(pages))
            pages.extend(more)
        except (requests.RequestException, UnsafeURLError):
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
    max_pages = max(1, min(int(max_pages), ABS_MAX_CRAWL_PAGES))
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

    sitemap_limit = min(max_pages * 4, ABS_MAX_CRAWL_PAGES)
    for u in collect_sitemap_urls(
        seed_url, probes.get("sitemap") or {}, limit=sitemap_limit
    ):
        add(u)
        if len(ordered) >= max_pages:
            return ordered[:max_pages]

    for href in scraped.get("internal_hrefs") or scraped.get("hrefs") or []:
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


def _enqueue_links(
    queue: list[str],
    seen: set[str],
    *,
    seed_url: str,
    scraped: dict[str, Any] | None,
    max_pages: int,
) -> None:
    if not scraped or len(seen) >= max_pages:
        return
    candidates: list[str] = []
    candidates.extend(scraped.get("internal_hrefs") or [])
    candidates.extend(scraped.get("hrefs") or [])
    for item in scraped.get("links") or []:
        if isinstance(item, str) and "->" in item:
            candidates.append(item.split("->", 1)[1].strip())
    for raw in candidates:
        if len(seen) + len(queue) >= max_pages * 2:
            break
        canon = canonicalize_page_url(raw, seed=seed_url)
        if not canon or canon in seen or canon in queue:
            continue
        queue.append(canon)


def crawl_domain_bfs(
    seed_url: str,
    seed_scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    *,
    max_pages: int,
    max_workers: int = 6,
) -> list[dict[str, Any]]:
    """
    Crawl BFS stesso dominio: sitemap + link interni fino a max_pages
    o finché non restano URL da visitare.
    """
    max_pages = max(1, min(int(max_pages), ABS_MAX_CRAWL_PAGES))
    seed_report = score_page_signals(seed_scraped)
    seed_report["scraped"] = seed_scraped
    reports: list[dict[str, Any]] = [seed_report]

    seed_canon = canonicalize_page_url(
        seed_scraped.get("final_url") or seed_url, seed=seed_url
    ) or canonicalize_page_url(seed_url, seed=seed_url)
    seen: set[str] = set()
    if seed_canon:
        seen.add(seed_canon)

    queue: list[str] = []
    for u in discover_domain_urls(
        seed_url, seed_scraped, probes, max_pages=max_pages
    ):
        if u in seen:
            continue
        queue.append(u)

    _enqueue_links(
        queue, seen, seed_url=seed_url, scraped=seed_scraped, max_pages=max_pages
    )

    while queue and len(reports) < max_pages:
        batch_n = min(max_workers, max_pages - len(reports), len(queue))
        batch = queue[:batch_n]
        del queue[:batch_n]
        # Evita di riaccodare URL già in batch
        for u in batch:
            seen.add(u)

        batch_reports = _crawl_extra_pages(batch, seed_url=seed_url, max_workers=batch_n)
        for report in batch_reports:
            if len(reports) >= max_pages:
                break
            reports.append(report)
            _enqueue_links(
                queue,
                seen,
                seed_url=seed_url,
                scraped=report.get("scraped"),
                max_pages=max_pages,
            )

    return reports


def _clamp(n: float) -> int:
    return max(0, min(100, int(round(n))))


PAGE_ISSUE_LABELS: dict[str, str] = {
    "title": "Title",
    "description": "Meta",
    "json_ld": "JSON-LD",
    "canonical": "Canonical",
    "og": "OG",
    "h1": "H1",
    "lang": "Lang",
    "noindex": "noindex",
    "crawl_fetch_failed": "Fetch",
    "off_domain_redirect": "Redirect",
}

PAGE_ISSUE_DETAILS: dict[str, str] = {
    "title": "Title assente o troppo corto",
    "description": "Meta description assente o troppo corta",
    "json_ld": "JSON-LD strutturato assente",
    "canonical": "Canonical URL mancante",
    "og": "Open Graph incompleto",
    "h1": "H1 assente",
    "lang": "Attributo lang mancante",
    "noindex": "Pagina con noindex (non indicizzabile)",
    "low_score": "Score AIO/GEO sotto soglia",
    "crawl_fetch_failed": "Fetch pagina fallito (timeout/rete/WAF)",
    "off_domain_redirect": "Redirect fuori dominio: pagina esclusa",
}

# Issues that always mark a page as critical.
_CRITICAL_PAGE_ISSUES = frozenset({"noindex"})


def page_severity(page: dict[str, Any]) -> str:
    """Severity UI per pagina crawl: critical | warn | ok."""
    issues = {str(i).lower() for i in (page.get("issues") or [])}
    try:
        aio = float(page.get("aio_score") if page.get("aio_score") is not None else 100)
    except (TypeError, ValueError):
        aio = 100.0
    try:
        geo = float(page.get("geo_score") if page.get("geo_score") is not None else 100)
    except (TypeError, ValueError):
        geo = 100.0

    if issues & _CRITICAL_PAGE_ISSUES or min(aio, geo) < 40 or (aio < 45 and geo < 45):
        return "critical"
    if issues or aio < 55 or geo < 55:
        return "warn"
    return "ok"


def _page_problem_details(page: dict[str, Any]) -> list[str]:
    """Elenco leggibile dei problemi per la UI dashboard."""
    details: list[str] = []
    seen: set[str] = set()
    for raw in page.get("issues") or []:
        key = str(raw).lower()
        text = PAGE_ISSUE_DETAILS.get(key) or PAGE_ISSUE_LABELS.get(key) or key
        if text in seen:
            continue
        seen.add(text)
        details.append(text)
    try:
        aio = float(page.get("aio_score") if page.get("aio_score") is not None else 100)
    except (TypeError, ValueError):
        aio = 100.0
    try:
        geo = float(page.get("geo_score") if page.get("geo_score") is not None else 100)
    except (TypeError, ValueError):
        geo = 100.0
    if (aio < 55 or geo < 55) and "low_score" not in {
        str(i).lower() for i in (page.get("issues") or [])
    }:
        low = PAGE_ISSUE_DETAILS["low_score"]
        if low not in seen:
            details.append(low)
    return details


def prioritize_crawl_pages(pages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Annota severity/issue labels e mette le criticità in cima."""
    rank = {"critical": 0, "warn": 1, "ok": 2}
    out: list[dict[str, Any]] = []
    for raw in pages or []:
        if not isinstance(raw, dict):
            continue
        page = dict(raw)
        severity = page_severity(page)
        issues = [str(i) for i in (page.get("issues") or [])]
        problems = _page_problem_details(page)
        page["severity"] = severity
        page["issue_labels"] = [
            PAGE_ISSUE_LABELS.get(i, i) for i in issues[:4]
        ]
        page["issue_count"] = len(issues)
        page["problems"] = problems
        out.append(page)

    def sort_key(p: dict[str, Any]) -> tuple[int, float, str]:
        aio = p.get("aio_score")
        geo = p.get("geo_score")
        try:
            avg = -((float(aio or 0) + float(geo or 0)) / 2)
        except (TypeError, ValueError):
            avg = 0.0
        return (rank.get(str(p.get("severity") or "ok"), 9), avg, str(p.get("url") or ""))

    out.sort(key=sort_key)
    return out


def critical_crawl_pages(pages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Solo pagine con criticità (critical/warn), già annotate e ordinate."""
    return [
        p
        for p in prioritize_crawl_pages(pages)
        if p.get("severity") in {"critical", "warn"}
    ]


_STORAGE_PAGE_KEYS = (
    "url",
    "title",
    "description",
    "aio_score",
    "geo_score",
    "issues",
    "word_count",
    "response_ms",
    "status_code",
    "crawl_error",
)


def pages_for_storage(
    pages: list[dict[str, Any]] | None,
    *,
    limit: int = 150,
) -> list[dict[str, Any]]:
    """
    Persiste le pagine in ordine di criticità (critical/warn prima),
    così il truncamento non perde i problemi.
    """
    limit = max(1, min(int(limit), ABS_MAX_CRAWL_PAGES))
    ranked = prioritize_crawl_pages(pages)
    out: list[dict[str, Any]] = []
    for page in ranked[:limit]:
        out.append({key: page.get(key) for key in _STORAGE_PAGE_KEYS})
    return out


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

    def push(
        category: str,
        severity: str,
        title: str,
        detail: str,
        *,
        evidence: str = "estimated",
    ) -> None:
        findings.append(
            {
                "category": category,
                "severity": severity,
                "title": title,
                "detail": detail,
                "evidence": evidence
                if evidence in {"measured", "proxy", "estimated"}
                else "estimated",
            }
        )

    title = scraped.get("title") or ""
    if len(title) >= 10:
        aio += 10
        geo += 8
        push("aio", "ok", "Title presente", f"Trovato: “{title[:90]}”", evidence="measured")
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
        push("geo", "ok", "Meta description utile", "Buona base per snippet generativi.", evidence="measured")
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

    entity = scraped.get("entity") or enrich_jsonld_entities(jsonld_meta)
    for block in (
        analyze_heading_hierarchy(scraped),
        analyze_content_quality(scraped),
        analyze_brand_nap(scraped, entity),
        analyze_geo_discoverability(scraped),
        analyze_technical_page(scraped, url),
    ):
        aio += block["aio"]
        geo += block["geo"]
        findings.extend(block["findings"])

    if scraped.get("canonical"):
        geo += 8
        push("technical", "ok", "Canonical impostato", scraped["canonical"], evidence="measured")
    else:
        push(
            "technical",
            "warn",
            "Canonical mancante",
            "Un canonical stabile riduce ambiguità tra URL duplicate.",
        )

    if scraped.get("og_title") or scraped.get("og_description"):
        geo += 6
        push("geo", "ok", "Open Graph presente", "Utile per anteprime e citazioni.", evidence="measured")
    else:
        push(
            "geo",
            "warn",
            "Open Graph assente",
            "og:title / og:description migliorano la rappresentazione del brand.",
        )

    if scraped.get("has_h1"):
        aio += 6
        push("aio", "ok", "H1 presente", "Gerarchia semantica rilevata.", evidence="measured")
    else:
        push(
            "aio",
            "warn",
            "H1 assente",
            "Un H1 chiaro rafforza il topic principale per i crawler AI.",
        )

    if scraped.get("lang"):
        geo += 6
        push("geo", "ok", "Lingua dichiarata", f'lang="{scraped["lang"]}"', evidence="measured")
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
        push("geo", "ok", "sitemap.xml presente", sitemap.get("url") or "/sitemap.xml", evidence="measured")
    else:
        push(
            "geo",
            "warn",
            "sitemap.xml assente",
            "Una sitemap aiuta la scoperta delle pagine chiave.",
        )

    pages = page_reports or []
    crawled = len(pages)
    page_payloads = []
    for p in pages:
        sc = p.get("scraped") or {}
        page_payloads.append(
            {
                "url": p.get("url") or sc.get("final_url"),
                "title": p.get("title") or sc.get("title"),
                "description": p.get("description") or sc.get("description") or "",
                "word_count": p.get("word_count") if p.get("word_count") is not None else sc.get("word_count"),
                "status_code": p.get("status_code") if p.get("status_code") is not None else sc.get("status_code"),
                "response_ms": p.get("response_ms") if p.get("response_ms") is not None else sc.get("response_ms"),
                "internal_hrefs": sc.get("internal_hrefs") or p.get("internal_hrefs") or [],
                "aio_score": p.get("aio_score"),
                "geo_score": p.get("geo_score"),
                "issues": p.get("issues") or [],
            }
        )

    sitemap_urls = list((probes.get("sitemap") or {}).get("urls") or [])
    crawl_agg = analyze_crawl_aggregate(
        page_payloads, sitemap_urls=sitemap_urls, seed_url=url
    )
    aio += crawl_agg["aio"]
    geo += crawl_agg["geo"]
    findings.extend(crawl_agg["findings"])

    aux = analyze_aux_files(probes)
    aio += aux["aio"]
    geo += aux["geo"]
    findings.extend(aux["findings"])

    if crawled > 1:
        avg_aio = sum(p["aio_score"] for p in pages) / crawled
        avg_geo = sum(p["geo_score"] for p in pages) / crawled
        aio = aio * 0.55 + avg_aio * 0.45
        geo = geo * 0.55 + avg_geo * 0.45

        weak = [p for p in pages if p["aio_score"] < 55 or p["geo_score"] < 55]
        missing_title = sum(1 for p in pages if "title" in p.get("issues", []))
        missing_h1 = sum(1 for p in pages if "h1" in p.get("issues", []))
        with_jsonld = sum(1 for p in pages if "json_ld" not in p.get("issues", []))

        push(
            "crawl",
            "ok",
            f"Crawl dominio: {crawled} pagine",
            f"Media pagine AIO {avg_aio:.0f} / GEO {avg_geo:.0f}.",
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
        if with_jsonld / crawled < 0.35:
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
            f"{crawled} pagine · suite AIO/GEO completa."
        )
    else:
        notes = (
            f"Analisi di {urlparse(url).netloc}: suite AIO/GEO completa "
            "(content, brand, GEO, tecnico, llms/robots)."
        )

    findings = normalize_finding_evidence(findings)

    return {
        "aio_score": _clamp(aio),
        "geo_score": _clamp(geo),
        "findings": findings,
        "notes": notes,
        "signals": {
            "jsonld": jsonld_meta,
            "entity": entity,
            "llms_quality": llms_score.get("quality"),
            "llms_sections": llms_score.get("sections") or [],
            "bot_policies": bots_score.get("policies") or {},
            "robots_probe_ok": bool(robots_probe.get("ok")),
            "faq": {
                "has_faq_page": bool(jsonld_meta.get("has_faq_page")),
                "faq_questions": jsonld_meta.get("faq_questions") or 0,
                "html_faq_likely": bool(
                    (scraped.get("html_faq") or {}).get("html_faq_likely")
                ),
            },
            "crawl": {
                "coverage": crawl_agg.get("coverage"),
                "thin_count": crawl_agg.get("thin_count"),
                "orphan_count": crawl_agg.get("orphan_count"),
                "sitemap_count": crawl_agg.get("sitemap_count"),
                "error_count": crawl_agg.get("error_count"),
                "slow_count": crawl_agg.get("slow_count"),
            },
        },
    }


def _crawl_extra_pages(urls: list[str], *, seed_url: str, max_workers: int = 4) -> list[dict[str, Any]]:
    """Scarica e scorea URL aggiuntivi (seed già fatto dal caller).

    Le pagine fallite restano come evidence (status/error) invece di sparire
    silenziosamente: utile per coverage e debug WAF/timeout.
    """
    reports: list[dict[str, Any]] = []
    if not urls:
        return reports

    def job(u: str) -> dict[str, Any] | None:
        try:
            page = scrape_page(u)
            # Se redirect fuori dominio, salta
            if not same_domain(page.get("final_url") or u, seed_url):
                return {
                    "url": u,
                    "title": "",
                    "aio_score": None,
                    "geo_score": None,
                    "issues": ["off_domain_redirect"],
                    "scraped": {
                        "url": u,
                        "final_url": page.get("final_url") or u,
                        "status_code": page.get("status_code"),
                        "word_count": 0,
                        "response_ms": page.get("response_ms"),
                        "description": "",
                    },
                    "crawl_error": "off_domain_redirect",
                }
            scored = score_page_signals(page)
            scored["scraped"] = page
            return scored
        except Exception as exc:
            return {
                "url": u,
                "title": "",
                "aio_score": None,
                "geo_score": None,
                "issues": ["crawl_fetch_failed"],
                "scraped": {
                    "url": u,
                    "final_url": u,
                    "status_code": None,
                    "word_count": 0,
                    "response_ms": None,
                    "description": "",
                },
                "crawl_error": str(exc)[:200],
            }

    workers = max(1, min(max_workers, len(urls)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(job, u): u for u in urls}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                reports.append(result)
    return reports


def analyze_site(
    url: str,
    *,
    max_pages: int = 1,
    competitor_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Analizza il dominio a partire da `url`.
    max_pages=1 → solo seed (+ probe root).
    max_pages>1 → crawl BFS stesso dominio (sitemap + link interni).
    """
    max_pages = max(1, min(int(max_pages), ABS_MAX_CRAWL_PAGES))
    scraped = scrape_page(url)
    if int(scraped.get("status_code") or 200) >= 400:
        raise requests.RequestException(
            f"HTTP {scraped.get('status_code')} su {url}"
        )
    base = scraped.get("final_url") or url
    paths = {
        "llms": "/llms.txt",
        "robots": "/robots.txt",
        "sitemap": "/sitemap.xml",
        "ai": "/ai.txt",
        "humans": "/humans.txt",
    }
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            key: pool.submit(probe_path, base, path) for key, path in paths.items()
        }
        probes = {key: fut.result() for key, fut in futures.items()}

    # Estrai URL sitemap per coverage (anche se host canonico ≠ seed IP)
    sm = probes.get("sitemap") or {}
    if sm.get("ok"):
        sm_limit = min(max(max_pages * 5, 40), ABS_MAX_CRAWL_PAGES)
        urls = collect_sitemap_urls(base, sm, limit=sm_limit)
        if not urls and sm.get("snippet"):
            urls = [
                u.strip()
                for u in re.findall(r"<loc>\s*([^<]+)\s*</loc>", sm["snippet"], flags=re.I)
            ][:sm_limit]
        probes["sitemap"]["urls"] = urls

    if max_pages <= 1:
        seed_report = score_page_signals(scraped)
        seed_report["scraped"] = scraped
        page_reports = [seed_report]
    else:
        page_reports = crawl_domain_bfs(
            base, scraped, probes, max_pages=max_pages
        )

    scored = score_site(url, scraped, probes, page_reports=page_reports)

    crawl_pages = [
        {
            "url": p.get("url"),
            "title": p.get("title") or "",
            "description": ((p.get("scraped") or {}).get("description") or "")[:300],
            "aio_score": p.get("aio_score"),
            "geo_score": p.get("geo_score"),
            "issues": p.get("issues") or [],
            "word_count": (p.get("scraped") or {}).get("word_count"),
            "response_ms": (p.get("scraped") or {}).get("response_ms"),
            "status_code": (p.get("scraped") or {}).get("status_code"),
            "crawl_error": p.get("crawl_error"),
        }
        for p in page_reports
    ]
    # Criticità prima: così storage/export non perdono le pagine con problemi.
    crawl_pages = pages_for_storage(crawl_pages, limit=len(crawl_pages) or 1)

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

    competitors: list[dict[str, Any]] = []
    for raw in (competitor_urls or [])[:3]:
        try:
            comp_url = normalize_url(raw)
            if same_host(comp_url, base):
                continue
            comp = analyze_site(comp_url, max_pages=min(5, max_pages))
            competitors.append(summarize_competitor(comp))
        except Exception:
            competitors.append({"url": raw, "error": "analisi non riuscita"})

    return {
        "scraped": scraped,
        "probes": probes,
        "pages": crawl_pages,
        "pages_analyzed": len(crawl_pages),
        "competitors": competitors,
        **scored,
    }
