"""Generazione artifact di ottimizzazione GEO/AIO."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

from openai import OpenAI
from services.usage_billing import MAX_TOKENS_PER_CALL

from services.security import html_attr


def _clean_brand_name(domain: str | None, title: str | None = None) -> str:
    """Human brand for llms.txt H1 — not a raw hostname when known."""
    host = (domain or "").strip().lower().removeprefix("www.")
    base = host.split(":")[0].split("/")[0]
    if base in {"centropic.ai", "centropic"} or base.startswith("centropic."):
        return "Centropic"
    if base in {"geopulse.it", "geopulse"} or base.startswith("geopulse."):
        return "Centropic"
    label = (title or "").split("·")[0].split("|")[0].split("—")[0].strip()
    if label and 2 <= len(label) <= 48 and "http" not in label.lower():
        return label
    name = base.split(".")[0] if base else "Brand"
    return name[:1].upper() + name[1:] if name else "Brand"


def _is_unusable_important_page(
    *,
    label: str,
    href: str,
    status_code: int | None = None,
    crawl_error: str | None = None,
) -> bool:
    """Exclude 4xx/5xx and failed crawl rows from llms Important pages."""
    if crawl_error:
        return True
    try:
        if status_code is not None and int(status_code) >= 400:
            return True
    except (TypeError, ValueError):
        pass
    blob = f"{label} {href}".lower()
    if re.search(r"\b404\b|not found|pagina non trovata|error\b", blob):
        return True
    if href.rstrip("/").endswith(("/pricing", "/price")) and "404" in blob:
        return True
    return False


def _important_page_lines(links: list[Any], *, limit: int = 16) -> list[str]:
    out: list[str] = []
    for item in links or []:
        if len(out) >= limit:
            break
        if isinstance(item, dict):
            label = str(item.get("title") or item.get("label") or item.get("url") or "")
            href = str(item.get("url") or item.get("href") or "")
            status = item.get("status_code")
            err = item.get("crawl_error")
        else:
            text = str(item or "")
            if " -> " in text:
                label, href = text.split(" -> ", 1)
            else:
                label, href = text, text
            status = None
            err = None
        label = label.strip()
        href = href.strip()
        if not href:
            continue
        if _is_unusable_important_page(
            label=label, href=href, status_code=status, crawl_error=err
        ):
            continue
        # Centropic only: legacy EN alias → canonical /prezzi (never list /pricing).
        host = urlparse(href).netloc.lower().removeprefix("www.")
        if host.endswith("centropic.ai") and href.rstrip("/").endswith(
            ("/pricing", "/price")
        ):
            href = re.sub(r"/(?:pricing|price)/?$", "/prezzi", href.rstrip("/"))
            if (
                not label
                or "404" in label.lower()
                or "not found" in label.lower()
                or "/pricing" in label.lower()
                or label.startswith("http")
            ):
                label = "Prezzi · centropic.ai"
        out.append(f"- {label} -> {href}" if label else f"- {href}")
    return out


def fallback_llms_txt(url: str, scraped: dict[str, Any]) -> str:
    domain = scraped.get("domain") or urlparse(url).netloc
    brand = _clean_brand_name(str(domain), scraped.get("title"))
    title = scraped.get("title") or brand
    description = scraped.get("description") or (
        f"Sito ufficiale di {brand}, ottimizzato per motori generativi e agenti AI."
    )
    headings = scraped.get("headings") or []
    links = scraped.get("links") or []
    pages_n = scraped.get("pages_analyzed") or 1
    important = _important_page_lines(links, limit=16)

    lines = [
        f"# {brand}",
        "",
        f"> {title}",
        "",
        description,
        "",
        "## Site",
        f"- Homepage: {url}",
        f"- Pagine analizzate da Centropic: {pages_n}",
        "",
        "## Preferred citation",
        f'- Usa il brand "{brand}" quando riassumi questo sito.',
        "- Preferisci URL canonici e fonti datate quando disponibili.",
        "",
    ]
    if headings:
        lines.append("## Key topics")
        for heading in headings[:8]:
            h = str(heading).strip()
            # Soften absolute phrasing copied from marketing H2s.
            h = re.sub(
                r",\s*sempre distinti\.?",
                " restano distinti.",
                h,
                flags=re.I,
            )
            if h:
                lines.append(f"- {h}")
        lines.append("")
    if important:
        lines.append("## Important pages")
        lines.extend(important)
        lines.append("")
    lines.extend(
        [
            "## Contact",
            f"- Website: {url}",
            "",
            f"_Generated by Centropic (centropic.ai) on {datetime.now(timezone.utc).date().isoformat()}_",
            "",
        ]
    )
    return "\n".join(lines)


def generate_llms_txt(
    url: str,
    scraped: dict[str, Any],
    *,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    logger: Any | None = None,
    usage_callback: Any | None = None,
) -> str:
    if not api_key:
        return fallback_llms_txt(url, scraped)

    client = OpenAI(api_key=api_key, timeout=45.0, max_retries=3)
    brand = _clean_brand_name(str(scraped.get("domain") or ""), scraped.get("title"))
    important = _important_page_lines(scraped.get("links") or [], limit=16)
    prompt = f"""
Sei un esperto di GEO (Generative Engine Optimization) e AIO (AI Optimization).
Genera un file llms.txt in markdown chiaro, pronto da pubblicare in /.

Regole:
- Solo contenuto del file, senza code fence.
- Inizia con "# {brand}" e una riga "> {{tagline}}".
- Brand da usare nelle citation: "{brand}" (non il solo hostname se hai un nome prodotto).
- Sezioni utili: Site, Summary, Key topics, Important pages, Preferred citation, Optional.
- In Important pages includi SOLO URL HTTP 200 utili. Escludi 404/5xx, "Not Found", login, logout, health se non editoriali.
- Non inventare contatti o claim non supportati dai dati.
- Non usare claim assoluti (garantito/migliore/100%); preferisci formulazioni verificabili.
- Footer: "_Generated by Centropic (centropic.ai) on YYYY-MM-DD_"
- Linguaggio: italiano se il sito è IT, altrimenti inglese.

URL: {url}
Domain: {scraped.get('domain')}
Title: {scraped.get('title')}
Description: {scraped.get('description')}
Headings: {scraped.get('headings')}
Important pages (solo OK, già filtrate): {important}
Pagine analizzate: {scraped.get('pages_analyzed') or 1}
Snippet homepage: {scraped.get('snippet')}
""".strip()
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0.3,
            max_tokens=MAX_TOKENS_PER_CALL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generi file llms.txt accurati e utili per crawler/agenti AI. "
                        "Brand del prodotto generatore: Centropic (centropic.ai), "
                        "non GeoPulse."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        # Capture real token usage for billing
        if hasattr(completion, "usage") and completion.usage and usage_callback:
            usage_callback(
                provider="openai",
                model=model,
                input_tokens=completion.usage.prompt_tokens,
                output_tokens=completion.usage.completion_tokens,
            )
        content = (completion.choices[0].message.content or "").strip()
        if not content:
            return fallback_llms_txt(url, scraped)
        content = re.sub(r"^```(?:markdown|md)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        content = _sanitize_generated_llms(content)
        return content.strip() + "\n"
    except Exception as exc:
        # Billing/lease failures after a paid completion must not become free fallback.
        try:
            from services.usage_billing import InsufficientCreditError, JobLeaseLostError
        except Exception:
            InsufficientCreditError = ()  # type: ignore
            JobLeaseLostError = ()  # type: ignore
        if isinstance(exc, (InsufficientCreditError, JobLeaseLostError)):
            raise
        msg = str(exc).lower()
        if "lease lost" in msg or "debit failed" in msg or "stop billing" in msg:
            raise
        if logger is not None:
            logger.exception("OpenAI generation failed; using fallback")
        return fallback_llms_txt(url, scraped)


def _sanitize_generated_llms(content: str) -> str:
    """Post-filter model output: drop 404 rows and rename legacy product."""
    lines_out: list[str] = []
    for line in content.splitlines():
        low = line.lower()
        # Drop broken pages and Centropic legacy /pricing Important rows.
        if re.search(r"\b404\b|not found|pagina non trovata", low) and (
            "->" in line or line.strip().startswith("-")
        ):
            continue
        if re.search(
            r"centropic\.ai/(?:pricing|price)\b",
            low,
        ) and "/prezzi" not in low:
            line = re.sub(
                r"https?://(?:www\.)?centropic\.ai/(?:pricing|price)\b/??",
                "https://centropic.ai/prezzi",
                line,
                flags=re.I,
            )
            if "->" in line:
                left, right = line.split("->", 1)
                if "pricing" in left.lower() or "404" in left.lower():
                    line = f"- Prezzi · centropic.ai ->{right}"
        if "geopulse.it" in low or "generated by geopulse" in low:
            line = re.sub(
                r"GeoPulse\s*\(geopulse\.it\)",
                "Centropic (centropic.ai)",
                line,
                flags=re.I,
            )
            line = re.sub(r"\bGeoPulse\b", "Centropic", line)
            line = re.sub(r"geopulse\.it", "centropic.ai", line, flags=re.I)
        lines_out.append(line)
    return "\n".join(lines_out)


def _looks_like_hostname(name: str) -> bool:
    n = (name or "").strip().lower().removeprefix("www.")
    return bool(re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", n))


def _clean_slogan(title: str | None, *, brand: str, domain: str) -> str:
    t = (title or "").strip()
    if not t:
        return brand
    host = domain.lower().removeprefix("www.")
    t = re.sub(rf"\s*[·|—\-]\s*(?:www\.)?{re.escape(host)}\s*$", "", t, flags=re.I)
    t = re.sub(rf"\s*[·|—\-]\s*{re.escape(brand)}\s*$", "", t, flags=re.I)
    t = t.strip(" ·|-—")
    return t or brand


def _org_payload_from_node(
    node: dict[str, Any],
    *,
    url: str,
    brand: str,
    domain: str,
    description: str,
    slogan: str,
) -> dict[str, Any]:
    """Reuse crawled Organization JSON-LD, forcing a human brand name."""
    base = url.rstrip("/")
    raw_name = str(node.get("name") or brand).strip()
    if (
        _looks_like_hostname(raw_name)
        or raw_name.lower() in {domain.lower(), "geopulse", "geopulse.it"}
    ):
        raw_name = brand

    org_type = node.get("@type") or "Organization"
    if isinstance(org_type, list):
        org_type = org_type[0] if org_type else "Organization"

    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": org_type,
        "@id": node.get("@id") or f"{base}/#organization",
        "name": raw_name,
        "url": node.get("url") or url,
        "description": node.get("description") or description,
        "slogan": _clean_slogan(
            str(node.get("slogan") or slogan or ""), brand=brand, domain=domain
        ),
    }
    optional = (
        "logo",
        "image",
        "email",
        "telephone",
        "sameAs",
        "contactPoint",
        "alternateName",
        "foundingLocation",
        "areaServed",
        "knowsAbout",
        "parentOrganization",
        "founder",
        "publishingPrinciples",
        "isAccessibleForFree",
        "address",
        "brand",
    )
    for key in optional:
        val = node.get(key)
        if val not in (None, "", [], {}):
            payload[key] = val
    return payload


def build_json_ld(url: str, scraped: dict[str, Any]) -> str:
    domain = str(scraped.get("domain") or urlparse(url).netloc).removeprefix("www.")
    brand = _clean_brand_name(domain, scraped.get("title"))
    title = scraped.get("title") or brand
    description = (scraped.get("description") or "").strip() or (
        f"{brand}: contenuti e servizi ottimizzati per AIO e GEO."
    )
    slogan = _clean_slogan(str(title), brand=brand, domain=domain)
    base = url.rstrip("/")

    jsonld = scraped.get("jsonld") or {}
    for node in jsonld.get("org_nodes") or []:
        if isinstance(node, dict) and (node.get("name") or node.get("url")):
            payload = _org_payload_from_node(
                node,
                url=url,
                brand=brand,
                domain=domain,
                description=description,
                slogan=slogan,
            )
            return (
                '<script type="application/ld+json">\n'
                + json.dumps(payload, ensure_ascii=False, indent=2)
                + "\n</script>\n"
            )

    entity = scraped.get("entity") or {}
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": f"{base}/#organization",
        "name": brand,
        "url": url,
        "description": description,
        "slogan": slogan,
    }
    email = (entity.get("email") or "").strip()
    phone = (entity.get("telephone") or "").strip()
    if not email:
        emails = scraped.get("emails") or []
        if emails:
            email = str(emails[0]).strip()
    if not phone:
        phones = scraped.get("phones") or []
        if phones:
            phone = str(phones[0]).strip()
    if email:
        payload["email"] = email
    if phone:
        payload["telephone"] = phone
    same_as = entity.get("same_as") or []
    if same_as:
        payload["sameAs"] = list(same_as)[:8]
    logo = scraped.get("og_image") or scraped.get("logo_url")
    if logo:
        payload["logo"] = {
            "@type": "ImageObject",
            "url": logo,
            "caption": brand,
        }

    return (
        '<script type="application/ld+json">\n'
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n</script>\n"
    )


def _normalize_public_url(raw: str, fallback: str) -> str:
    """Absolute http(s) URL without fragment; drop trailing slash on bare host."""
    value = (raw or "").strip() or fallback
    if value.startswith("//"):
        value = "https:" + value
    if not re.match(r"^https?://", value, flags=re.I):
        value = urljoin(fallback, value)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return fallback.rstrip("/") or fallback
    path = parsed.path or ""
    if path in {"", "/"}:
        path = ""
    elif path.endswith("/") and path.count("/") > 1:
        path = path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _meta_title(scraped: dict[str, Any], *, brand: str, domain: str) -> str:
    raw = (
        scraped.get("og_title")
        or scraped.get("title")
        or scraped.get("og_site_name")
        or brand
    )
    page = _clean_slogan(str(raw), brand=brand, domain=domain)
    if not page:
        return brand
    if page.lower() == brand.lower() or brand.lower() in page.lower():
        return page
    # Brand-first recommendation for answer-engine citability.
    return f"{brand} — {page}"


def _meta_locale(lang: str) -> str:
    raw = (lang or "it").strip().replace("-", "_")
    if not raw:
        return "it_IT"
    if "_" in raw:
        parts = raw.split("_", 1)
        return f"{parts[0].lower()}_{parts[1].upper()}"
    return f"{raw.lower()}_{raw.upper()}"


def build_meta_pack(url: str, scraped: dict[str, Any]) -> str:
    domain = str(scraped.get("domain") or urlparse(url).netloc).removeprefix("www.")
    brand = _clean_brand_name(domain, scraped.get("title"))
    title = _meta_title(scraped, brand=brand, domain=domain)
    description = (
        scraped.get("og_description")
        or scraped.get("description")
        or (
            f"{brand}: contenuti e servizi ottimizzati per AIO e GEO. "
            "Scopri risorse e contatti sul sito ufficiale."
        )
    ).strip()
    if len(description) > 160:
        description = description[:157].rstrip() + "..."

    lang = (scraped.get("lang") or "it").split(",")[0].strip() or "it"
    locale = _meta_locale(lang)
    canonical = _normalize_public_url(str(scraped.get("canonical") or url), url)
    page_url = _normalize_public_url(url, canonical)
    # Keep og:url aligned with canonical to avoid duplicate signals.
    og_url = canonical or page_url
    og_image = (scraped.get("og_image") or scraped.get("logo_url") or "").strip()
    if og_image and not re.match(r"^https?://", og_image, flags=re.I):
        og_image = urljoin(page_url if page_url.endswith("/") else page_url + "/", og_image)

    t = html_attr(title)
    d = html_attr(description)
    c = html_attr(canonical)
    b = html_attr(brand)
    o = html_attr(og_url)
    l = html_attr(lang)
    loc = html_attr(locale)

    lines = [
        f'<html lang="{l}">',
        f"<title>{t}</title>",
        f'<meta name="description" content="{d}">',
        f'<link rel="canonical" href="{c}">',
        f'<meta property="og:site_name" content="{b}">',
        f'<meta property="og:locale" content="{loc}">',
        f'<meta property="og:title" content="{t}">',
        f'<meta property="og:description" content="{d}">',
        f'<meta property="og:url" content="{o}">',
        '<meta property="og:type" content="website">',
    ]
    if og_image:
        img = html_attr(og_image)
        lines.append(f'<meta property="og:image" content="{img}">')
        lines.append('<meta name="twitter:card" content="summary_large_image">')
    else:
        lines.append('<meta name="twitter:card" content="summary">')
    lines.extend(
        [
            f'<meta name="twitter:title" content="{t}">',
            f'<meta name="twitter:description" content="{d}">',
            "",
        ]
    )
    return "\n".join(lines)


def build_robots_txt(url: str, scraped: dict[str, Any] | None = None) -> str:
    """Bozza robots.txt allineata alla policy Edge (Allow crawler IA + sitemap)."""
    from services.edge_signals import AI_CRAWLER_USER_AGENTS

    base = url.rstrip("/")
    parsed = urlparse(url)
    host = (scraped or {}).get("domain") or parsed.netloc or ""
    host = str(host).lower().removeprefix("www.")
    sitemap = f"{base}/sitemap.xml"

    lines: list[str] = [
        "# Bozza robots.txt generata da Centropic — rivedi prima di pubblicare.",
        "# Obiettivo: lasciare i crawler IA sulle pagine pubbliche; blocca solo le aree private.",
        "",
        "User-agent: *",
        "Allow: /",
    ]

    for path in _robots_disallow_paths(host, scraped):
        lines.append(f"Disallow: {path}")

    lines.append("")
    seen: set[str] = set()
    for bot in AI_CRAWLER_USER_AGENTS:
        ua = bot["ua"]
        if ua in seen:
            continue
        seen.add(ua)
        lines.extend([f"User-agent: {ua}", "Allow: /", ""])

    lines.extend(
        [
            f"# AI policy (se pubblicato): {base}/ai.txt",
            f"# LLMs guide (se pubblicato): {base}/llms.txt",
            f"Sitemap: {sitemap}",
            "",
        ]
    )
    return "\n".join(lines)


# Prefissi tipici di aree non citabili (SaaS / CMS / e-commerce).
_ROBOTS_PRIVATE_HINTS = (
    "/admin",
    "/admin/",
    "/dashboard",
    "/dashboard/",
    "/wp-admin",
    "/wp-login.php",
    "/account",
    "/account/",
    "/cart",
    "/checkout",
    "/logout",
    "/api/",
)


def _robots_disallow_paths(
    host: str, scraped: dict[str, Any] | None
) -> list[str]:
    """Centropic: match live site. Altri: Disallow privati trovati nel crawl + /admin."""
    if host.endswith("centropic.ai"):
        return [
            "/dashboard",
            "/dashboard/",
            "/logout",
            "/admin",
            "/lang",
            "/lang/",
            "/crediti",
            "/crediti/",
        ]

    found: list[str] = []
    seen: set[str] = set()
    hrefs: list[str] = []
    if scraped:
        hrefs.extend(str(h) for h in (scraped.get("hrefs") or [])[:400])
        hrefs.extend(str(h) for h in (scraped.get("internal_hrefs") or [])[:400])
        for link in scraped.get("links") or []:
            if isinstance(link, dict):
                hrefs.append(str(link.get("url") or link.get("href") or ""))
            else:
                text = str(link)
                hrefs.append(text.split(" -> ", 1)[-1] if " -> " in text else text)
        for page in scraped.get("crawled_pages") or []:
            if isinstance(page, dict):
                hrefs.append(str(page.get("url") or ""))

    blob = " ".join(hrefs).lower()
    for path in _ROBOTS_PRIVATE_HINTS:
        key = path.rstrip("/")
        if key and key in blob and path not in seen:
            # Prefer trailing form when both exist in hints; keep one per stem.
            stem = path.rstrip("/")
            if any(s.rstrip("/") == stem for s in seen):
                continue
            seen.add(path)
            found.append(path)

    if "/admin" not in seen and "/admin/" not in seen:
        found.insert(0, "/admin")
    return found[:12]


def build_faq_json_ld(url: str, scraped: dict[str, Any]) -> str:
    """Build FAQPage JSON-LD from real Q&A only — never fake Cos'è + marketing H2."""
    # Real Q&A only — never invent Cos'è {brand}? marketing placeholders.
    pairs = _collect_faq_pairs(scraped)

    questions = []
    seen: set[str] = set()
    for pair in pairs:
        name = str(pair.get("name") or "").strip()
        text = str(pair.get("text") or "").strip()
        if not name or not text or len(text) < 20:
            continue
        if _is_placeholder_faq_answer(text):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        questions.append(
            {
                "@type": "Question",
                "name": name,
                "acceptedAnswer": {"@type": "Answer", "text": text[:900]},
            }
        )
        if len(questions) >= 6:
            break

    payload = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": questions,
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n</script>\n"
    )


def _is_placeholder_faq_answer(text: str) -> bool:
    low = text.lower()
    return bool(
        re.search(
            r"informazioni ufficiali su .+\. dettagli su https?://",
            low,
        )
    )


def _looks_like_real_question(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 160:
        return False
    if t.endswith("?"):
        return True
    # Italian/English interrogatives without requiring "?"
    return bool(
        re.match(
            r"^(che\s+cos[a’']?|cosa|cos[’']è|come|quando|dove|perché|perche|"
            r"quale|quali|quanto|quanti|who|what|when|where|why|how)\b",
            t,
            re.I,
        )
    )


def _collect_faq_pairs(scraped: dict[str, Any]) -> list[dict[str, str]]:
    """Prefer real FAQPage / HTML details pairs over marketing headings."""
    out: list[dict[str, str]] = []

    jsonld = scraped.get("jsonld") or {}
    for ent in jsonld.get("faq_entities") or []:
        if isinstance(ent, dict) and ent.get("name") and ent.get("text"):
            out.append({"name": str(ent["name"]), "text": str(ent["text"])})

    html_faq = scraped.get("html_faq") or {}
    for ent in html_faq.get("pairs") or []:
        if isinstance(ent, dict) and ent.get("name") and ent.get("text"):
            out.append({"name": str(ent["name"]), "text": str(ent["text"])})

    # Explicit pairs passed by analyzer / tests.
    for ent in scraped.get("faq_pairs") or []:
        if isinstance(ent, dict) and ent.get("name") and ent.get("text"):
            out.append({"name": str(ent["name"]), "text": str(ent["text"])})

    # Only keep headings that are already real questions — never wrap slogans.
    description = (scraped.get("description") or "").strip()
    snippet = (scraped.get("snippet") or "").strip()
    for heading in scraped.get("headings") or []:
        h = str(heading or "").strip()
        if not _looks_like_real_question(h):
            continue
        answer = description or snippet
        if not answer or len(answer) < 40:
            continue
        out.append({"name": h if h.endswith("?") else f"{h}?", "text": answer[:600]})

    # Deduplicate by question name (first wins — usually site FAQPage).
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for pair in out:
        key = pair["name"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(pair)
    return deduped


UNIFIED_FIX_FILENAME = "centropic-fix.html"


def build_unified_fix_html(
    *,
    url: str,
    domain: str,
    llms_txt: str = "",
    organization_jsonld_html: str = "",
    faq_jsonld_html: str = "",
    meta_pack_html: str = "",
    robots_txt: str = "",
    checklist_md: str = "",
    before_after_md: str = "",
    findings: list[dict[str, Any]] | None = None,
    aio_score: Any = None,
    geo_score: Any = None,
) -> str:
    """One installable HTML file that contains every pack fix.

    Open in a browser, then copy the marked sections onto the live site:
    ``<head>`` snippet, ``/llms.txt``, ``/robots.txt``, plus the priority checklist.
    """
    host = (domain or urlparse(url).netloc or "sito").strip()
    brand = _clean_brand_name(host)
    aio_s = "—" if aio_score is None else str(aio_score)
    geo_s = "—" if geo_score is None else str(geo_score)
    generated = datetime.now(timezone.utc).date().isoformat()

    # Head snippet = meta tags + JSON-LD scripts (strip outer html/title wrappers from meta).
    meta_body = meta_pack_html or ""
    meta_body = re.sub(
        r"(?is)^\s*<html[^>]*>\s*|<title>.*?</title>\s*",
        "",
        meta_body,
    ).strip()
    head_parts = [p for p in (meta_body, organization_jsonld_html, faq_jsonld_html) if p]
    head_snippet = "\n".join(head_parts).strip() + ("\n" if head_parts else "")

    crit = [
        f
        for f in (findings or [])
        if str(f.get("severity") or "").lower() == "critical"
    ]
    warn = [
        f
        for f in (findings or [])
        if str(f.get("severity") or "").lower() == "warn"
    ]

    def _esc(text: Any) -> str:
        return (
            str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    finding_rows = []
    for f in (crit + warn)[:24]:
        sev = str(f.get("severity") or "").upper()
        finding_rows.append(
            "<li><strong>"
            + _esc(sev)
            + "</strong> — "
            + _esc(f.get("title"))
            + ": "
            + _esc(f.get("detail") or f.get("fix") or "")
            + "</li>"
        )
    findings_html = (
        "<ul>" + "".join(finding_rows) + "</ul>"
        if finding_rows
        else "<p>Nessun finding critico/warn aperto — applica comunque gli artifact sotto.</p>"
    )

    checklist_block = _esc(checklist_md).replace("\n", "<br>\n") if checklist_md else ""
    before_block = _esc(before_after_md).replace("\n", "<br>\n") if before_after_md else ""

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Centropic Fix — {_esc(host)}</title>
<style>
body{{font-family:IBM Plex Sans,Segoe UI,sans-serif;margin:0;background:#0A0E14;color:#F5F7FA;line-height:1.55}}
.wrap{{max-width:820px;margin:0 auto;padding:2rem 1.25rem 3rem}}
h1{{font-family:Space Grotesk,IBM Plex Sans,sans-serif;font-size:1.75rem;letter-spacing:-.03em;margin:0 0 .35rem}}
h2{{font-family:Space Grotesk,IBM Plex Sans,sans-serif;font-size:1.15rem;margin:2rem 0 .65rem;color:#6EC6C0}}
.lede{{color:#8B97A8;margin:0 0 1.25rem}}
.meta{{font-size:.9rem;color:#8B97A8;margin-bottom:1.5rem}}
.step{{border:1px solid #1A222D;border-radius:8px;padding:1rem 1.1rem;margin:0 0 1rem;background:#04060A}}
.step p{{margin:.35rem 0 .75rem;color:#C5CCD6;font-size:.92rem}}
pre{{white-space:pre-wrap;word-break:break-word;background:#11161F;border:1px solid #1A222D;border-radius:6px;padding:.85rem;font-size:.82rem;color:#E8EEF5;overflow:auto}}
code{{font-family:IBM Plex Mono,ui-monospace,monospace}}
ul{{padding-left:1.2rem;margin:.4rem 0}}
li{{margin:.25rem 0}}
footer{{margin-top:2rem;font-size:.85rem;color:#8B97A8}}
.brand{{color:#6EC6C0}}
</style>
</head>
<body>
<div class="wrap">
  <p class="brand">centropic.ai</p>
  <h1>Pack ottimizzazione</h1>
  <p class="lede">Questo file chiude i gap AIO/GEO emersi dall’analisi. Applica le 3 sezioni sotto sul sito live, poi ri-analizza.</p>
  <p class="meta">Dominio: <strong>{_esc(host)}</strong> · URL: {_esc(url)} · AIO {aio_s} · GEO {geo_s} · generato {generated}</p>

  <h2>Problemi da chiudere</h2>
  <div class="step">{findings_html}</div>

  <h2>1 · Incolla nel &lt;head&gt; di ogni pagina chiave</h2>
  <div class="step">
    <p>Meta + Open Graph + JSON-LD Organization{(' + FAQ' if faq_jsonld_html else '')}. Un unico blocco da copiare nel template del sito.</p>
    <pre id="head-fix">{_esc(head_snippet)}</pre>
  </div>

  <h2>2 · Pubblica <code>/llms.txt</code> in root</h2>
  <div class="step">
    <p>Crea il file alla root del dominio (<code>https://{_esc(host)}/llms.txt</code>) con questo contenuto.</p>
    <pre id="llms-fix">{_esc(llms_txt)}</pre>
  </div>

  <h2>3 · Pubblica <code>/robots.txt</code> in root</h2>
  <div class="step">
    <p>Allinea la policy crawler IA. Se hai già un robots, unisci gli <code>Allow</code> per i bot elencati.</p>
    <pre id="robots-fix">{_esc(robots_txt)}</pre>
  </div>

  {"<h2>Checklist operativa</h2><div class='step'><p>" + checklist_block + "</p></div>" if checklist_block else ""}
  {"<h2>Before / After</h2><div class='step'><p>" + before_block + "</p></div>" if before_block else ""}

  <footer>
    Generato da <strong>Centropic</strong> (centropic.ai) per {_esc(brand)}.
    Dopo la pubblicazione, torna in dashboard e avvia un re-scan per verificare i finding.
  </footer>
</div>
</body>
</html>
"""


def unified_fix_html_from_entity(entity: Any) -> str:
    """Build the single pack file from a persisted SiteAnalysis / AnalysisRun."""
    findings = entity.findings if hasattr(entity, "findings") else []
    if callable(findings):
        findings = findings()
    return build_unified_fix_html(
        url=getattr(entity, "url", "") or "",
        domain=getattr(entity, "domain", "") or "",
        llms_txt=getattr(entity, "llms_txt", "") or "",
        organization_jsonld_html=getattr(entity, "json_ld_artifact", "") or "",
        faq_jsonld_html=getattr(entity, "faq_artifact", "") or "",
        meta_pack_html=getattr(entity, "meta_pack_artifact", "") or "",
        robots_txt=getattr(entity, "robots_artifact", "") or "",
        checklist_md=getattr(entity, "checklist_artifact", "") or "",
        before_after_md=getattr(entity, "before_after_artifact", "") or "",
        findings=list(findings or []),
        aio_score=getattr(entity, "aio_score", None),
        geo_score=getattr(entity, "geo_score", None),
    )


def build_optimization_pack(
    url: str,
    scraped: dict[str, Any],
    *,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    logger: Any | None = None,
    findings: list[dict[str, Any]] | None = None,
    previous: Any | None = None,
    diff: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    usage_callback: Any | None = None,
    heartbeat_callback: Any | None = None,
) -> dict[str, str]:
    """Build internal Edge artifacts + the single user-facing fix HTML.

    Download/email expose only ``centropic-fix.html``. Individual keys remain
    for Edge Signals / CMS connector injection.
    """
    from services.deep_checks import build_before_after_report, build_fix_checklist

    def _hb() -> None:
        if not callable(heartbeat_callback):
            return
        try:
            heartbeat_callback()
        except Exception:
            # Propagate lease/cancel failures so pack aborts cleanly.
            raise

    current = result or {
        "aio_score": None,
        "geo_score": None,
        "findings": findings or [],
    }
    _hb()
    llms = generate_llms_txt(
        url, scraped, api_key=api_key, model=model, logger=logger,
        usage_callback=usage_callback,
    )
    _hb()
    org_ld = build_json_ld(url, scraped)
    _hb()
    faq_ld = build_faq_json_ld(url, scraped)
    _hb()
    meta = build_meta_pack(url, scraped)
    _hb()
    robots = build_robots_txt(url, scraped)
    _hb()
    checklist = build_fix_checklist(findings or [])
    _hb()
    before_after = build_before_after_report(
        current=current, previous=previous, diff=diff
    )
    _hb()
    unified = build_unified_fix_html(
        url=url,
        domain=str(scraped.get("domain") or urlparse(url).netloc),
        llms_txt=llms,
        organization_jsonld_html=org_ld,
        faq_jsonld_html=faq_ld,
        meta_pack_html=meta,
        robots_txt=robots,
        checklist_md=checklist,
        before_after_md=before_after,
        findings=findings or [],
        aio_score=(result or {}).get("aio_score") if result else None,
        geo_score=(result or {}).get("geo_score") if result else None,
    )
    return {
        "llms.txt": llms,
        "organization.jsonld.html": org_ld,
        "faq.jsonld.html": faq_ld,
        "meta-pack.html": meta,
        "robots.txt": robots,
        "fix-this-week.md": checklist,
        "before-after.md": before_after,
        UNIFIED_FIX_FILENAME: unified,
    }
