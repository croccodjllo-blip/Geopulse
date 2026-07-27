"""Check avanzati AIO/GEO: JSON-LD tipizzato, bots, llms, FAQ, diff run."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

AI_BOTS = (
    "GPTBot",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
    "Applebot-Extended",
)

VALUABLE_TYPES = {
    "Organization",
    "LocalBusiness",
    "WebSite",
    "WebPage",
    "FAQPage",
    "Article",
    "NewsArticle",
    "BlogPosting",
    "Person",
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
    "Service",
    "AboutPage",
    "ContactPage",
}

LLMS_SECTION_HINTS = (
    ("site", re.compile(r"^#{1,3}\s*(site|website|sito)\b", re.I | re.M)),
    ("summary", re.compile(r"^#{1,3}\s*(summary|overview|about|chi siamo)\b", re.I | re.M)),
    ("topics", re.compile(r"^#{1,3}\s*(key topics?|topics?|argomenti)\b", re.I | re.M)),
    ("pages", re.compile(r"^#{1,3}\s*(important pages?|pages?|pagine|links?)\b", re.I | re.M)),
    ("citation", re.compile(r"^#{1,3}\s*(preferred citation|citation|citazione)\b", re.I | re.M)),
    ("contact", re.compile(r"^#{1,3}\s*(contact|contatti)\b", re.I | re.M)),
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_type(raw: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(raw):
        if isinstance(item, str):
            name = item.split("/")[-1].strip()
            if name:
                out.append(name)
    return out


def _walk_jsonld(node: Any, found: list[dict[str, Any]]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, found)
        return
    if not isinstance(node, dict):
        return
    types = _normalize_type(node.get("@type"))
    if types:
        found.append({"types": types, "node": node})
    graph = node.get("@graph")
    if graph is not None:
        _walk_jsonld(graph, found)
    # Alcuni payload annidano mainEntity
    for key in ("mainEntity", "hasPart", "about"):
        if key in node:
            _walk_jsonld(node[key], found)


def parse_json_ld_scripts(scripts_text: list[str]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    types: list[str] = []
    parse_errors = 0
    for raw in scripts_text:
        text = (raw or "").strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        local: list[dict[str, Any]] = []
        _walk_jsonld(data, local)
        blocks.extend(local)
        for item in local:
            types.extend(item["types"])

    uniq: list[str] = []
    seen: set[str] = set()
    for t in types:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    faq_blocks = [b for b in blocks if "FAQPage" in b["types"]]
    faq_questions = 0
    for block in faq_blocks:
        ents = _as_list(block["node"].get("mainEntity"))
        faq_questions += len(ents)

    org_nodes = [
        b["node"]
        for b in blocks
        if any(t in {"Organization", "LocalBusiness"} for t in b["types"])
    ][:5]

    return {
        "types": uniq,
        "block_count": len(blocks),
        "parse_errors": parse_errors,
        "has_faq_page": bool(faq_blocks),
        "faq_questions": faq_questions,
        "has_organization": any(t in {"Organization", "LocalBusiness"} for t in uniq),
        "has_website": "WebSite" in uniq,
        "valuable_types": [t for t in uniq if t in VALUABLE_TYPES],
        "org_nodes": org_nodes,
        "typed_nodes": [
            {
                "types": b["types"],
                "keys": sorted(str(k) for k in (b["node"] or {}).keys())[:24],
                "name": (b["node"] or {}).get("name")
                if isinstance((b["node"] or {}).get("name"), str)
                else None,
                "has_steps": bool((b["node"] or {}).get("step")),
                "has_offers": bool((b["node"] or {}).get("offers")),
                "has_aggregate": bool((b["node"] or {}).get("aggregateRating")),
                "has_review": bool((b["node"] or {}).get("review")),
                "has_transcript": bool(
                    (b["node"] or {}).get("transcript")
                    or (b["node"] or {}).get("caption")
                ),
                "has_speakable": bool((b["node"] or {}).get("speakable")),
                "has_author": bool((b["node"] or {}).get("author")),
                "has_date": bool(
                    (b["node"] or {}).get("datePublished")
                    or (b["node"] or {}).get("dateModified")
                ),
            }
            for b in blocks[:40]
        ],
        "has_article": any(
            t in {"Article", "NewsArticle", "BlogPosting"} for t in uniq
        ),
    }


def extract_json_ld_from_soup(soup: Any) -> dict[str, Any]:
    texts: list[str] = []
    for script in soup.find_all(
        "script", attrs={"type": re.compile(r"application/ld\+json", re.I)}
    ):
        content = script.string if script.string is not None else script.get_text()
        if content:
            texts.append(str(content))
    return parse_json_ld_scripts(texts)


def detect_html_faq(soup: Any, body_text: str = "") -> dict[str, Any]:
    """Segnali FAQ in HTML (oltre a FAQPage JSON-LD)."""
    details_q = 0
    for det in soup.find_all("details"):
        summary = det.find("summary")
        if summary and summary.get_text(strip=True):
            details_q += 1

    class_hits = soup.find_all(
        class_=re.compile(r"(faq|accordion|question)", re.I)
    )
    text = body_text or ""
    q_marks = len(re.findall(r"\?", text[:4000]))
    return {
        "details_questions": details_q,
        "class_hits": len(class_hits),
        "question_marks": q_marks,
        "html_faq_likely": details_q >= 2 or (len(class_hits) >= 2 and q_marks >= 3),
    }


def analyze_json_ld_types(meta: dict[str, Any]) -> dict[str, Any]:
    """Ritorna delta score + findings per JSON-LD tipizzato."""
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    types = meta.get("types") or []
    valuable = meta.get("valuable_types") or []

    if not types and not meta.get("block_count"):
        findings.append(
            {
                "category": "aio",
                "severity": "critical",
                "title": "Manca JSON-LD",
                "detail": "Aggiungi Schema.org tipizzato (Organization/WebSite come minimo).",
            }
        )
        return {"aio": aio, "geo": geo, "findings": findings}

    if meta.get("parse_errors"):
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "JSON-LD non valido",
                "detail": f"{meta['parse_errors']} blocco/i non parsabile/i: verifica la sintassi JSON.",
            }
        )

    if valuable:
        aio += 12
        geo += 8
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "JSON-LD tipizzato",
                "detail": "Tipi: " + ", ".join(valuable[:8]),
            }
        )
    elif types:
        aio += 6
        geo += 4
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "JSON-LD generico",
                "detail": "Trovato JSON-LD ma senza tipi chiave (Organization, WebSite, FAQPage…).",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "critical",
                "title": "JSON-LD senza @type",
                "detail": "I blocchi non espongono tipi Schema.org utilizzabili.",
            }
        )

    if meta.get("has_organization"):
        aio += 4
        geo += 3
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "Organization/LocalBusiness",
                "detail": "Entità brand strutturata rilevata.",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Manca Organization",
                "detail": "Aggiungi JSON-LD Organization (o LocalBusiness) con name e url.",
            }
        )

    if meta.get("has_website"):
        geo += 3
        findings.append(
            {
                "category": "geo",
                "severity": "ok",
                "title": "WebSite schema",
                "detail": "Utile per sitelink e interpretazione del dominio.",
            }
        )
    else:
        findings.append(
            {
                "category": "geo",
                "severity": "warn",
                "title": "Manca WebSite schema",
                "detail": "Aggiungi @type WebSite collegato all’Organization.",
            }
        )

    return {"aio": aio, "geo": geo, "findings": findings}


def analyze_faq_signals(jsonld_meta: dict[str, Any], html_faq: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0

    if jsonld_meta.get("has_faq_page"):
        n = int(jsonld_meta.get("faq_questions") or 0)
        aio += 8
        geo += 6
        detail = "FAQPage presente"
        if n:
            detail += f" con {n} domande"
        detail += "."
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "FAQ schema",
                "detail": detail,
            }
        )
        if n and n < 2:
            findings.append(
                {
                    "category": "aio",
                    "severity": "warn",
                    "title": "FAQPage troppo corta",
                    "detail": "Aggiungi almeno 2–3 Question/Answer in mainEntity.",
                }
            )
    elif html_faq.get("html_faq_likely"):
        aio += 2
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "FAQ in HTML senza schema",
                "detail": "Sembra esserci una FAQ visiva: aggiungi JSON-LD FAQPage per AIO.",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "FAQ schema assente",
                "detail": "Una FAQPage con Q&A tipizzate aiuta answer engine e snippet.",
            }
        )

    return {"aio": aio, "geo": geo, "findings": findings}


def _bot_policy(robots_text: str, bot: str) -> str:
    """allow | block | default | missing"""
    text = robots_text or ""
    if not text.strip():
        return "missing"

    # Spezza per blocchi User-agent
    blocks = re.split(r"(?i)\n\s*user-agent\s*:", "\n" + text)
    specific = None
    star = None
    for block in blocks[1:]:
        lines = block.splitlines()
        if not lines:
            continue
        agent = lines[0].split("#", 1)[0].strip()
        body = "\n".join(lines[1:])
        disallow_all = bool(re.search(r"(?im)^\s*disallow\s*:\s*/\s*$", body))
        allow_root = bool(re.search(r"(?im)^\s*allow\s*:\s*/\s*$", body))
        status = "block" if disallow_all and not allow_root else "allow"
        if agent == "*":
            star = status
        if agent.lower() == bot.lower():
            specific = status

    if specific:
        return specific
    if star:
        return "default"
    # File esiste ma senza regole chiare per il bot
    return "default"


def analyze_robots_bots(robots_text: str, *, robots_ok: bool) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0

    if not robots_ok:
        findings.append(
            {
                "category": "technical",
                "severity": "warn",
                "title": "robots.txt assente o non raggiungibile",
                "detail": "Pubblica policy esplicite per GPTBot, ClaudeBot, PerplexityBot, Google-Extended.",
            }
        )
        return {"aio": aio, "geo": geo, "findings": findings, "policies": {}}

    policies = {bot: _bot_policy(robots_text, bot) for bot in AI_BOTS}
    blocked = [b for b, s in policies.items() if s == "block"]
    allowed = [b for b, s in policies.items() if s in {"allow", "default"}]
    explicit = [
        b
        for b in AI_BOTS
        if re.search(rf"(?im)^\s*user-agent\s*:\s*{re.escape(b)}\s*$", robots_text or "")
    ]

    geo += 5
    findings.append(
        {
            "category": "technical",
            "severity": "ok",
            "title": "robots.txt raggiungibile",
            "detail": "File root leggibile per crawler e bot AI.",
        }
    )

    if blocked:
        aio -= 12
        geo -= 10
        findings.append(
            {
                "category": "technical",
                "severity": "critical",
                "title": "Bot AI bloccati",
                "detail": "Disallow per: " + ", ".join(blocked),
            }
        )
    else:
        aio += 4
        geo += 3

    if len(explicit) >= 3:
        aio += 5
        geo += 4
        findings.append(
            {
                "category": "technical",
                "severity": "ok",
                "title": "Policy bot AI esplicite",
                "detail": "Dichiarati: " + ", ".join(explicit),
            }
        )
    elif not blocked:
        findings.append(
            {
                "category": "technical",
                "severity": "warn",
                "title": "Policy bot AI implicite",
                "detail": "Aggiungi blocchi User-agent dedicati (GPTBot, ClaudeBot, PerplexityBot, Google-Extended) con Allow: /.",
            }
        )

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "policies": policies,
        "allowed": allowed,
        "blocked": blocked,
        "explicit": explicit,
    }


def analyze_llms_txt(content: str, *, present: bool) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    aio = 0.0
    geo = 0.0
    text = (content or "").strip()

    if not present or not text:
        findings.append(
            {
                "category": "aio",
                "severity": "critical",
                "title": "llms.txt assente",
                "detail": "Crea /llms.txt per guidare crawler e agenti AI sul tuo contenuto.",
            }
        )
        return {
            "aio": aio,
            "geo": geo,
            "findings": findings,
            "quality": 0,
            "sections": [],
            "link_count": 0,
        }

    sections = [name for name, pattern in LLMS_SECTION_HINTS if pattern.search(text)]
    links = re.findall(r"https?://[^\s\)\]\>]+", text)
    has_h1 = bool(re.search(r"^#\s+\S+", text, re.M))
    length = len(text)
    quality = 20
    if has_h1:
        quality += 15
    quality += min(40, len(sections) * 8)
    quality += min(15, len(links) * 3)
    if length >= 400:
        quality += 10
    elif length >= 180:
        quality += 5
    quality = max(0, min(100, quality))

    aio += 8
    geo += 4
    findings.append(
        {
            "category": "aio",
            "severity": "ok",
            "title": "llms.txt disponibile",
            "detail": f"Qualità stimata {quality}/100 · {len(sections)} sezioni utili · {len(links)} link.",
        }
    )

    if quality >= 70:
        aio += 8
        geo += 4
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "llms.txt di buona qualità",
                "detail": "Struttura e link sufficienti per orientare gli agenti.",
            }
        )
    elif quality >= 45:
        aio += 3
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "llms.txt migliorabile",
                "detail": "Aggiungi sezioni Site/Summary/Important pages/Preferred citation e link canonici.",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "critical",
                "title": "llms.txt povero",
                "detail": "File troppo corto o senza sezioni/link utili. Usa il pack GeoPulse come base.",
            }
        )

    if not has_h1:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "llms.txt senza titolo #",
                "detail": "Inizia con `# Brand` e una riga `> tagline`.",
            }
        )
    if len(links) < 2:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Pochi link in llms.txt",
                "detail": "Inserisci almeno homepage e 2–3 pagine chiave.",
            }
        )

    return {
        "aio": aio,
        "geo": geo,
        "findings": findings,
        "quality": quality,
        "sections": sections,
        "link_count": len(links),
    }


def compare_with_previous(
    *,
    aio_score: int | None,
    geo_score: int | None,
    findings: list[dict[str, Any]] | None,
    previous: Any | None,
) -> dict[str, Any]:
    """Confronta con AnalysisRun precedente dello stesso sito."""
    if previous is None:
        return {
            "has_previous": False,
            "findings": [],
            "delta_aio": None,
            "delta_geo": None,
            "improved": [],
            "regressed": [],
        }

    prev_aio = previous.aio_score
    prev_geo = previous.geo_score
    cur_aio = 0 if aio_score is None else int(aio_score)
    cur_geo = 0 if geo_score is None else int(geo_score)
    d_aio = cur_aio - (0 if prev_aio is None else int(prev_aio))
    d_geo = cur_geo - (0 if prev_geo is None else int(prev_geo))

    def titles(items: list[dict[str, Any]] | None, severity: str) -> set[str]:
        out: set[str] = set()
        for item in items or []:
            if str(item.get("severity") or "").lower() == severity:
                title = str(item.get("title") or "").strip()
                if title:
                    out.add(title)
        return out

    try:
        prev_findings = previous.findings if hasattr(previous, "findings") else []
    except Exception:
        prev_findings = []

    prev_crit = titles(prev_findings, "critical")
    cur_crit = titles(findings, "critical")
    resolved = sorted(prev_crit - cur_crit)
    new_crit = sorted(cur_crit - prev_crit)

    out_findings: list[dict[str, str]] = []
    if d_aio or d_geo:
        sign_aio = f"{d_aio:+d}" if d_aio else "0"
        sign_geo = f"{d_geo:+d}" if d_geo else "0"
        severity = "ok"
        if d_aio <= -5 or d_geo <= -5:
            severity = "critical"
        elif d_aio < 0 or d_geo < 0:
            severity = "warn"
        out_findings.append(
            {
                "category": "diff",
                "severity": severity,
                "title": "Confronto vs run precedente",
                "detail": (
                    f"AIO {sign_aio} ({prev_aio}→{cur_aio}), "
                    f"GEO {sign_geo} ({prev_geo}→{cur_geo})."
                ),
            }
        )
    else:
        out_findings.append(
            {
                "category": "diff",
                "severity": "ok",
                "title": "Score stabili vs run precedente",
                "detail": f"AIO {cur_aio}, GEO {cur_geo} invariati.",
            }
        )

    if resolved:
        out_findings.append(
            {
                "category": "diff",
                "severity": "ok",
                "title": f"Risolti {len(resolved)} critical",
                "detail": ", ".join(resolved[:4]),
            }
        )
    if new_crit:
        out_findings.append(
            {
                "category": "diff",
                "severity": "critical",
                "title": f"{len(new_crit)} nuovi critical",
                "detail": ", ".join(new_crit[:4]),
            }
        )

    return {
        "has_previous": True,
        "findings": out_findings,
        "delta_aio": d_aio,
        "delta_geo": d_geo,
        "previous_aio": prev_aio,
        "previous_geo": prev_geo,
        "improved": resolved,
        "regressed": new_crit,
        "previous_at": (
            previous.created_at.isoformat() if getattr(previous, "created_at", None) else None
        ),
    }


def origin_from_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
