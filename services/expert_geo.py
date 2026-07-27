"""Suite GEO expert: citabilità, autorità, answer-ready, distribuzione, trust, ops.

Molti check sono misurabili on-site + probe pubblici (Wikipedia/Wikidata).
Citazioni live multi-engine usano PERPLEXITY_API_KEY se presente, altrimenti proxy.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "GeoPulse/1.0 (+https://geopulse.it; GEO-expert)",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }
)

SURFACE_RE = {
    "linkedin": re.compile(r"linkedin\.com", re.I),
    "youtube": re.compile(r"youtube\.com|youtu\.be", re.I),
    "wikipedia": re.compile(r"wikipedia\.org", re.I),
    "wikidata": re.compile(r"wikidata\.org", re.I),
    "crunchbase": re.compile(r"crunchbase\.com", re.I),
    "github": re.compile(r"github\.com", re.I),
    "medium": re.compile(r"medium\.com", re.I),
    "substack": re.compile(r"substack\.com", re.I),
    "pdf": re.compile(r"\.pdf(\?|$)", re.I),
    "docs": re.compile(r"/(docs|documentation|developers|api)(/|$)", re.I),
}

SYNDICATION_RE = re.compile(
    r"(guest|contrib|press|newsroom|prnewswire|globenewswire|medium\.com|substack)",
    re.I,
)
DIRECT_ANSWER_RE = re.compile(
    r"^(.{40,220})$",
)
CLAIM_RE = re.compile(
    r"\b\d{1,3}\s*%|\b(?:milioni|miliardi|studio|ricerca|secondo|dato|fonte)\b",
    re.I,
)
EVIDENCE_RE = re.compile(r"(fonte|source|secondo|studio|ricerca|http)", re.I)
YMYL_RE = re.compile(
    r"\b(salute|health|medical|finanza|finance|legal|avvocato|invest|crypto|farmac)\b",
    re.I,
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


def _brand(scraped: dict[str, Any]) -> str:
    entity = scraped.get("entity") or {}
    if entity.get("brand_name"):
        return str(entity["brand_name"]).strip()
    dom = (scraped.get("domain") or "").replace("www.", "")
    return dom.split(".")[0].replace("-", " ").title() if dom else "Brand"


def _domain(scraped: dict[str, Any]) -> str:
    return (scraped.get("domain") or "").replace("www.", "")


def build_prompt_library(scraped: dict[str, Any], *, n: int = 24) -> list[dict[str, str]]:
    brand = _brand(scraped)
    domain = _domain(scraped)
    sector = (scraped.get("headings") or ["servizi"])[0]
    desc = (scraped.get("description") or scraped.get("snippet") or brand)[:120]
    templates = [
        ("informational", f"Cos’è {brand}?"),
        ("informational", f"A cosa serve {brand}?"),
        ("informational", f"Come funziona {brand}?"),
        ("informational", f"{brand} spiegato in modo semplice"),
        ("commercial", f"Alternatives to {brand}"),
        ("commercial", f"{brand} vs competitor"),
        ("commercial", f"Miglieri alternative a {domain}"),
        ("commercial", f"Vale la pena usare {brand}?"),
        ("local", f"{brand} recensioni"),
        ("local", f"{brand} contatti"),
        ("local", f"Dove si trova {brand}?"),
        ("howto", f"Come iniziare con {brand}"),
        ("howto", f"Guida pratica {sector}"),
        ("howto", f"Best practice {sector} 2026"),
        ("comparison", f"{brand} pricing"),
        ("comparison", f"{brand} pros and cons"),
        ("authority", f"Fonti autorevoli su {sector}"),
        ("authority", f"Statistiche {sector}"),
        ("authority", f"Report {sector} aggiornato"),
        ("definition", f"Definizione di {sector}"),
        ("definition", f"Glossario {sector}"),
        ("trust", f"{brand} è affidabile?"),
        ("trust", f"Chi c’è dietro {brand}?"),
        ("citation", f"Cita una fonte ufficiale su {desc}"),
    ]
    out = []
    for intent, prompt in templates[:n]:
        out.append({"intent": intent, "prompt": prompt})
    return out


def probe_wikipedia(brand: str) -> dict[str, Any]:
    if not brand or len(brand) < 2:
        return {"found": False}
    try:
        r = SESSION.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": brand,
                "srlimit": 3,
                "format": "json",
            },
            timeout=8,
        )
        if r.status_code >= 400:
            return {"found": False, "error": r.status_code}
        hits = ((r.json().get("query") or {}).get("search")) or []
        titles = [h.get("title") for h in hits if h.get("title")]
        exact = any(brand.lower() == str(t).lower() for t in titles)
        return {
            "found": bool(titles),
            "exact": exact,
            "titles": titles[:3],
        }
    except Exception as exc:
        return {"found": False, "error": str(exc)[:120]}


def probe_wikidata(brand: str) -> dict[str, Any]:
    if not brand:
        return {"found": False}
    try:
        r = SESSION.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": brand,
                "language": "en",
                "limit": 5,
                "format": "json",
            },
            timeout=8,
        )
        if r.status_code >= 400:
            return {"found": False, "error": r.status_code}
        hits = r.json().get("search") or []
        return {
            "found": bool(hits),
            "ids": [h.get("id") for h in hits if h.get("id")][:3],
            "labels": [h.get("label") for h in hits if h.get("label")][:3],
        }
    except Exception as exc:
        return {"found": False, "error": str(exc)[:120]}


def probe_answer_engine(brand: str, url: str, prompts: list[str]) -> dict[str, Any]:
    """Live citation probe via Perplexity if configured."""
    api_key = (os.getenv("PERPLEXITY_API_KEY") or "").strip()
    results = []
    if not api_key:
        return {"enabled": False, "results": [], "cited": 0, "total": 0}
    cited = 0
    for prompt in prompts[:5]:
        try:
            resp = SESSION.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=14,
            )
            text = ""
            if resp.status_code < 400:
                text = (
                    ((resp.json().get("choices") or [{}])[0].get("message") or {}).get(
                        "content"
                    )
                    or ""
                )
            hit = bool(
                brand
                and (
                    brand.lower() in text.lower()
                    or _domain({"domain": urlparse(url).netloc}).lower() in text.lower()
                )
            )
            if hit:
                cited += 1
            results.append(
                {
                    "prompt": prompt,
                    "cited": hit,
                    "excerpt": (text or "")[:220],
                    "engine": "perplexity",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "prompt": prompt,
                    "cited": False,
                    "error": str(exc)[:100],
                    "engine": "perplexity",
                }
            )
    return {
        "enabled": True,
        "results": results,
        "cited": cited,
        "total": len(results),
        "share": round(100 * cited / max(1, len(results))),
    }


def analyze_query_brand_match(
    scraped: dict[str, Any], library: list[dict[str, str]]
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    brand = _brand(scraped)
    url = scraped.get("final_url") or ""
    prompts = [p["prompt"] for p in library if p.get("intent") in {"informational", "authority", "definition"}]
    live = probe_answer_engine(brand, url, prompts)
    if live.get("enabled"):
        share = int(live.get("share") or 0)
        if share >= 40:
            aio += 6
            _push(
                findings,
                "aio",
                "ok",
                "Query→brand citation live",
                f"Citato in {live['cited']}/{live['total']} prompt Perplexity ({share}%).",
            )
        else:
            _push(
                findings,
                "aio",
                "warn",
                "Bassa citazione live su prompt",
                f"Solo {live['cited']}/{live['total']} prompt citano {brand}.",
            )
    else:
        # proxy: readiness for informational prompts
        has_def = bool(scraped.get("description")) and len(scraped.get("description") or "") >= 80
        has_llms = False  # filled by caller signals optionally
        score = 0
        if has_def:
            score += 1
        if scraped.get("has_json_ld"):
            score += 1
        if scraped.get("has_author_signal"):
            score += 1
        _push(
            findings,
            "aio",
            "warn" if score < 2 else "ok",
            "Query→brand match (proxy)",
            "Nessuna API live: stima su description/schema/author. "
            "Imposta PERPLEXITY_API_KEY per misura reale.",
        )
        if score >= 2:
            aio += 2
        live["proxy_score"] = score
    return {"aio": aio, "geo": 0.0, "findings": findings, "citation_live": live}


def analyze_answer_share_by_intent(
    library: list[dict[str, str]], citation_live: dict[str, Any]
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    by_intent: dict[str, list[bool]] = defaultdict(list)
    results = citation_live.get("results") or []
    prompt_intent = {p["prompt"]: p["intent"] for p in library}
    for row in results:
        intent = prompt_intent.get(row.get("prompt") or "", "other")
        by_intent[intent].append(bool(row.get("cited")))
    shares = {
        k: round(100 * sum(v) / max(1, len(v))) for k, v in by_intent.items() if v
    }
    if shares:
        weak = [k for k, v in shares.items() if v < 30]
        if not weak:
            aio += 3
            _push(
                findings,
                "aio",
                "ok",
                "Answer share per intent",
                "Share: " + ", ".join(f"{k} {v}%" for k, v in shares.items()),
            )
        else:
            _push(
                findings,
                "aio",
                "warn",
                "Answer share debole su intent",
                "Intent deboli: " + ", ".join(weak),
            )
    else:
        # structural proxy: ensure content covers intents
        intents = Counter(p["intent"] for p in library)
        _push(
            findings,
            "aio",
            "ok",
            "Intent library pronta",
            "Prompt per intent: "
            + ", ".join(f"{k}={v}" for k, v in intents.most_common()),
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "answer_share": shares}


def analyze_citation_position_proxy(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    # On-page signals that correlate with being a primary citation
    score = 0
    if (scraped.get("jsonld") or {}).get("has_organization"):
        score += 1
    if scraped.get("date_meta") or scraped.get("date_hits", 0) >= 2:
        score += 1
    if scraped.get("citation_link_count", 0) >= 2:
        score += 1
    if len(scraped.get("snippet") or "") > 400:
        score += 1
    label = "primary_ready" if score >= 3 else ("footnote_risk" if score >= 2 else "weak")
    if label == "primary_ready":
        aio += 2
        _push(
            findings,
            "aio",
            "ok",
            "Citation position readiness",
            "Segnali da fonte primaria (entity+date+depth+outbound).",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Rischio citazione footnote",
            "Pochi segnali da primary source: rafforza entity, date e depth.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "citation_position": label}


def analyze_citation_stability(
    previous: Any | None, citation_live: dict[str, Any]
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    now_share = citation_live.get("share")
    prev_share = None
    if previous is not None:
        try:
            adv = {}
            blob = getattr(previous, "signals", None) or {}
            if isinstance(blob, dict):
                adv = ((blob.get("advanced") or {}).get("extended") or {}).get(
                    "expert_geo"
                ) or blob.get("expert_geo") or {}
            prev_share = (adv.get("citation_live") or {}).get("share")
        except Exception:
            prev_share = None
    if now_share is not None and prev_share is not None:
        delta = int(now_share) - int(prev_share)
        if delta >= 10:
            aio += 2
            _push(
                findings,
                "aio",
                "ok",
                "Citation stability in crescita",
                f"Share {prev_share}% → {now_share}% ({delta:+d}).",
            )
        elif delta <= -10:
            _push(
                findings,
                "aio",
                "critical",
                "Citation stability in calo",
                f"Share {prev_share}% → {now_share}% ({delta:+d}).",
            )
        else:
            _push(
                findings,
                "aio",
                "ok",
                "Citation stability stabile",
                f"Share ~{now_share}% (Δ {delta:+d}).",
            )
    else:
        _push(
            findings,
            "aio",
            "ok",
            "Citation baseline impostata",
            "Prossime run misureranno stabilità citazioni nel tempo.",
        )
    return {
        "aio": aio,
        "geo": 0.0,
        "findings": findings,
        "citation_delta": None
        if now_share is None or prev_share is None
        else int(now_share) - int(prev_share),
    }


def analyze_cross_engine_parity(citation_live: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    # Only Perplexity live today; encode parity checklist for other engines
    engines = {"perplexity": "measured" if citation_live.get("enabled") else "proxy"}
    for name in ("chatgpt", "gemini", "ai_overview"):
        engines[name] = "pending_api"
    if citation_live.get("enabled"):
        aio += 1
        _push(
            findings,
            "aio",
            "ok",
            "Cross-engine parity (parziale)",
            "Perplexity misurato; ChatGPT/Gemini/AI Overview in coda API.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Cross-engine non misurato",
            "Configura PERPLEXITY_API_KEY; altri engine richiedono integrazioni dedicate.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "engines": engines}


def analyze_entity_completeness(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    brand = _brand(scraped)
    wiki = probe_wikipedia(brand)
    wikidata = probe_wikidata(brand)
    same_as = list((scraped.get("entity") or {}).get("same_as") or [])
    score = 0
    if wiki.get("found"):
        score += 2
    if wiki.get("exact"):
        score += 1
    if wikidata.get("found"):
        score += 2
    if same_as:
        score += 1
    if score >= 4:
        aio += 4
        geo += 2
        _push(
            findings,
            "aio",
            "ok",
            "Entity completeness forte",
            f"Wikipedia={wiki.get('found')} Wikidata={wikidata.get('found')} sameAs={len(same_as)}.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Entity KG incompleta",
            "Mancano Wikipedia/Wikidata/sameAs forti per ownership di entità.",
        )
    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "wikipedia": wiki,
        "wikidata": wikidata,
        "entity_score": score,
    }


def analyze_corroboration_graph(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    outbound = scraped.get("external_hrefs") or []
    hosts = {_host(u) for u in outbound if u}
    hosts.discard("")
    # third-party corroboration proxy = diverse outbound citation hosts
    n = len(hosts)
    if n >= 5:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Corroboration graph",
            f"{n} host esterni distinti citati (proxy di corroborazione).",
        )
    elif n >= 2:
        aio += 1
        _push(
            findings,
            "aio",
            "warn",
            "Corroboration limitata",
            f"Solo {n} host esterni: aumenta fonti indipendenti.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Poca corroborazione esterna",
            "Pochi link a fonti terze indipendenti.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "corroboration_hosts": n}


def _host(url: str) -> str:
    host = urlparse(url or "").netloc.lower().split("@")[-1]
    return host[4:] if host.startswith("www.") else host


def analyze_topic_ownership(scraped: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    brand = _brand(scraped).lower()
    titles = []
    for p in pages:
        titles.append((p.get("title") or (p.get("scraped") or {}).get("title") or "").lower())
    titles.append((scraped.get("title") or "").lower())
    brand_in_titles = sum(1 for t in titles if brand and brand.split()[0] in t)
    ratio = brand_in_titles / max(1, len(titles))
    if ratio >= 0.35:
        aio += 2
        _push(
            findings,
            "aio",
            "ok",
            "Brand–topic ownership",
            f"Brand in {brand_in_titles}/{len(titles)} title del campione.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Topic ownership debole",
            "Il brand appare poco nei title: rafforza ownership semantica.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "ownership_ratio": round(ratio, 2)}


def analyze_author_graph(scraped: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    author = bool(scraped.get("has_author_signal"))
    person = "Person" in set((scraped.get("jsonld") or {}).get("types") or [])
    author_urls = [
        p.get("url")
        for p in pages
        if p.get("url") and re.search(r"/(author|autore|team)/", p.get("url") or "", re.I)
    ]
    score = int(author) + int(person) + (1 if author_urls else 0)
    if score >= 2:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Author graph",
            f"Segnali author/Person/pagine dedicata={bool(author_urls)}.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Author graph incompleto",
            "Servono autore, Person schema e pagina bio/affiliazione.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "author_graph_score": score}


def analyze_consensus_uniqueness(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    text = scraped.get("snippet") or ""
    claims = len(CLAIM_RE.findall(text))
    evidence = len(EVIDENCE_RE.findall(text))
    unique_markers = len(
        re.findall(r"\b(proprietar|esclusiv|interno|nostro dataset|in-house)\b", text, re.I)
    )
    if claims and evidence and unique_markers:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Consensus + uniqueness",
            f"Claim {claims}, evidence {evidence}, originali {unique_markers}.",
        )
    elif claims and not unique_markers:
        _push(
            findings,
            "aio",
            "warn",
            "Poco insight unico",
            "Hai claim ma pochi asset proprietari citabili.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Consensus/uniqueness deboli",
            "Bilancia fatti allineati al consensus + dati originali.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_direct_answer_blocks(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    snippet = (scraped.get("snippet") or "").strip()
    first = " ".join(snippet.split()[:55])
    desc = scraped.get("description") or ""
    good = 40 <= len(first) <= 320 or 60 <= len(desc) <= 180
    if good and (desc or first):
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Direct-answer block",
            "Definizione/answer block presente in meta o apertura testo.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Manca direct-answer block",
            "Apri con 40–60 parole definitorie snippabili dai modelli.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "answer_block": first[:180]}


def analyze_extractability(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    html_faq = bool((scraped.get("html_faq") or {}).get("html_faq_likely"))
    h2 = int(scraped.get("h2_count") or 0)
    lists = 0
    # approximate from snippet punctuation / headings
    if h2 >= 3:
        lists += 1
    if html_faq:
        lists += 1
    if (scraped.get("jsonld") or {}).get("has_faq_page"):
        lists += 1
    if "HowTo" in set((scraped.get("jsonld") or {}).get("types") or []):
        lists += 1
    if lists >= 2:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Extractability alta",
            "Strutture snippabili: FAQ/H2/HowTo rilevate.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Bassa extractability",
            "Aggiungi liste, step, tabelle e FAQ esplicite.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "extractability": lists}


def analyze_claim_evidence_pairing(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    text = scraped.get("snippet") or ""
    claims = len(CLAIM_RE.findall(text))
    evidence = len(EVIDENCE_RE.findall(text))
    outbound = int(scraped.get("citation_link_count") or 0)
    if claims == 0:
        _push(findings, "aio", "warn", "Pochi claim strutturati", "Aggiungi claim verificabili.")
    elif evidence + outbound >= max(1, claims // 2):
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Claim–evidence pairing",
            f"Claim {claims} · evidence markers {evidence} · outbound {outbound}.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Claim senza evidence",
            "Abbina ogni claim a fonte/data/metodo.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings}


def analyze_freshness_decay(
    scraped: dict[str, Any], score_history: list[dict[str, Any]] | None
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    dates = list(scraped.get("date_meta") or [])
    dated = bool(dates) or int(scraped.get("date_hits") or 0) >= 2
    hist = score_history or []
    decay = None
    if len(hist) >= 3:
        vals = [(int(h.get("aio") or 0) + int(h.get("geo") or 0)) / 2 for h in hist[-4:]]
        decay = round(vals[-1] - vals[0], 1)
        if decay < -8 and not dated:
            _push(
                findings,
                "aio",
                "critical",
                "Freshness decay alto",
                f"Score Δ {decay} e poche date: aggiorna contenuti chiave.",
            )
        elif decay < -8:
            _push(
                findings,
                "aio",
                "warn",
                "Decay score con date presenti",
                f"Δ {decay}: verifica se i competitor hanno contenuti più freschi.",
            )
        else:
            aio += 1
            _push(findings, "aio", "ok", "Freshness decay sotto controllo", f"Δ score {decay}.")
    elif not dated:
        _push(
            findings,
            "aio",
            "warn",
            "Freshness non misurabile",
            "Poche date on-page: aggiungi datePublished/Modified.",
        )
    else:
        aio += 1
        _push(findings, "aio", "ok", "Segnali freshness presenti", "Date rilevate sulla seed.")
    return {"aio": aio, "geo": 0.0, "findings": findings, "freshness_delta": decay}


def analyze_contradictions(pages: list[dict[str, Any]], scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    phones = Counter()
    emails = Counter()
    for src in [scraped] + [(p.get("scraped") or {}) for p in pages if p.get("scraped")]:
        for ph in src.get("phones") or []:
            phones[re.sub(r"\D", "", ph)[-9:]] += 1
        for em in src.get("emails") or []:
            emails[em.lower()] += 1
    conflicts = (1 if len(phones) > 2 else 0) + (1 if len(emails) > 2 else 0)
    # title contradictions soft-404 vs brand pages already covered elsewhere
    if conflicts:
        aio -= 2
        _push(
            findings,
            "aio",
            "warn",
            "Contradiction audit",
            "NAP inconsistente tra pagine: rischio confusione entity per i modelli.",
        )
    else:
        aio += 1
        _push(findings, "aio", "ok", "Nessuna contraddizione NAP evidente", "Campione coerente.")
    return {"aio": aio, "geo": 0.0, "findings": findings, "contradictions": conflicts}


def analyze_multi_surface(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    same_as = list((scraped.get("entity") or {}).get("same_as") or [])
    hrefs = list(scraped.get("external_hrefs") or []) + same_as + list(scraped.get("hrefs") or [])
    found = []
    for name, rx in SURFACE_RE.items():
        if any(rx.search(str(h) or "") for h in hrefs):
            found.append(name)
    if len(found) >= 4:
        aio += 3
        geo += 2
        _push(
            findings,
            "aio",
            "ok",
            "Multi-surface presence",
            "Surface: " + ", ".join(found),
        )
    elif len(found) >= 2:
        aio += 1
        _push(
            findings,
            "aio",
            "warn",
            "Multi-surface parziale",
            "Presenti: " + ", ".join(found) + ". Aggiungi docs/YouTube/LinkedIn/PDF.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Presenza mono-surface",
            "Pochi canali oltre il sito: riduce probabilità di citazione.",
        )
    return {"aio": aio, "geo": geo, "findings": findings, "surfaces": found}


def analyze_syndication(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    hits = [
        h
        for h in (scraped.get("external_hrefs") or [])
        if SYNDICATION_RE.search(h or "")
    ]
    if hits:
        aio += 2
        _push(
            findings,
            "aio",
            "ok",
            "Syndication quality signals",
            f"{len(hits)} link verso press/guest/community.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Poca syndication",
            "Nessun segnale PR/guest/community rilevato nei link.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "syndication_hits": len(hits)}


def analyze_primary_source_assets(scraped: dict[str, Any], probes: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    assets = []
    if (probes.get("llms") or {}).get("ok"):
        assets.append("llms.txt")
    if any(".pdf" in (h or "").lower() for h in scraped.get("hrefs") or []):
        assets.append("pdf")
    if any(re.search(r"/(report|research|benchmark|dataset|stats)", h or "", re.I) for h in scraped.get("hrefs") or []):
        assets.append("report")
    if scraped.get("claim_hits", 0) >= 3:
        assets.append("stats")
    if len(assets) >= 2:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Primary source signals",
            "Asset: " + ", ".join(assets),
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Pochi primary source asset",
            "Crea report, dataset, tool o stats proprietarie citabili.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "primary_assets": assets}


def analyze_docs_hub(scraped: dict[str, Any], probes: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    docs = any(SURFACE_RE["docs"].search(h or "") for h in scraped.get("hrefs") or [])
    llms = bool((probes.get("llms") or {}).get("ok"))
    ai = bool((probes.get("ai") or {}).get("ok"))
    score = int(docs) + int(llms) + int(ai)
    if score >= 2:
        aio += 3
        _push(
            findings,
            "aio",
            "ok",
            "Machine-readable docs hub",
            f"docs={docs} llms={llms} ai.txt={ai}",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Docs hub incompleto",
            "Pubblica /docs + llms.txt + ai.txt come hub per agenti.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "docs_hub_score": score}


def analyze_citation_bait(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    text = f"{scraped.get('title') or ''} {scraped.get('snippet') or ''}"
    bait = []
    if re.search(r"\b(benchmark|report|studio|indagine|survey)\b", text, re.I):
        bait.append("benchmark")
    if re.search(r"\b(glossario|glossary|definizioni)\b", text, re.I):
        bait.append("glossary")
    if re.search(r"\b(statistiche|stats|dati|dataset)\b", text, re.I):
        bait.append("stats")
    if (scraped.get("jsonld") or {}).get("has_faq_page"):
        bait.append("faq")
    if bait:
        aio += 2
        _push(findings, "aio", "ok", "Citation bait assets", "Trovati: " + ", ".join(bait))
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Pochi citation bait",
            "Crea glossari, benchmark e statistiche originali.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "citation_bait": bait}


def analyze_ymyl_depth(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    text = f"{scraped.get('title') or ''} {scraped.get('description') or ''} {scraped.get('snippet') or ''}"
    ymyl = bool(YMYL_RE.search(text))
    if not ymyl:
        return {"aio": 0.0, "geo": 0.0, "findings": findings, "ymyl": False}
    depth = 0
    if scraped.get("has_author_signal"):
        depth += 1
    if scraped.get("has_about_link"):
        depth += 1
    if scraped.get("has_contact_link"):
        depth += 1
    if scraped.get("has_privacy_link"):
        depth += 1
    if depth >= 3:
        aio += 2
        _push(findings, "aio", "ok", "YMYL depth adeguata", f"Trust signals {depth}/4.")
    else:
        _push(
            findings,
            "aio",
            "critical" if depth <= 1 else "warn",
            "YMYL depth insufficiente",
            f"Solo {depth}/4 segnali trust su topic sensibile.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "ymyl": True, "ymyl_depth": depth}


def analyze_offsite_reputation(scraped: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    hrefs = (scraped.get("external_hrefs") or []) + list(
        (scraped.get("entity") or {}).get("same_as") or []
    )
    reviewish = [
        h
        for h in hrefs
        if re.search(r"(trustpilot|g2\.com|capterra|google\.[^/]+/maps|yelp|facebook\.com/.+reviews)", h or "", re.I)
    ]
    if reviewish:
        aio += 2
        geo += 1
        _push(
            findings,
            "aio",
            "ok",
            "Reputation off-site",
            f"{len(reviewish)} link a review/directory.",
        )
    else:
        _push(
            findings,
            "aio",
            "warn",
            "Reputation off-site assente",
            "Collega profili review coerenti col brand.",
        )
    return {"aio": aio, "geo": geo, "findings": findings, "reputation_links": len(reviewish)}


def analyze_bot_policy_fine(probes: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    robots = (probes.get("robots") or {}).get("snippet") or ""
    bots = ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Applebot-Extended")
    explicit = [b for b in bots if re.search(rf"User-agent:\s*{b}", robots, re.I)]
    if len(explicit) >= 3:
        aio += 2
        geo += 1
        _push(
            findings,
            "aio",
            "ok",
            "Bot access policy fine",
            "Policy esplicite: " + ", ".join(explicit),
        )
    elif robots:
        _push(
            findings,
            "aio",
            "warn",
            "Bot policy generica",
            "Dichiara Allow/Disallow per singolo AI bot, non solo User-agent: *.",
        )
    else:
        _push(findings, "aio", "critical", "robots.txt assente", "Nessuna policy bot.")
    return {"aio": aio, "geo": geo, "findings": findings, "explicit_bots": explicit}


def analyze_hallucination_risk(scraped: dict[str, Any], wiki: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    brand = _brand(scraped)
    ambiguous = bool(wiki.get("found") and not wiki.get("exact") and len(wiki.get("titles") or []) >= 2)
    generic = bool(re.fullmatch(r"(home|index|welcome|benvenuti)", (scraped.get("title") or "").strip(), re.I))
    if ambiguous:
        _push(
            findings,
            "aio",
            "warn",
            "Hallucination risk: omonimia",
            f"Wikipedia ha più hit per “{brand}”: disambigua con sameAs e Entity chiara.",
        )
    elif generic:
        _push(
            findings,
            "aio",
            "warn",
            "Hallucination risk: title generico",
            "Title troppo generico: i modelli confondono l’entità.",
        )
    else:
        aio += 1
        _push(findings, "aio", "ok", "Hallucination risk contenuto", "Entity naming relativamente chiaro.")
    return {"aio": aio, "geo": 0.0, "findings": findings, "ambiguous_entity": ambiguous}


def analyze_competitor_spoofing(
    scraped: dict[str, Any], competitors: list[dict[str, Any]] | None
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    brand = _brand(scraped).lower()
    stolen = []
    for c in competitors or []:
        # if competitor summary somehow includes our brand heavily — we only have scores
        # proxy: competitor domain similar to brand
        dom = (c.get("domain") or "").lower().replace("www.", "")
        if brand and brand.replace(" ", "") in dom.replace("-", "").replace(".", ""):
            stolen.append(dom)
    if stolen:
        _push(
            findings,
            "aio",
            "critical",
            "Competitor spoofing sospetto",
            "Domini rivali simili al brand: " + ", ".join(stolen),
        )
    else:
        aio += 0.5
        _push(
            findings,
            "aio",
            "ok",
            "Nessun spoofing dominio evidente",
            "I competitor analizzati non mimano il brand nel dominio.",
        )
    return {"aio": aio, "geo": 0.0, "findings": findings, "spoof_domains": stolen}


def analyze_win_loss(competitors: list[dict[str, Any]] | None, own: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    rows = []
    own_aio = int(own.get("aio_score") or 0)
    own_geo = int(own.get("geo_score") or 0)
    for c in competitors or []:
        if c.get("error") or c.get("aio_score") is None:
            continue
        gap = own_aio - int(c.get("aio_score") or 0)
        rows.append(
            {
                "domain": c.get("domain"),
                "result": "win" if gap >= 5 else ("loss" if gap <= -5 else "tie"),
                "gap_aio": gap,
                "gap_geo": own_geo - int(c.get("geo_score") or 0),
            }
        )
    wins = sum(1 for r in rows if r["result"] == "win")
    losses = sum(1 for r in rows if r["result"] == "loss")
    if rows:
        if wins >= losses:
            aio += 2
            _push(
                findings,
                "aio",
                "ok",
                "Win/loss vs competitor",
                f"{wins} win · {losses} loss su AIO.",
            )
        else:
            _push(
                findings,
                "aio",
                "warn",
                "Più loss che win vs competitor",
                f"{wins} win · {losses} loss: chiudi gap schema/llms/authority.",
            )
    return {"aio": aio, "geo": 0.0, "findings": findings, "win_loss": rows}


def build_content_brief(scraped: dict[str, Any], library: list[dict[str, str]]) -> str:
    brand = _brand(scraped)
    lines = [
        f"# Content brief for models — {brand}",
        "",
        "## Direct answer (40–60 parole)",
        scraped.get("description")
        or "Scrivi una definizione chiara del brand/servizio in 40–60 parole.",
        "",
        "## Struttura richiesta",
        "1. Definizione",
        "2. Per chi è",
        "3. Come funziona (step)",
        "4. Prove / dati / fonti",
        "5. FAQ (3–6 domande)",
        "",
        "## Prompt da coprire",
    ]
    for p in library[:12]:
        lines.append(f"- ({p['intent']}) {p['prompt']}")
    lines.extend(
        [
            "",
            "## Machine pack",
            "- Aggiorna llms.txt",
            "- FAQPage JSON-LD",
            "- Organization sameAs",
            "- DatePublished/Modified",
            "",
        ]
    )
    return "\n".join(lines)


def build_experiment_design(scraped: dict[str, Any]) -> str:
    brand = _brand(scraped)
    return "\n".join(
        [
            f"# GEO experiment design — {brand}",
            "",
            "## Ipotesi",
            "Un direct-answer block + FAQ schema + llms.txt aggiornato aumenta la share di citazione.",
            "",
            "## Varianti",
            "A. Control (stato attuale)",
            "B. Answer block in hero + FAQPage",
            "C. B + llms.txt + sameAs Wikipedia/Wikidata",
            "",
            "## Metriche",
            "- Citation share su 10 prompt fissi",
            "- AIO/GEO GeoPulse",
            "- Position proxy (primary vs footnote)",
            "",
            "## Protocollo",
            "1. Baseline scan + prompt probe",
            "2. Pubblica variante",
            "3. Re-scan a 3/7/14 giorni",
            "4. Confronta win/loss vs competitor",
            "",
            f"_Generato {datetime.now(timezone.utc).date().isoformat()}_",
            "",
        ]
    )


def build_prompt_library_md(library: list[dict[str, str]], brand: str) -> str:
    lines = [f"# GEO prompt library — {brand}", ""]
    by_intent: dict[str, list[str]] = defaultdict(list)
    for p in library:
        by_intent[p["intent"]].append(p["prompt"])
    for intent, prompts in by_intent.items():
        lines.append(f"## {intent}")
        for pr in prompts:
            lines.append(f"- {pr}")
        lines.append("")
    return "\n".join(lines)


def build_citation_rescan_playbook(brand: str) -> str:
    return "\n".join(
        [
            f"# Citation re-scan playbook — {brand}",
            "",
            "Dopo ogni publish GEO:",
            "1. Attendi 24–72h",
            "2. Riesegui analisi GeoPulse",
            "3. Riesegui prompt library (Perplexity/altre API)",
            "4. Registra citation share e win/loss",
            "5. Se share non sale: rafforza primary assets + entity KG",
            "",
        ]
    )


def run_expert_geo_suite(
    *,
    url: str,
    scraped: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    page_reports: list[dict[str, Any]],
    competitors: list[dict[str, Any]] | None = None,
    previous: Any | None = None,
    aio_score: int | None = None,
    geo_score: int | None = None,
    score_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pages = page_reports or []
    library = build_prompt_library(scraped)
    brand = _brand(scraped)

    blocks: list[dict[str, Any]] = []
    qbm = analyze_query_brand_match(scraped, library)
    blocks.append(qbm)
    citation_live = qbm.get("citation_live") or {}
    blocks.append(analyze_answer_share_by_intent(library, citation_live))
    blocks.append(analyze_citation_position_proxy(scraped))
    blocks.append(analyze_citation_stability(previous, citation_live))
    blocks.append(analyze_cross_engine_parity(citation_live))

    ent = analyze_entity_completeness(scraped)
    blocks.append(ent)
    blocks.append(analyze_corroboration_graph(scraped))
    blocks.append(analyze_topic_ownership(scraped, pages))
    blocks.append(analyze_author_graph(scraped, pages))
    blocks.append(analyze_consensus_uniqueness(scraped))

    blocks.append(analyze_direct_answer_blocks(scraped))
    blocks.append(analyze_extractability(scraped))
    blocks.append(analyze_claim_evidence_pairing(scraped))
    blocks.append(analyze_freshness_decay(scraped, score_history))
    blocks.append(analyze_contradictions(pages, scraped))

    blocks.append(analyze_multi_surface(scraped))
    blocks.append(analyze_syndication(scraped))
    blocks.append(analyze_primary_source_assets(scraped, probes))
    blocks.append(analyze_docs_hub(scraped, probes))
    blocks.append(analyze_citation_bait(scraped))

    blocks.append(analyze_ymyl_depth(scraped))
    blocks.append(analyze_offsite_reputation(scraped))
    blocks.append(analyze_bot_policy_fine(probes))
    blocks.append(analyze_hallucination_risk(scraped, ent.get("wikipedia") or {}))
    blocks.append(analyze_competitor_spoofing(scraped, competitors))

    # operational
    blocks.append(
        analyze_win_loss(competitors, {"aio_score": aio_score, "geo_score": geo_score})
    )
    ops_findings: list[dict[str, str]] = []
    _push(
        ops_findings,
        "aio",
        "ok",
        "Prompt library generata",
        f"{len(library)} prompt pronti per probe/citation re-scan.",
    )
    _push(
        ops_findings,
        "aio",
        "ok",
        "Content brief for models",
        "Brief operativo incluso nel pack.",
    )
    _push(
        ops_findings,
        "aio",
        "ok",
        "Citation re-scan playbook",
        "Playbook post-publish incluso nel pack.",
    )
    _push(
        ops_findings,
        "aio",
        "ok",
        "GEO experiment design",
        "Disegno A/B incluso nel pack.",
    )
    blocks.append({"aio": 1.0, "geo": 0.0, "findings": ops_findings})

    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    signals: dict[str, Any] = {"prompt_library_count": len(library)}
    for block in blocks:
        aio += float(block.get("aio") or 0)
        geo += float(block.get("geo") or 0)
        findings.extend(block.get("findings") or [])
        for k, v in block.items():
            if k not in {"aio", "geo", "findings"}:
                signals[k] = v

    artifacts = {
        "geo-prompt-library.md": build_prompt_library_md(library, brand),
        "geo-content-brief.md": build_content_brief(scraped, library),
        "geo-experiment-design.md": build_experiment_design(scraped),
        "geo-citation-rescan.md": build_citation_rescan_playbook(brand),
        "expert-geo.json": json.dumps(
            {
                "brand": brand,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "signals": {
                    k: v
                    for k, v in signals.items()
                    if k
                    in {
                        "citation_live",
                        "answer_share",
                        "citation_position",
                        "engines",
                        "wikipedia",
                        "wikidata",
                        "entity_score",
                        "surfaces",
                        "win_loss",
                        "ymyl",
                        "docs_hub_score",
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    }

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "signals": signals,
        "artifacts": artifacts,
    }
