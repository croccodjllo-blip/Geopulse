"""Public Search / Ads helpers: hreflang, sitemap xhtml, crawler locale, hashing."""

from __future__ import annotations

import hashlib
from typing import Any

from services.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, locale_meta, normalize_locale

# Short UI code → hreflang BCP 47 (Google Search).
_HREFLANG: dict[str, str] = {
    "it": "it",
    "en": "en",
    "de": "de",
    "es": "es",
    "zh": "zh-CN",
    "ko": "ko",
}

# Marketing paths that get BreadcrumbList + sit in the public sitemap.
MARKETING_CRUMBS: dict[str, str] = {
    "/prodotto": "Prodotto",
    "/prezzi": "Prezzi",
    "/faq": "FAQ",
    "/register": "Registrati",
    "/guida": "Guida",
    "/esempio-report": "Esempio report",
    "/metodologia": "Metodologia",
    "/guide/llms-txt": "llms.txt",
    "/guide/schema-ai": "Schema AI",
    "/guide/score-vs-sov": "Score vs SoV",
    "/chi-siamo": "Chi siamo",
    "/contatti": "Contatti",
    "/interesse-plus": "Interesse Plus",
    "/status": "Status",
    "/privacy": "Privacy",
    "/termini": "Termini",
    "/rimborsi": "Rimborsi",
    "/dpa": "DPA",
    "/cookie": "Cookie",
    "/ai": "Trasparenza AI",
    "/trust": "Trust",
    "/accessibilita": "Accessibilità",
}

_SEARCH_CRAWLER_TOKENS: tuple[str, ...] = (
    "googlebot",
    "google-inspectiontool",
    "storebot-google",
    "adsbot-google",
    "mediapartners-google",
    "apis-google",
    "bingbot",
    "bingpreview",
    "yandexbot",
    "duckduckbot",
    "applebot",
    "slurp",
    "baiduspider",
)


def schema_in_language(code: str | None = None) -> str:
    """BCP 47 tag for JSON-LD ``inLanguage`` (it-IT, en-US, …)."""
    return locale_meta(code)["og"].replace("_", "-")


def hreflang_code(code: str | None) -> str:
    loc = normalize_locale(code)
    return _HREFLANG.get(loc, loc)


def language_alternate_url(base: str, path: str, code: str) -> str:
    """Absolute URL for one language version. Default locale keeps a clean path."""
    root = (base or "").rstrip("/")
    path = path or "/"
    if not path.startswith("/"):
        path = "/" + path
    loc = normalize_locale(code)
    if path == "/":
        url = f"{root}/"
    else:
        url = f"{root}{path}"
    if loc != DEFAULT_LOCALE:
        url = f"{url}?lang={loc}"
    return url


_HREFLANG_SKIP_ENDPOINTS = frozenset(
    {
        "login",
        "logout",
        "forgot_password",
        "reset_password",
        "verify_email",
        "preview_analyze",
        "preview_analyze_start",
        "preview_analyze_status",
        "billing_success",
        "billing_checkout",
        "billing_portal",
        "topup_credit_page",
        "topup_success",
    }
)
_HREFLANG_SKIP_PREFIXES = (
    "dashboard",
    "admin",
    "api_v1",
    "edge_",
    "ops_",
)
_PRIVATE_INDEX_PATH_PREFIXES = (
    "/dashboard",
    "/admin",
    "/crediti",
    "/billing",
    "/anteprima",
    "/logout",
    "/ops",
    "/api/",
)


def hreflang_enabled_for_request(endpoint: str | None, path: str | None) -> bool:
    """Hreflang belongs on public marketing HTML, not authed/app chrome."""
    ep = (endpoint or "").strip()
    p = path or "/"
    if ep in _HREFLANG_SKIP_ENDPOINTS:
        return False
    if ep.startswith(_HREFLANG_SKIP_PREFIXES):
        return False
    if any(p == pref or p.startswith(pref + "/") for pref in _PRIVATE_INDEX_PATH_PREFIXES):
        return False
    return True


def is_private_html_path(endpoint: str | None, path: str | None) -> bool:
    """App HTML that must not be indexed (dashboard, billing, preview, auth gates)."""
    ep = (endpoint or "").strip()
    if ep in {
        "login",
        "logout",
        "forgot_password",
        "reset_password",
        "verify_email",
    }:
        return True
    return not hreflang_enabled_for_request(endpoint, path) and ep not in {
        "register",
        "index",
        "sitemap_xml",
        "robots_txt",
        "health",
    }


def hreflang_alternates(base: str, path: str) -> list[dict[str, str]]:
    """``[{code, href}, …]`` including ``x-default`` (clean default-locale URL)."""
    items = [
        {
            "code": hreflang_code(code),
            "href": language_alternate_url(base, path, code),
        }
        for code in SUPPORTED_LOCALES
    ]
    items.append(
        {
            "code": "x-default",
            "href": language_alternate_url(base, path, DEFAULT_LOCALE),
        }
    )
    return items


def canonical_with_lang(base: str, path: str, lang_arg: str | None) -> str:
    """Self-canonical: ``?lang=`` only when it is a non-default locale."""
    root = (base or "").rstrip("/")
    path = path or "/"
    loc_url = f"{root}/" if path == "/" else f"{root}{path}"
    if not lang_arg:
        return loc_url
    loc = normalize_locale(lang_arg)
    if loc == DEFAULT_LOCALE or loc not in SUPPORTED_LOCALES:
        return loc_url
    return language_alternate_url(base, path, loc)


def og_locale_alternates(current: str | None) -> list[str]:
    cur = locale_meta(current)["og"]
    return [meta["og"] for code, meta in SUPPORTED_LOCALES.items() if meta["og"] != cur]


def breadcrumb_items(base: str, path: str) -> list[dict[str, str]]:
    """Home + current page for known marketing paths; empty on home/unknown."""
    path = path or "/"
    label = MARKETING_CRUMBS.get(path)
    if not label:
        return []
    root = (base or "").rstrip("/")
    return [
        {"name": "Centropic", "url": f"{root}/"},
        {"name": label, "url": f"{root}{path}"},
    ]


def sitemap_xhtml_links(base: str, path: str) -> str:
    """Indented xhtml:link rows for one sitemap ``<url>``."""
    lines = []
    for item in hreflang_alternates(base, path):
        href = item["href"].replace("&", "&amp;")
        lines.append(
            f'    <xhtml:link rel="alternate" hreflang="{item["code"]}" href="{href}"/>'
        )
    return "\n".join(lines)


def request_is_search_crawler(user_agent: str | None) -> bool:
    """True for Google/Bing/Ads crawlers — ignore Accept-Language on clean URLs."""
    ua = (user_agent or "").lower()
    if not ua:
        return False
    return any(tok in ua for tok in _SEARCH_CRAWLER_TOKENS)


def ads_sha256_email(email: str | None) -> str | None:
    """Google Ads enhanced conversions: SHA-256 of trimmed lowercase email."""
    raw = (email or "").strip().lower()
    if not raw or "@" not in raw or raw.startswith("@"):
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ads_user_data(email: str | None) -> dict[str, Any]:
    digest = ads_sha256_email(email)
    if not digest:
        return {}
    return {"user_data": {"sha256_email_address": digest}}
