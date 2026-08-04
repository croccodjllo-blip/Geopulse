"""
Hosting dinamico segnali AIO/GEO (CDN / Edge ready).

Espone payload versionati e snippet Worker/embed che aggiornano
robots / llms / JSON-LD / signals.json senza ridistribuire ZIP statici.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

# User-Agent tipici dei crawler AI (lista viva — aggiornabile lato server).
# I Worker / endpoint Edge la ripubblicano via signals.json.
AI_CRAWLER_USER_AGENTS: list[dict[str, str]] = [
    {"name": "GPTBot", "vendor": "OpenAI", "ua": "GPTBot", "purpose": "training+retrieval"},
    {"name": "ChatGPT-User", "vendor": "OpenAI", "ua": "ChatGPT-User", "purpose": "retrieval"},
    {"name": "OAI-SearchBot", "vendor": "OpenAI", "ua": "OAI-SearchBot", "purpose": "search"},
    {"name": "ClaudeBot", "vendor": "Anthropic", "ua": "ClaudeBot", "purpose": "training+retrieval"},
    {"name": "anthropic-ai", "vendor": "Anthropic", "ua": "anthropic-ai", "purpose": "training"},
    {"name": "PerplexityBot", "vendor": "Perplexity", "ua": "PerplexityBot", "purpose": "search"},
    {"name": "Google-Extended", "vendor": "Google", "ua": "Google-Extended", "purpose": "training"},
    {"name": "GoogleOther", "vendor": "Google", "ua": "GoogleOther", "purpose": "misc"},
    {"name": "Bytespider", "vendor": "ByteDance", "ua": "Bytespider", "purpose": "training"},
    {"name": "CCBot", "vendor": "Common Crawl", "ua": "CCBot", "purpose": "training"},
    {"name": "meta-externalagent", "vendor": "Meta", "ua": "meta-externalagent", "purpose": "training"},
    {"name": "Applebot-Extended", "vendor": "Apple", "ua": "Applebot-Extended", "purpose": "training"},
    {"name": "Amazonbot", "vendor": "Amazon", "ua": "Amazonbot", "purpose": "search"},
    {"name": "cohere-ai", "vendor": "Cohere", "ua": "cohere-ai", "purpose": "training"},
    {"name": "Diffbot", "vendor": "Diffbot", "ua": "Diffbot", "purpose": "extraction"},
    {"name": "YouBot", "vendor": "You.com", "ua": "YouBot", "purpose": "search"},
]

# Private/short TTL: plan downgrades must not keep serving Plus bodies via CDN.
CACHE_CONTROL = "private, max-age=60"


def new_public_token() -> str:
    return secrets.token_urlsafe(18)


def edge_base_url(public_base: str, token: str) -> str:
    return f"{public_base.rstrip('/')}/e/{token}"


def content_etag(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def is_ai_crawler(user_agent: str | None) -> bool:
    ua = (user_agent or "").lower()
    if not ua:
        return False
    return any(bot["ua"].lower() in ua for bot in AI_CRAWLER_USER_AGENTS)


def analysis_brand(analysis: Any) -> str:
    domain = getattr(analysis, "domain", None) or ""
    title = getattr(analysis, "page_title", None) or ""
    if domain:
        return str(domain).replace("www.", "")
    if title:
        return str(title)[:80]
    parsed = urlparse(getattr(analysis, "url", "") or "")
    return parsed.netloc or "site"


def citation_potential_of(analysis: Any) -> float:
    """Estrae citation_potential da colonna o blob signals, se presente."""
    direct = getattr(analysis, "citation_potential", None)
    if direct is not None:
        try:
            return float(direct)
        except (TypeError, ValueError):
            pass
    signals = getattr(analysis, "signals", None)
    if isinstance(signals, dict):
        for key in ("citation_potential", "citability", "citation"):
            if key in signals:
                try:
                    return float(signals[key] or 0)
                except (TypeError, ValueError):
                    continue
    return 0.0


def build_live_robots_txt(site_url: str) -> str:
    """robots.txt dinamico: Allow per ogni crawler IA noto + sitemap."""
    sitemap = site_url.rstrip("/") + "/sitemap.xml"
    lines = [
        "# Centropic Edge Signals — AI crawler policy (live)",
        "# Aggiornato server-side quando la lista crawler cambia.",
        "",
        "User-agent: *",
        "Allow: /",
        "",
    ]
    seen: set[str] = set()
    for bot in AI_CRAWLER_USER_AGENTS:
        ua = bot["ua"]
        if ua in seen:
            continue
        seen.add(ua)
        lines.extend([f"User-agent: {ua}", "Allow: /", ""])
    lines.extend([f"Sitemap: {sitemap}", ""])
    return "\n".join(lines)


def extract_jsonld_body(artifact: str) -> str:
    """Estrae JSON da script ld+json o restituisce il testo grezzo."""
    text = (artifact or "").strip()
    if not text:
        return "{}"
    match = re.search(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    if text.startswith("{") or text.startswith("["):
        return text
    return text


def build_signals_payload(
    *,
    analysis: Any,
    public_base: str,
    token: str,
    version: int,
    full: bool = True,
) -> dict[str, Any]:
    """Manifest Edge: URL artifact + lista crawler + meta AIO/GEO."""
    base = edge_base_url(public_base, token)
    brand = analysis_brand(analysis)
    site = getattr(analysis, "domain", None) or urlparse(analysis.url or "").netloc
    aio = analysis.aio_score or 0
    geo = analysis.geo_score or 0
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    endpoints: dict[str, str] = {
        "llms_txt": f"{base}/llms.txt",
        "signals_json": f"{base}/signals.json",
        "meta": f"{base}/meta",
    }
    if full:
        endpoints["robots_txt"] = f"{base}/robots.txt"
        endpoints["organization_jsonld"] = f"{base}/organization.jsonld"
    payload: dict[str, Any] = {
        "schema": "geopulse.signals/v1",
        "version": int(version or 1),
        "updated_at": updated,
        "brand": brand,
        "site": site,
        "url": analysis.url,
        "scores": {
            "aio": round(float(aio), 1),
            "geo": round(float(geo), 1),
            "citation_potential": round(citation_potential_of(analysis), 1),
        },
        "endpoints": endpoints,
        "ai_crawlers": AI_CRAWLER_USER_AGENTS,
        "policy": {
            "allow_ai_crawlers": True,
            "prefer_llms_txt": True,
            "cache_control": CACHE_CONTROL,
            "tier": "full" if full else "basic",
        },
        "provider": {
            "name": "Centropic",
            "docs": f"{public_base.rstrip('/')}/faq#edge-signals",
        },
    }
    return payload


def cloudflare_worker_snippet(*, origin_edge_base: str, site_origin: str) -> str:
    """
    Worker che fa proxy degli artifact Centropic verso il dominio del cliente.
    origin_edge_base: https://app.../e/<token>
    site_origin: https://cliente.com (documentazione)
    """
    return f"""// Centropic Edge Signals — Cloudflare Worker
// Deploy: wrangler deploy (vedi workers/geopulse-signals/)
// Sostituisci CENTROPIC_ORIGIN con il tuo endpoint Edge assegnato.

const CENTROPIC_ORIGIN = "{origin_edge_base}";
const SITE_ORIGIN = "{site_origin.rstrip('/')}";

const ROUTES = {{
  "/llms.txt": "/llms.txt",
  "/.well-known/llms.txt": "/llms.txt",
  "/robots.txt": "/robots.txt",
  "/.well-known/organization.jsonld": "/organization.jsonld",
  "/geopulse/signals.json": "/signals.json",
}};

export default {{
  async fetch(request, env) {{
    const url = new URL(request.url);
    const path = ROUTES[url.pathname];
    if (!path) {{
      return new Response("Not found", {{ status: 404 }});
    }}
    const upstream = CENTROPIC_ORIGIN.replace(/\\/$/, "") + path;
    const headers = new Headers(request.headers);
    headers.set("X-GeoPulse-Site", SITE_ORIGIN);
    headers.set("Accept", "text/plain, application/json, */*");
    const res = await fetch(upstream, {{
      headers,
      cf: {{ cacheTtl: 300, cacheEverything: true }},
    }});
    const out = new Headers(res.headers);
    out.set("Access-Control-Allow-Origin", "*");
    out.set("X-GeoPulse-Edge", "1");
    out.set("Cache-Control", "private, max-age=60");
    return new Response(res.body, {{ status: res.status, headers: out }});
  }},
}};
"""


def html_embed_snippet(*, signals_url: str) -> str:
    """Snippet opzionale: discovery link + JSON-LD remoto via link tag."""
    llms = signals_url.replace("/signals.json", "/llms.txt")
    return (
        "<!-- Centropic Edge Signals -->\n"
        f'<link rel="alternate" type="text/plain" href="{llms}" title="llms.txt" />\n'
        f'<link rel="describedby" href="{signals_url}" type="application/json" />\n'
        '<script type="application/ld+json" id="geopulse-org">\n'
        "{\n"
        '  "@context": "https://schema.org",\n'
        '  "@type": "WebSite",\n'
        '  "hasPart": {\n'
        '    "@type": "CreativeWork",\n'
        f'    "url": "{llms}",\n'
        '    "name": "llms.txt"\n'
        "  }\n"
        "}\n"
        "</script>\n"
    )


def vercel_edge_config_snippet(*, origin_edge_base: str) -> str:
    base = origin_edge_base.rstrip("/")
    return f"""{{
  "version": 2,
  "rewrites": [
    {{ "source": "/llms.txt", "destination": "{base}/llms.txt" }},
    {{ "source": "/robots.txt", "destination": "{base}/robots.txt" }},
    {{ "source": "/geopulse/signals.json", "destination": "{base}/signals.json" }},
    {{ "source": "/.well-known/organization.jsonld", "destination": "{base}/organization.jsonld" }}
  ],
  "headers": [
    {{
      "source": "/(llms.txt|robots.txt|geopulse/signals.json)",
      "headers": [
        {{ "key": "Cache-Control", "value": "private, max-age=60" }},
        {{ "key": "X-GeoPulse-Edge", "value": "1" }}
      ]
    }}
  ]
}}
"""
