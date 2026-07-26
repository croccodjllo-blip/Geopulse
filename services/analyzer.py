"""Analisi GEO/AIO: scrape, probe e scoring con findings."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HTTP_TIMEOUT = 15
USER_AGENT = "AIO-Bot/1.0 (+https://aio-bot.local; GEO/AIO optimizer)"


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r"^https?://", raw, flags=re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL non valido")
    path = parsed.path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


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


def scrape_homepage(url: str) -> dict[str, Any]:
    response = requests.get(
        url,
        timeout=HTTP_TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
        allow_redirects=True,
    )
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "lxml")

    # Segnali strutturali prima di rimuovere script
    has_json_ld = bool(
        soup.find("script", attrs={"type": re.compile(r"application/ld\+json", re.I)})
    )
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

    links: list[str] = []
    for a in clean.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        if href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        if text:
            links.append(f"{text} -> {href}")
        if len(links) >= 20:
            break

    body_text = " ".join(clean.get_text(" ", strip=True).split())
    return {
        "final_url": str(response.url),
        "title": title,
        "description": description,
        "headings": headings,
        "links": links,
        "snippet": body_text[:2500],
        "domain": urlparse(str(response.url)).netloc,
        "has_json_ld": has_json_ld,
        "canonical": canonical,
        "lang": lang,
        "robots": robots,
        "og_title": og_title,
        "og_description": og_description,
        "has_h1": has_h1,
    }


def probe_path(base_url: str, path: str) -> dict[str, Any]:
    target = urljoin(base_url if base_url.endswith("/") else base_url + "/", path.lstrip("/"))
    try:
        res = requests.get(
            target,
            timeout=8,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        ok = res.status_code == 200 and bool(res.text.strip())
        return {
            "url": target,
            "ok": ok,
            "status": res.status_code,
            "snippet": res.text[:300] if ok else "",
        }
    except requests.RequestException:
        return {"url": target, "ok": False, "status": None, "snippet": ""}


def _clamp(n: float) -> int:
    return max(0, min(100, int(round(n))))


def score_site(url: str, scraped: dict[str, Any], probes: dict[str, dict[str, Any]]) -> dict[str, Any]:
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

    if scraped.get("has_json_ld"):
        aio += 14
        geo += 10
        push("aio", "ok", "JSON-LD rilevato", "Schema strutturato aiuta AIO e GEO.")
    else:
        push(
            "aio",
            "critical",
            "Manca JSON-LD",
            "Senza Schema.org i motori generativi faticano a classificare il brand.",
        )

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
    if llms.get("ok"):
        aio += 14
        geo += 8
        push("aio", "ok", "llms.txt disponibile", llms.get("url") or "/llms.txt")
    else:
        push(
            "aio",
            "critical",
            "llms.txt assente",
            "Crea /llms.txt per guidare crawler e agenti AI sul tuo contenuto.",
        )

    robots_probe = probes.get("robots") or {}
    if robots_probe.get("ok"):
        geo += 6
        push("technical", "ok", "robots.txt raggiungibile", robots_probe.get("url") or "/robots.txt")
    else:
        push(
            "technical",
            "warn",
            "robots.txt assente o non raggiungibile",
            "Pubblica una policy chiara per crawler AI e sitemap.",
        )

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

    return {
        "aio_score": _clamp(aio),
        "geo_score": _clamp(geo),
        "findings": findings,
        "notes": (
            f"Analisi homepage di {urlparse(url).netloc} + probe "
            "/llms.txt, /robots.txt, /sitemap.xml."
        ),
    }


def analyze_site(url: str) -> dict[str, Any]:
    scraped = scrape_homepage(url)
    base = scraped.get("final_url") or url
    probes = {
        "llms": probe_path(base, "/llms.txt"),
        "robots": probe_path(base, "/robots.txt"),
        "sitemap": probe_path(base, "/sitemap.xml"),
    }
    scored = score_site(url, scraped, probes)
    return {"scraped": scraped, "probes": probes, **scored}
