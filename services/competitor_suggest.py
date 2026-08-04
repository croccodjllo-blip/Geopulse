"""Auto-suggest competitor domains for Plus Competitor snapshot."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests
from openai import OpenAI

from services.ssrf import assert_public_http_url, safe_get
from services.usage_billing import MAX_TOKENS_PER_CALL

logger = logging.getLogger(__name__)

_SKIP_HOST_SUFFIXES = (
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "google.com",
    "googleapis.com",
    "gstatic.com",
    "apple.com",
    "microsoft.com",
    "github.com",
    "wikipedia.org",
    "cloudflare.com",
    "cdninstagram.com",
    "schema.org",
    "w3.org",
    "sentry.io",
    "hotjar.com",
    "googletagmanager.com",
)

# Seed rivals for known product niches when LLM/heuristics are thin.
_VERTICAL_SEEDS: dict[str, list[str]] = {
    "centropic.ai": [
        "https://surferseo.com/",
        "https://peec.ai/",
        "https://otterly.ai/",
    ],
    "geopulse.it": [
        "https://surferseo.com/",
        "https://peec.ai/",
        "https://otterly.ai/",
    ],
}


def _host_key(netloc: str) -> str:
    host = (netloc or "").lower().split("@")[-1]
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


def _is_skipped_host(host: str) -> bool:
    h = _host_key(host)
    if not h or "." not in h:
        return True
    return any(h == s or h.endswith("." + s) for s in _SKIP_HOST_SUFFIXES)


def normalize_competitor_url(raw: str, *, seed_host: str = "") -> str | None:
    """Return a public homepage URL or None if invalid / same-host / blocked."""
    text = (raw or "").strip()
    if not text:
        return None
    if not re.match(r"^https?://", text, flags=re.I):
        text = "https://" + text.lstrip("/")
    try:
        safe = assert_public_http_url(text, resolve=False)
    except Exception:
        return None
    parsed = urlparse(safe)
    host = _host_key(parsed.netloc)
    if not host or _is_skipped_host(host):
        return None
    if seed_host and host == _host_key(seed_host):
        return None
    # Prefer site root for snapshot (homepage score).
    return f"{parsed.scheme}://{parsed.netloc}/"


def _snippet_context(url: str, timeout: float = 12.0) -> dict[str, str]:
    """Lightweight public fetch for title/description used by the suggester."""
    out = {"url": url, "domain": _host_key(urlparse(url).netloc), "title": "", "description": ""}
    try:
        assert_public_http_url(url, resolve=True)
    except Exception:
        return out
    try:
        session = requests.Session()
        res = safe_get(
            session,
            url,
            timeout=timeout,
            max_redirects=3,
            headers={
                "User-Agent": "Centropic/1.0 (+https://centropic.ai; competitor-suggest)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
    except Exception:
        return out
    if res.status_code >= 400 or not res.text:
        return out
    html = res.text[:400_000]
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if title_m:
        out["title"] = re.sub(r"\s+", " ", title_m.group(1)).strip()[:160]
    desc_m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        flags=re.I,
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
        html,
        flags=re.I,
    )
    if desc_m:
        out["description"] = re.sub(r"\s+", " ", desc_m.group(1)).strip()[:280]
    out["domain"] = _host_key(urlparse(str(res.url)).netloc) or out["domain"]
    # Collect a few external href hosts for heuristic fallback.
    hosts: list[str] = []
    for href in re.findall(r'href=["\'](https?://[^"\']+)["\']', html[:200_000], flags=re.I):
        host = _host_key(urlparse(href).netloc)
        if host and host != out["domain"] and not _is_skipped_host(host):
            if host not in hosts:
                hosts.append(host)
        if len(hosts) >= 12:
            break
    out["outbound_hosts"] = ",".join(hosts)
    return out


def _llm_competitors(
    ctx: dict[str, str],
    *,
    api_key: str,
    model: str,
    limit: int,
) -> list[str]:
    client = OpenAI(api_key=api_key, timeout=35.0, max_retries=2)
    prompt = f"""
Sei un analista di mercato digital/SaaS. Suggerisci fino a {limit} competitor diretti
del sito sotto (homepage pubbliche). Rispondi SOLO con JSON:
{{"competitors":["https://esempio.com/","https://altro.com/"]}}

Regole:
- Solo homepage di brand rivali reali nello stesso spazio prodotto/niche.
- Niente social, directory, CDN, Wikipedia, Google, news generiche.
- Niente lo stesso dominio del seed.
- URL https assoluti, preferisci root "/" .
- Se il seed è uno strumento AIO/GEO/answer-engine optimization, preferisci rivali in quell'area.

Seed URL: {ctx.get("url")}
Domain: {ctx.get("domain")}
Title: {ctx.get("title")}
Description: {ctx.get("description")}
""".strip()
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=min(400, MAX_TOKENS_PER_CALL),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Restituisci solo JSON valido con chiave competitors.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = (completion.choices[0].message.content or "").strip()
        data = json.loads(raw) if raw else {}
        items = data.get("competitors") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        return [str(x) for x in items if x]
    except Exception:
        logger.exception("competitor LLM suggest failed for %s", ctx.get("domain"))
        return []


def _heuristic_competitors(ctx: dict[str, str], *, limit: int) -> list[str]:
    seed = (ctx.get("domain") or "").lower()
    out: list[str] = []
    for url in _VERTICAL_SEEDS.get(seed) or []:
        norm = normalize_competitor_url(url, seed_host=seed)
        if norm and norm not in out:
            out.append(norm)
    for host in (ctx.get("outbound_hosts") or "").split(","):
        host = host.strip()
        if not host:
            continue
        norm = normalize_competitor_url(f"https://{host}/", seed_host=seed)
        if norm and norm not in out:
            out.append(norm)
        if len(out) >= limit:
            break
    return out[:limit]


def suggest_competitors(
    url: str,
    *,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    limit: int = 3,
    logger: Any | None = None,
) -> dict[str, Any]:
    """
    Suggest up to `limit` competitor homepage URLs for Competitor snapshot.

    Returns {competitors: [url...], source: llm|seed|heuristic|mixed, domain}.
    """
    limit = max(1, min(int(limit or 3), 3))
    try:
        seed = assert_public_http_url(url, resolve=True)
    except Exception as exc:
        return {"competitors": [], "source": "error", "error": str(exc), "domain": ""}

    ctx = _snippet_context(seed)
    seed_host = ctx.get("domain") or _host_key(urlparse(seed).netloc)
    collected: list[str] = []
    source = "heuristic"

    # 1) Vertical seeds first (stable for our own product niche).
    for url_s in _heuristic_competitors(
        {**ctx, "outbound_hosts": ""}, limit=limit
    ):
        if url_s not in collected:
            collected.append(url_s)
    if collected:
        source = "seed"

    # 2) LLM fill / replace gaps.
    if api_key and len(collected) < limit:
        for raw in _llm_competitors(ctx, api_key=api_key, model=model, limit=limit):
            norm = normalize_competitor_url(raw, seed_host=seed_host)
            if norm and norm not in collected:
                collected.append(norm)
            if len(collected) >= limit:
                break
        if any(
            _host_key(urlparse(u).netloc) not in {
                _host_key(urlparse(s).netloc)
                for s in (_VERTICAL_SEEDS.get(seed_host) or [])
            }
            for u in collected
        ):
            source = "mixed" if source == "seed" else "llm"
        elif source != "seed":
            source = "llm"

    # 3) Outbound-host heuristic to finish the list.
    if len(collected) < limit:
        for url_h in _heuristic_competitors(ctx, limit=limit):
            if url_h not in collected:
                collected.append(url_h)
            if len(collected) >= limit:
                break
        if source == "heuristic" and collected:
            source = "heuristic"
        elif collected and source == "seed":
            source = "mixed"

    if logger is not None:
        logger.info(
            "competitor_suggest domain=%s source=%s n=%s",
            seed_host,
            source,
            len(collected),
        )
    return {
        "competitors": collected[:limit],
        "source": source,
        "domain": seed_host,
        "title": ctx.get("title") or "",
    }
