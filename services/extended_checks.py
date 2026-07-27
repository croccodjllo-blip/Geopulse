"""Suite estesa AIO/GEO: 33 check aggiuntivi (proxy dove mancano API esterne)."""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urljoin, urlparse

import requests


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


def _nodes_of(jsonld: dict[str, Any], *types: str) -> list[dict[str, Any]]:
    out = []
    for node in jsonld.get("typed_nodes") or []:
        if set(node.get("types") or []) & set(types):
            out.append(node)
    return out


def analyze_live_citation_proxy(
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    readiness_score: int = 0,
) -> dict[str, Any]:
    """Citazioni live: se c'è API key prova un probe; altrimenti readiness estesa."""
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    brand = (scraped.get("entity") or {}).get("brand_name") or (
        scraped.get("domain") or ""
    ).replace("www.", "")
    engines: dict[str, str] = {}
    api_key = (os.getenv("PERPLEXITY_API_KEY") or "").strip()
    if api_key and brand:
        try:
            resp = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"In one short sentence: is {brand} "
                                f"({scraped.get('final_url')}) a known web source? "
                                "Mention if you would cite it."
                            ),
                        }
                    ],
                },
                timeout=12,
            )
            if resp.status_code < 400:
                text = (
                    ((resp.json().get("choices") or [{}])[0].get("message") or {}).get(
                        "content"
                    )
                    or ""
                )
                engines["perplexity"] = "mentioned" if brand.lower() in text.lower() else "unclear"
            else:
                engines["perplexity"] = f"http_{resp.status_code}"
        except Exception:
            engines["perplexity"] = "error"

    # Heuristic share-of-answer readiness for ChatGPT/Gemini/AI Overview
    score = int(readiness_score or 0)
    if (probes.get("llms") or {}).get("ok"):
        score += 1
    if scraped.get("citation_link_count", 0) >= 3:
        score += 1
    label = "alta" if score >= 7 else ("media" if score >= 4 else "bassa")
    if engines.get("perplexity") == "mentioned":
        aio += 5
        geo += 4
        _push(
            findings,
            "aio",
            "ok",
            "Citazione live Perplexity",
            f"Il brand {brand} compare nella risposta probe.",
        )
    elif api_key:
        _push(
            findings,
            "aio",
            "warn",
            "Citazione live non confermata",
            "Probe Perplexity eseguito senza menzione chiara del brand.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn" if label != "alta" else "ok",
            f"Citabilità answer engine (proxy) {label}",
            "Nessuna API live configurata (PERPLEXITY_API_KEY). "
            "Stima su llms/schema/author/citazioni outbound.",
        )
        if label == "alta":
            aio += 2
            geo += 1
    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "citation_engines": engines,
        "citation_proxy": label,
    }


def analyze_faq_intent_coverage(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    headings = scraped.get("headings") or []
    questions = [h for h in headings if "?" in h or re.match(r"^(come|cosa|chi|dove|perché|why|how|what)\b", h or "", re.I)]
    faq_n = int((scraped.get("jsonld") or {}).get("faq_questions") or 0)
    html_faq = bool((scraped.get("html_faq") or {}).get("html_faq_likely"))
    intent_n = len(questions)
    if faq_n >= max(3, intent_n):
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "FAQ intent coverage",
            f"{faq_n} Q&A schema vs {intent_n} intent in heading.",
        )
    elif intent_n and faq_n == 0 and not html_faq:
        _push(
            findings,
            "aio",
            "warn",
            "Intent senza FAQ",
            f"{intent_n} heading interrogativi senza FAQPage: genera Q&A schema.",
        )
    elif faq_n:
        aio += 1
        _push(
            findings,
            "aio",
            "warn",
            "FAQ parziale vs intent",
            f"FAQ schema {faq_n}, intent heading {intent_n}.",
        )
    return {"aio": aio, "geo": geo, "findings": findings, "intent_n": intent_n, "faq_n": faq_n}


def analyze_citable_claims(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    hits = int(scraped.get("claim_hits") or 0)
    citations = int(scraped.get("citation_link_count") or 0)
    dates = int(scraped.get("date_hits") or 0) + len(scraped.get("date_meta") or [])
    if hits >= 3 and (citations >= 1 or dates >= 1):
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Claim citabili",
            f"{hits} segnali numerici/fonte, {citations} link esterni, {dates} date.",
        )
    elif hits >= 2 and citations == 0:
        _push(
            findings,
            "aio",
            "warn",
            "Claim senza fonti",
            "Ci sono percentuali/claim ma mancano link a fonti verificabili.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Pochi claim citabili",
            "Aggiungi dati, date e fonti outbound per aumentare la citabilità AI.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_entity_salience(
    scraped: dict[str, Any], competitors: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    brand = (
        (scraped.get("entity") or {}).get("brand_name")
        or (scraped.get("domain") or "").replace("www.", "").split(".")[0]
    )
    text = f"{scraped.get('title') or ''} {scraped.get('snippet') or ''}".lower()
    brand_l = (brand or "").lower()
    brand_hits = text.count(brand_l) if brand_l and len(brand_l) >= 3 else 0
    comp_hits = 0
    for c in competitors or []:
        dom = (c.get("domain") or "").replace("www.", "").split(".")[0].lower()
        if dom and len(dom) >= 3:
            comp_hits += text.count(dom)
    if brand_hits >= 3 and brand_hits >= comp_hits:
        aio += 2
        _push(
            findings,
            "aio",
            "ok",
            "Entity salience brand",
            f"Brand “{brand}” ricorrente ({brand_hits}) più dei rivali nel testo seed.",
        )
    elif brand_hits == 0:
        _push(
            findings,
            "aio",
            "warn",
            "Brand poco saliente",
            "Il nome brand compare poco nel title/body: rafforza entity clarity.",
        )
    elif comp_hits > brand_hits:
        _push(
            findings,
            "aio",
            "warn",
            "Competitor più salienti nel copy",
            f"Brand hits {brand_hits} vs competitor {comp_hits} nel campione testo.",
        )
    return {
        "aio": aio,
        "geo": 0.0,
        "findings": findings,
        "brand_hits": brand_hits,
        "competitor_hits": comp_hits,
    }


def analyze_multilang_parity(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    langs = {
        str(p.get("lang") or "").lower()
        for p in (scraped.get("hreflang_pairs") or [])
        if p.get("lang")
    } or {str(x).lower() for x in (scraped.get("hreflang") or [])}
    core = {c.split("-")[0] for c in langs if c and c != "x-default"}
    if len(core) >= 2:
        geo += 2
        aio += 1
        _push(
            findings,
            "geo",
            "ok",
            "Multilingua dichiarato",
            "Lingue hreflang: " + ", ".join(sorted(core)[:8]),
        )
        if not ({"it", "en"} <= core or len(core) >= 3):
            _push(
                findings,
                "geo",
                "warn",
                "Parity IT/EN incompleta",
                "Per espansione GEO valuta almeno IT+EN allineati.",
            )
    elif scraped.get("lang"):
        _push(
            findings,
            "geo",
            "ok",
            "Sito mono-lingua",
            f'lang="{scraped.get("lang")}" senza alternate: ok se mercato unico.',
        )
    return {"aio": aio, "geo": geo, "findings": findings, "langs": sorted(core)}


def analyze_schema_strict(jsonld: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    if jsonld.get("parse_errors"):
        _push(
            findings,
            "aio",
            "critical",
            "Schema JSON non valido",
            f"{jsonld['parse_errors']} blocco/i con errore di parse.",
        )
        return {"aio": -3, "geo": -1, "findings": findings}
    required = {
        "Organization": {"name", "url"},
        "LocalBusiness": {"name", "url"},
        "WebSite": {"name", "url"},
        "FAQPage": {"mainEntity"},
        "Product": {"name"},
        "HowTo": {"name", "step"},
        "VideoObject": {"name"},
        "Article": {"headline", "author", "datePublished"},
        "BreadcrumbList": {"itemListElement"},
    }
    # typed_nodes only has keys list — map required to keys presence
    key_alias = {
        "mainEntity": "mainEntity",
        "step": "has_steps",
        "headline": "name",
        "author": "has_author",
        "datePublished": "has_date",
        "itemListElement": "itemListElement",
    }
    issues = 0
    ok = 0
    for node in jsonld.get("typed_nodes") or []:
        keys = set(node.get("keys") or [])
        for t in node.get("types") or []:
            need = required.get(t)
            if not need:
                continue
            missing = []
            for field in need:
                if field in {"step"} and node.get("has_steps"):
                    continue
                if field in {"author"} and node.get("has_author"):
                    continue
                if field in {"datePublished"} and node.get("has_date"):
                    continue
                alias = key_alias.get(field, field)
                if alias in keys or field in keys:
                    continue
                if field == "headline" and node.get("name"):
                    continue
                missing.append(field)
            if missing:
                issues += 1
                _push(
                    findings,
                    "aio",
                    "warn",
                    f"Schema {t} incompleto",
                    "Campi mancanti: " + ", ".join(missing),
                )
            else:
                ok += 1
    if ok and not issues:
        aio += 3
        _push(findings, "aio", "ok", "Schema strict ok", f"{ok} nodi tipizzati completi.")
    elif ok:
        aio += 1
    return {"aio": aio, "geo": geo, "findings": findings, "schema_ok": ok, "schema_issues": issues}


def analyze_product_offer(jsonld: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    products = _nodes_of(jsonld, "Product", "Offer")
    if not products:
        _push(
            findings,
            "aio",
            "ok",
            "Product schema N/A",
            "Nessun Product/Offer: skip se non e-commerce.",
        )
        return {"aio": aio, "geo": 0.0, "findings": findings}
    strong = [
        p
        for p in products
        if p.get("has_offers") or p.get("has_aggregate") or "offers" in (p.get("keys") or [])
    ]
    if strong:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Product/Offer completo",
            f"{len(strong)} nodi con offer/rating.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Product senza Offer/availability",
            "Aggiungi offers.price / availability / aggregateRating.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_howto_quality(jsonld: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    howtos = _nodes_of(jsonld, "HowTo")
    if not howtos:
        return {"aio": 0.0, "geo": 0.0, "findings": findings}
    good = [h for h in howtos if h.get("has_steps")]
    if good:
        aio += 3
        _push(findings, "aio", "ok", "HowTo con step", f"{len(good)} HowTo con step[].")
    else:
        _push(
            findings,
            "aio",
            "warn",
            "HowTo senza step",
            "HowTo presente ma senza step strutturati.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_video_transcript(jsonld: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    videos = _nodes_of(jsonld, "VideoObject")
    if not videos:
        return {"aio": 0.0, "geo": 0.0, "findings": findings}
    with_tr = [v for v in videos if v.get("has_transcript")]
    if with_tr:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "VideoObject + transcript",
            f"{len(with_tr)}/{len(videos)} con transcript/caption.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Video senza transcript",
            "Aggiungi transcript/caption per AIO e accessibilità.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_article_speakable(jsonld: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    articles = _nodes_of(jsonld, "Article", "NewsArticle", "BlogPosting")
    if not articles:
        return {"aio": 0.0, "geo": 0.0, "findings": findings}
    deep = [
        a
        for a in articles
        if a.get("has_author") and a.get("has_date")
    ]
    speak = [a for a in articles if a.get("has_speakable")]
    if deep:
        aio += 2
        _push(
            findings,
            "aio",
            "ok",
            "Article markup depth",
            f"{len(deep)} article con author+date.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Article schema superficiale",
            "Mancano author e/o datePublished.",
        )
    if speak:
        aio += 1
        _push(findings, "aio", "ok", "Speakable presente", f"{len(speak)} nodi speakable.")
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Speakable assente",
            "Utile per assistenti vocali / answer engine.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_lighthouse_optional(scraped: dict[str, Any]) -> dict[str, Any]:
    """Prova Lighthouse CLI se disponibile; altrimenti conferma proxy CWV."""
    findings: list[dict[str, str]] = []
    geo = 0.0
    metrics: dict[str, Any] = {}
    url = scraped.get("final_url") or scraped.get("requested_url")
    try:
        import shutil
        import subprocess
        import tempfile
        import json as _json

        if url and shutil.which("lighthouse"):
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "lh.json")
                subprocess.run(
                    [
                        "lighthouse",
                        url,
                        "--quiet",
                        "--chrome-flags=--headless --no-sandbox",
                        "--only-categories=performance",
                        f"--output-path={out}",
                        "--output=json",
                    ],
                    check=False,
                    timeout=90,
                    capture_output=True,
                )
                if os.path.isfile(out):
                    data = _json.loads(open(out, encoding="utf-8").read())
                    audits = data.get("audits") or {}
                    for key, label in (
                        ("largest-contentful-paint", "lcp_ms"),
                        ("interaction-to-next-paint", "inp_ms"),
                        ("cumulative-layout-shift", "cls"),
                    ):
                        val = (audits.get(key) or {}).get("numericValue")
                        if val is not None:
                            metrics[label] = round(float(val), 2)
                    if metrics:
                        geo += 3
                        _push(
                            findings,
                            "technical",
                            "ok",
                            "Lighthouse CWV misurato",
                            ", ".join(f"{k}={v}" for k, v in metrics.items()),
                        )
                        return {"aio": 0.0, "geo": geo, "findings": findings, "lighthouse": metrics}
    except Exception:
        pass
    _push(
        findings,
        "technical",
        "ok",
        "CWV via proxy GeoPulse",
        "Lighthouse/CrUX non disponibili in ambiente: usa stima TTFB/HTML/script.",
    )
    return {"aio": 0.0, "geo": geo, "findings": findings, "lighthouse": metrics}


def analyze_third_party_budget(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    n = int(scraped.get("third_party_scripts") or 0)
    if n <= 3:
        geo += 1
        _push(findings, "technical", "ok", "Third-party script budget", f"{n} script terzi.")
    elif n <= 8:
        _push(
            findings,
            "technical",
            "warn",
            "Molti script third-party",
            f"{n} script esterni: riduci tag manager/pixel non essenziali.",
        )
    else:
        geo -= 2
        _push(
            findings,
            "technical",
            "critical",
            "Budget script eccessivo",
            f"{n} script terzi: rischio INP/LCP.",
        )
    return {"aio": 0.0, "geo": geo, "findings": findings, "third_party_scripts": n}


def analyze_image_formats(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    total = int(scraped.get("img_count") or 0)
    modern = int(scraped.get("img_modern") or 0)
    srcset = int(scraped.get("img_with_srcset") or 0)
    if total == 0:
        return {"aio": 0.0, "geo": 0.0, "findings": findings}
    ratio = modern / total
    if ratio >= 0.4 or srcset >= max(1, total // 3):
        geo += 2
        _push(
            findings,
            "technical",
            "ok",
            "Image modern formats",
            f"WebP/AVIF {modern}/{total}, srcset {srcset}.",
        )
    else:
        _push(
            findings,
            "technical",
            "warn",
            "Immagini non ottimizzate",
            f"Pochi WebP/AVIF ({modern}/{total}) e srcset {srcset}: usa CDN/responsive.",
        )
    return {"aio": 0.0, "geo": geo, "findings": findings}


def analyze_font_loading(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    pre = int(scraped.get("font_preloads") or 0)
    face = bool(scraped.get("has_font_face"))
    if pre:
        geo += 1
        _push(findings, "technical", "ok", "Font preload", f"{pre} preload font.")
    elif face:
        _push(
            findings,
            "technical",
            "warn",
            "Font senza preload",
            "@font-face rilevato senza preload: rischio FOIT/FOUT.",
        )
    return {"aio": 0.0, "geo": geo, "findings": findings}


def analyze_sitemap_freshness(probes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    sm = probes.get("sitemap") or {}
    snippet = sm.get("snippet") or ""
    if not sm.get("ok"):
        return {"aio": 0.0, "geo": 0.0, "findings": findings}
    is_index = bool(re.search(r"<sitemapindex", snippet, re.I))
    lastmods = re.findall(r"<lastmod>\s*([^<]+)\s*</lastmod>", snippet, re.I)
    if is_index:
        geo += 1
        _push(findings, "geo", "ok", "Sitemap index", "sitemapindex rilevato.")
    if lastmods:
        geo += 1
        _push(
            findings,
            "geo",
            "ok",
            "Sitemap lastmod freshness",
            f"{len(lastmods)} lastmod nel campione sitemap.",
        )
    else:
        _push(
            findings,
            "geo",
            "warn",
            "Sitemap senza lastmod",
            "Aggiungi lastmod per segnalare freshness.",
        )
    return {"aio": 0.0, "geo": geo, "findings": findings, "sitemap_index": is_index}


def analyze_canonical_chain(scraped: dict[str, Any], seed_url: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    canonical = (scraped.get("canonical") or "").strip()
    final = scraped.get("final_url") or seed_url
    if not canonical:
        _push(findings, "technical", "warn", "Canonical assente", "Imposta self-canonical.")
        return {"aio": 0.0, "geo": geo, "findings": findings}
    abs_c = urljoin(final, canonical)
    if _host(abs_c) != _host(final):
        _push(
            findings,
            "technical",
            "critical",
            "Canonical cross-domain",
            f"Canonical punta a {_host(abs_c)}.",
        )
        geo -= 2
    else:
        # self-ish if path matches ignoring trailing slash
        a = urlparse(abs_c)
        b = urlparse(final)
        if a.path.rstrip("/") == b.path.rstrip("/"):
            geo += 1
            _push(findings, "technical", "ok", "Self-canonical", abs_c)
        else:
            _push(
                findings,
                "technical",
                "warn",
                "Canonical non self",
                f"{final} → {abs_c}",
            )
    return {"aio": 0.0, "geo": geo, "findings": findings}


def analyze_pagination(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    nxt, prev = scraped.get("rel_next") or "", scraped.get("rel_prev") or ""
    if nxt or prev:
        geo += 1
        _push(
            findings,
            "geo",
            "ok",
            "Pagination rel next/prev",
            f"next={bool(nxt)} prev={bool(prev)}",
        )
    return {"aio": 0.0, "geo": geo, "findings": findings}


def analyze_soft404_cluster(pages: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    soft = []
    for p in pages:
        sc = p.get("scraped") or p
        if sc.get("soft_404") or (
            int(sc.get("word_count") or 0) < 40
            and re.search(r"404|not found|non trovata", str(sc.get("title") or ""), re.I)
        ):
            soft.append(p.get("url") or sc.get("final_url"))
    if soft:
        geo -= 2
        _push(
            findings,
            "crawl",
            "critical" if len(soft) > 2 else "warn",
            "Soft-404 cluster",
            f"{len(soft)} URL sospette. Es: {soft[0]}",
        )
    return {"aio": 0.0, "geo": geo, "findings": findings, "soft404": soft[:10]}


def analyze_js_rendering(scraped: dict[str, Any]) -> dict[str, Any]:
    """Playwright opzionale; altrimenti euristica SPA."""
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    url = scraped.get("final_url")
    html_words = int(scraped.get("word_count") or 0)
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        if url:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=20000)
                rendered = page.inner_text("body")
                browser.close()
            rend_words = len((rendered or "").split())
            if html_words < 80 and rend_words > html_words * 3:
                aio -= 2
                geo -= 1
                _push(
                    findings,
                    "aio",
                    "critical",
                    "Contenuto solo JS-rendered",
                    f"HTML {html_words} parole vs rendered {rend_words}: SSR consigliato.",
                )
            else:
                aio += 1
                _push(
                    findings,
                    "aio",
                    "ok",
                    "Rendering HTML utile",
                    f"HTML {html_words} · rendered {rend_words}.",
                )
            return {
                "aio": aio,
                "geo": geo,
                "findings": findings,
                "rendered_words": rend_words,
            }
    except Exception:
        pass
    if html_words < 80 and int(scraped.get("blocking_scripts") or 0) >= 3:
        _push(
            findings,
            "aio",
            "warn",
            "Possibile dipendenza JS",
            "Playwright non disponibile: euristica SPA attiva.",
        )
    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_mixed_content(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    n = int(scraped.get("mixed_content") or 0)
    final = scraped.get("final_url") or ""
    if final.startswith("https://") and n:
        geo -= 2
        _push(
            findings,
            "technical",
            "warn" if n < 5 else "critical",
            "Mixed content HTTP",
            f"{n} risorse http:// su pagina HTTPS.",
        )
    elif final.startswith("https://"):
        geo += 1
        _push(findings, "technical", "ok", "HTTPS senza mixed content", "Nessun http:// evidente.")
    return {"aio": 0.0, "geo": geo, "findings": findings}


def analyze_topic_thin_clusters(pages: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    buckets: dict[str, list[str]] = defaultdict(list)
    for p in pages:
        sc = p.get("scraped") or p
        title = (p.get("title") or sc.get("title") or "").lower()
        words = re.findall(r"[a-zà-ü]{4,}", title)
        if len(words) < 2:
            continue
        key = " ".join(sorted(words[:4]))
        buckets[key].append(p.get("url") or "")
    thin_clusters = 0
    for key, urls in buckets.items():
        if len(urls) < 2:
            continue
        # if many similar titles and low word counts
        thin_clusters += 1
    if thin_clusters >= 2:
        aio -= 1
        _push(
            findings,
            "crawl",
            "warn",
            "Thin topic clusters",
            f"{thin_clusters} gruppi di title simili: rischio thin/cannibalization.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "topic_clusters": thin_clusters}


def analyze_keyword_cannibalization(pages: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    titles = [
        (p.get("title") or (p.get("scraped") or {}).get("title") or "").strip().lower()
        for p in pages
    ]
    titles = [t for t in titles if len(t) >= 12]
    dup = [t for t, n in Counter(titles).items() if n >= 2]
    near = 0
    for i, a in enumerate(titles):
        wa = set(re.findall(r"[a-zà-ü]{4,}", a))
        for b in titles[i + 1 :]:
            wb = set(re.findall(r"[a-zà-ü]{4,}", b))
            if not wa or not wb:
                continue
            j = len(wa & wb) / max(1, len(wa | wb))
            if j >= 0.7 and a != b:
                near += 1
    if dup or near >= 3:
        aio -= 2
        _push(
            findings,
            "aio",
            "warn",
            "Keyword cannibalization",
            f"Title duplicati {len(dup)}, near-match {near}.",
        )
    elif titles:
        aio += 1
        _push(findings, "aio", "ok", "Poca cannibalizzazione title", "Title distinti nel campione.")
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_readability(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    text = scraped.get("snippet") or ""
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    words = max(1, len(text.split()))
    chars = sum(len(w) for w in text.split())
    avg_w = words / sentences
    avg_c = chars / words
    # rough: prefer 12-22 words/sentence, 4.5-6.5 chars/word
    score = 100 - abs(avg_w - 17) * 3 - abs(avg_c - 5.5) * 8
    score = max(0, min(100, score))
    if score >= 65:
        aio += 2
        _push(
            findings,
            "aio",
            "ok",
            "Readability accettabile",
            f"Score {score:.0f} (parole/frase {avg_w:.1f}).",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Readability migliorabile",
            f"Score {score:.0f}: accorcia frasi e semplifica il lessico.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "readability": round(score)}


def analyze_internal_pagerank(pages: list[dict[str, Any]], seed_url: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    urls = []
    for p in pages:
        u = (p.get("url") or (p.get("scraped") or {}).get("final_url") or "").rstrip("/")
        if u:
            urls.append(u)
    if len(urls) < 3:
        return {"aio": 0.0, "geo": 0.0, "findings": findings}
    idx = {u: i for i, u in enumerate(urls)}
    n = len(urls)
    inbound = [0] * n
    for p in pages:
        sc = p.get("scraped") or {}
        for href in sc.get("internal_hrefs") or []:
            h = href.rstrip("/")
            if h in idx:
                inbound[idx[h]] += 1
    # simple equity share
    total = sum(inbound) or 1
    seed = (seed_url or "").rstrip("/")
    seed_i = idx.get(seed)
    top = sorted(range(n), key=lambda i: inbound[i], reverse=True)[:5]
    if seed_i is not None and inbound[seed_i] == 0 and n > 4:
        _push(
            findings,
            "geo",
            "warn",
            "Homepage poco linkata nel campione",
            "Pochi inbound verso la seed nel crawl interno.",
        )
    else:
        geo += 1
        _push(
            findings,
            "geo",
            "ok",
            "Internal link equity",
            "Top inbound: "
            + ", ".join(f"{inbound[i]}" for i in top[:3])
            + f" (somma {total}).",
        )
    orphans = sum(1 for v in inbound if v == 0)
    return {
        "aio": 0.0,
        "geo": geo,
        "findings": findings,
        "orphan_equity": orphans,
        "max_inbound": max(inbound) if inbound else 0,
    }


def analyze_outbound_broken(scraped: dict[str, Any], *, limit: int = 8) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    broken = []
    session = requests.Session()
    session.headers["User-Agent"] = "GeoPulse/1.0 (+https://geopulse.it; outbound-check)"
    for href in (scraped.get("external_hrefs") or [])[:limit]:
        try:
            r = session.head(href, timeout=4, allow_redirects=True)
            code = r.status_code
            if code >= 400 or code == 405:
                r = session.get(href, timeout=5, allow_redirects=True, stream=True)
                code = r.status_code
                r.close()
            if code >= 400:
                broken.append(f"{href} ({code})")
        except Exception:
            broken.append(f"{href} (errore)")
    if broken:
        geo -= 1
        _push(
            findings,
            "technical",
            "warn",
            "Outbound link rotti",
            f"{len(broken)} link esterni falliti. Es: {broken[0][:90]}",
        )
    elif scraped.get("external_hrefs"):
        geo += 1
        _push(findings, "technical", "ok", "Outbound campione ok", f"Verificati fino a {limit} link.")
    return {"aio": 0.0, "geo": geo, "findings": findings, "outbound_broken": broken}


def analyze_gbp_presence(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    links = scraped.get("gbp_links") or []
    if links:
        geo += 2
        _push(
            findings,
            "geo",
            "ok",
            "Google Business / Maps link",
            links[0][:120],
        )
    else:
        phones = scraped.get("phones") or []
        if phones or (scraped.get("entity") or {}).get("telephone"):
            _push(
                findings,
                "geo",
                "warn",
                "GBP non collegato",
                "Hai NAP ma nessun link Maps/g.page: collega il profilo Google Business.",
            )
    return {"aio": 0.0, "geo": geo, "findings": findings}


def analyze_review_consistency(jsonld: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    nodes = _nodes_of(jsonld, "Product", "LocalBusiness", "Organization", "Review")
    with_rev = [n for n in nodes if n.get("has_review") or n.get("has_aggregate")]
    if with_rev:
        aio += 2
        _push(
            findings,
            "aio",
            "ok",
            "Review/AggregateRating",
            f"{len(with_rev)} nodi con review/rating.",
        )
    elif _nodes_of(jsonld, "Product", "LocalBusiness"):
        _push(
            findings,
            "aio",
            "warn",
            "Manca review schema",
            "Product/LocalBusiness senza aggregateRating/review.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_legal_pages(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    flags = [
        ("privacy", scraped.get("has_privacy_link")),
        ("cookie", scraped.get("has_cookie_link")),
        ("legal/terms", scraped.get("has_legal_link")),
    ]
    ok = sum(1 for _, v in flags if v)
    if ok >= 2:
        geo += 2
        _push(
            findings,
            "geo",
            "ok",
            "Pagine legal/privacy",
            "Trovate: " + ", ".join(n for n, v in flags if v),
        )
    else:
        _push(
            findings,
            "geo",
            "warn",
            "Legal pages incomplete",
            "Assicura privacy/cookie/termini linkati in footer.",
        )
    return {"aio": 0.0, "geo": geo, "findings": findings, "legal_ok": ok}


def analyze_a11y_sample(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    geo = 0.0
    imgs = int(scraped.get("img_count") or 0)
    alts = int(scraped.get("img_with_alt") or 0)
    btn = int(scraped.get("buttons_no_name") or 0)
    inputs = int(scraped.get("inputs_no_label") or 0)
    issues = 0
    if imgs and alts / imgs < 0.7:
        issues += 1
        _push(
            findings,
            "technical",
            "warn",
            "A11y: alt immagini",
            f"Alt su {alts}/{imgs} immagini.",
        )
    if btn:
        issues += 1
        _push(
            findings,
            "technical",
            "warn",
            "A11y: button senza nome",
            f"{btn} button senza testo/aria-label.",
        )
    if inputs:
        issues += 1
        _push(
            findings,
            "technical",
            "warn",
            "A11y: input senza label",
            f"{inputs} campi form senza label.",
        )
    if issues == 0:
        geo += 1
        _push(findings, "technical", "ok", "A11y sample ok", "Alt/label/button nel campione.")
    return {"aio": 0.0, "geo": geo, "findings": findings, "a11y_issues": issues}


def analyze_share_of_voice(competitors: list[dict[str, Any]], own: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    valid = [c for c in (competitors or []) if c.get("aio_score") is not None]
    if not valid:
        return {"aio": 0.0, "geo": 0.0, "findings": findings}
    own_aio = int(own.get("aio_score") or 0)
    own_geo = int(own.get("geo_score") or 0)
    avg_aio = sum(int(c.get("aio_score") or 0) for c in valid) / len(valid)
    avg_geo = sum(int(c.get("geo_score") or 0) for c in valid) / len(valid)
    # pseudo SoV: score share
    sov = (own_aio + own_geo) / max(1.0, (own_aio + own_geo + avg_aio + avg_geo))
    pct = round(sov * 100)
    if pct >= 55:
        aio += 2
        geo += 1
        _push(
            findings,
            "aio",
            "ok",
            "Share-of-voice proxy alto",
            f"~{pct}% vs media competitor (AIO/GEO).",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Share-of-voice proxy basso",
            f"~{pct}%: i rivali mediamente battono su AIO/GEO.",
        )
    return {"aio": aio, "geo": geo, "findings": findings, "sov_pct": pct}


def analyze_pack_file_diff(previous: Any | None, current_pack_hints: dict[str, bool]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if previous is None:
        return {"aio": 0.0, "geo": 0.0, "findings": findings}
    prev_findings = []
    try:
        prev_findings = list(previous.findings or [])
    except Exception:
        prev_findings = []
    prev_titles = {str(f.get("title") or "") for f in prev_findings}
    mapping = {
        "llms": ("llms.txt disponibile", "llms.txt assente"),
        "robots": ("robots.txt raggiungibile", "robots.txt assente"),
        "org": ("Organization/LocalBusiness", "Manca Organization"),
        "faq": ("FAQ schema", "FAQ schema assente"),
    }
    for key, (ok_t, bad_t) in mapping.items():
        now = current_pack_hints.get(key)
        if now is None:
            continue
        had_ok = any(ok_t in t for t in prev_titles)
        had_bad = any(bad_t in t for t in prev_titles)
        if had_ok and now is False:
            _push(
                findings,
                "diff",
                "critical",
                f"Alert pack: {key} regresso",
                "Presente nella run precedente, ora assente.",
            )
        if had_bad and now is True:
            _push(
                findings,
                "diff",
                "ok",
                f"Pack ripristinato: {key}",
                "Segnale tornato positivo rispetto alla run precedente.",
            )
    return {"aio": 0.0, "geo": 0.0, "findings": findings}


def analyze_score_forecast(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    hist = history or []
    if len(hist) < 3:
        return {"aio": 0.0, "geo": 0.0, "findings": findings, "forecast": None}
    scores = [(int(h.get("aio") or 0) + int(h.get("geo") or 0)) / 2 for h in hist[-6:]]
    # linear slope
    xs = list(range(len(scores)))
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(scores) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, scores))
    den = sum((x - mean_x) ** 2 for x in xs) or 1
    slope = num / den
    forecast = round(scores[-1] + slope, 1)
    risk = "calo" if slope < -1.5 else ("stabile" if abs(slope) <= 1.5 else "crescita")
    if risk == "calo":
        _push(
            findings,
            "diff",
            "warn",
            "Forecast score in calo",
            f"Trend slope {slope:.2f} → proiezione {forecast}.",
        )
    else:
        aio += 0.5
        _push(
            findings,
            "diff",
            "ok",
            f"Forecast score {risk}",
            f"Slope {slope:.2f} · proiezione {forecast}.",
        )
    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "forecast": {"slope": round(slope, 2), "next": forecast, "risk": risk},
    }


def maybe_send_regression_alerts(findings: list[dict[str, str]], *, domain: str) -> dict[str, Any]:
    """Invia alert Slack/Telegram se configurati e ci sono critical diff."""
    critical = [
        f
        for f in findings
        if str(f.get("severity")).lower() == "critical"
        and str(f.get("category")).lower() in {"diff", "technical", "aio", "geo", "crawl"}
    ]
    if not critical:
        return {"sent": False, "reason": "no_critical"}
    text = f"GeoPulse alert — {domain}\n" + "\n".join(
        f"• [{f.get('severity')}] {f.get('title')}: {f.get('detail')}" for f in critical[:8]
    )
    sent = []
    slack = (os.getenv("SLACK_WEBHOOK_URL") or "").strip()
    if slack:
        try:
            requests.post(slack, json={"text": text}, timeout=8)
            sent.append("slack")
        except Exception:
            pass
    tg_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    tg_chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if tg_token and tg_chat:
        try:
            requests.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": tg_chat, "text": text},
                timeout=8,
            )
            sent.append("telegram")
        except Exception:
            pass
    return {"sent": bool(sent), "channels": sent}


def run_extended_suite(
    *,
    url: str,
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    page_reports: list[dict[str, Any]],
    competitors: list[dict[str, Any]] | None = None,
    previous: Any | None = None,
    aio_score: int | None = None,
    geo_score: int | None = None,
    readiness_score: int = 0,
    score_history: list[dict[str, Any]] | None = None,
    send_alerts: bool = True,
) -> dict[str, Any]:
    pages = page_reports or []
    jsonld = scraped.get("jsonld") or {}
    blocks = [
        analyze_live_citation_proxy(scraped, probes, readiness_score),
        analyze_faq_intent_coverage(scraped),
        analyze_citable_claims(scraped),
        analyze_entity_salience(scraped, competitors),
        analyze_multilang_parity(scraped),
        analyze_schema_strict(jsonld),
        analyze_product_offer(jsonld),
        analyze_howto_quality(jsonld),
        analyze_video_transcript(jsonld),
        analyze_article_speakable(jsonld),
        analyze_lighthouse_optional(scraped),
        analyze_third_party_budget(scraped),
        analyze_image_formats(scraped),
        analyze_font_loading(scraped),
        analyze_sitemap_freshness(probes),
        analyze_canonical_chain(scraped, url),
        analyze_pagination(scraped),
        analyze_soft404_cluster(pages),
        analyze_js_rendering(scraped),
        analyze_mixed_content(scraped),
        analyze_topic_thin_clusters(pages),
        analyze_keyword_cannibalization(pages),
        analyze_readability(scraped),
        analyze_internal_pagerank(pages, url),
        analyze_outbound_broken(scraped),
        analyze_gbp_presence(scraped),
        analyze_review_consistency(jsonld),
        analyze_legal_pages(scraped),
        analyze_a11y_sample(scraped),
        analyze_share_of_voice(competitors or [], {"aio_score": aio_score, "geo_score": geo_score}),
        analyze_pack_file_diff(
            previous,
            {
                "llms": bool((probes.get("llms") or {}).get("ok")),
                "robots": bool((probes.get("robots") or {}).get("ok")),
                "org": bool(jsonld.get("has_organization")),
                "faq": bool(jsonld.get("has_faq_page")),
            },
        ),
        analyze_score_forecast(score_history),
    ]

    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    signals: dict[str, Any] = {}
    for block in blocks:
        aio += float(block.get("aio") or 0)
        geo += float(block.get("geo") or 0)
        findings.extend(block.get("findings") or [])
        for k, v in block.items():
            if k in {"aio", "geo", "findings"}:
                continue
            signals[k] = v

    alert_info = {"sent": False}
    if send_alerts:
        alert_info = maybe_send_regression_alerts(
            findings, domain=scraped.get("domain") or _host(url)
        )
    signals["alerts"] = alert_info

    md_lines = [
        "# Extended analysis — GeoPulse",
        "",
        f"Domain: {scraped.get('domain')}",
        f"AIO delta: {aio:.1f} · GEO delta: {geo:.1f}",
        "",
        "## Findings",
    ]
    for f in findings:
        if str(f.get("severity")).lower() in {"critical", "warn", "ok"}:
            md_lines.append(f"- **{f.get('severity')}** {f.get('title')} — {f.get('detail')}")
    md_lines.append("")

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "signals": signals,
        "artifacts": {"extended-analysis.md": "\n".join(md_lines)},
    }
