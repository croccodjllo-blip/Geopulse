"""Generazione artifact di ottimizzazione GEO/AIO."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

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
    except Exception:
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


def build_json_ld(url: str, scraped: dict[str, Any]) -> str:
    domain = scraped.get("domain") or urlparse(url).netloc
    brand = _clean_brand_name(str(domain), scraped.get("title"))
    title = scraped.get("title") or brand
    description = scraped.get("description") or (
        f"{brand}: contenuti e servizi ottimizzati per AIO e GEO."
    )
    payload = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand,
        "url": url,
        "description": description,
        "slogan": title,
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n</script>\n"
    )


def build_meta_pack(url: str, scraped: dict[str, Any]) -> str:
    brand = (scraped.get("domain") or urlparse(url).netloc).replace("www.", "")
    title = scraped.get("title") or f"{brand} — Official site"
    description = scraped.get("description") or (
        f"{brand}: contenuti e servizi ottimizzati per AIO e GEO. "
        "Scopri risorse e contatti sul sito ufficiale."
    )
    if len(description) > 160:
        description = description[:157].rstrip() + "..."
    lang = scraped.get("lang") or "it"
    canonical = scraped.get("canonical") or url
    t = html_attr(title)
    d = html_attr(description)
    c = html_attr(canonical)
    u = html_attr(url)
    l = html_attr(lang)
    return "\n".join(
        [
            f"<title>{t}</title>",
            f'<meta name="description" content="{d}">',
            f'<link rel="canonical" href="{c}">',
            f'<meta property="og:title" content="{t}">',
            f'<meta property="og:description" content="{d}">',
            f'<meta property="og:url" content="{u}">',
            '<meta property="og:type" content="website">',
            f"<!-- Assicurati che <html lang=\"{l}\"> sia impostato -->",
            "",
        ]
    )


def build_robots_txt(url: str) -> str:
    sitemap = url.rstrip("/") + "/sitemap.xml"
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "",
            "User-agent: GPTBot",
            "Allow: /",
            "",
            "User-agent: ClaudeBot",
            "Allow: /",
            "",
            "User-agent: PerplexityBot",
            "Allow: /",
            "",
            "User-agent: Google-Extended",
            "Allow: /",
            "",
            "User-agent: Applebot-Extended",
            "Allow: /",
            "",
            "# Disallow: /admin",
            "# Disallow: /app",
            "",
            f"Sitemap: {sitemap}",
            "",
        ]
    )


def build_faq_json_ld(url: str, scraped: dict[str, Any]) -> str:
    brand = (scraped.get("domain") or urlparse(url).netloc).replace("www.", "")
    headings = [h for h in (scraped.get("headings") or []) if h][:4]
    questions = []
    if headings:
        for heading in headings:
            questions.append(
                {
                    "@type": "Question",
                    "name": heading if heading.endswith("?") else f"Cos’è {heading}?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            f"{heading}: informazioni ufficiali su {brand}. "
                            f"Dettagli su {url}."
                        ),
                    },
                }
            )
    else:
        questions = [
            {
                "@type": "Question",
                "name": f"Cos’è {brand}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": (
                        scraped.get("description")
                        or f"{brand} è il sito ufficiale. Visita {url}."
                    ),
                },
            },
            {
                "@type": "Question",
                "name": f"Dove trovo maggiori informazioni su {brand}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Consulta il sito ufficiale: {url}",
                },
            },
        ]
    payload = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": questions[:6],
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n</script>\n"
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
) -> dict[str, str]:
    from services.deep_checks import build_before_after_report, build_fix_checklist

    current = result or {
        "aio_score": None,
        "geo_score": None,
        "findings": findings or [],
    }
    return {
        "llms.txt": generate_llms_txt(
            url, scraped, api_key=api_key, model=model, logger=logger,
            usage_callback=usage_callback,
        ),
        "organization.jsonld.html": build_json_ld(url, scraped),
        "faq.jsonld.html": build_faq_json_ld(url, scraped),
        "meta-pack.html": build_meta_pack(url, scraped),
        "robots.txt": build_robots_txt(url),
        "fix-this-week.md": build_fix_checklist(findings or []),
        "before-after.md": build_before_after_report(
            current=current, previous=previous, diff=diff
        ),
    }
