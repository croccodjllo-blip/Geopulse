"""Measured Share-of-Voice via LLM prompt probes.

Compat layer: delegates to citation_monitor (multi-engine).
Measured analysis is a Plus-only product capability.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from services.citation_monitor import (
    citation_monitor_available as measured_sov_available,
    run_citation_monitor,
    run_measured_sov,
)


def user_can_run_measured(user: Any | None) -> bool:
    """True solo per piani Plus/pro/admin (is_pro). Free → solo SoV proxy."""
    if user is None:
        return False
    return bool(getattr(user, "is_pro", False))


def should_run_measured(
    *,
    user: Any | None,
    requested: bool = False,
    env_enabled: bool = True,
) -> bool:
    """Gate unico: env + Plus + connector API disponibili + richiesta esplicita."""
    return bool(
        requested
        and env_enabled
        and user_can_run_measured(user)
        and measured_sov_available()
    )


def _host(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw).strip().lower()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    try:
        host = (urlparse(text).hostname or "").lower()
    except Exception:
        host = ""
    if host.startswith("www."):
        host = host[4:]
    return host


def brand_from_domain(domain: str) -> str:
    host = _host(domain) or str(domain or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    label = host.split(".")[0] if host else ""
    if not label:
        return str(domain or "").strip()
    return label[:1].upper() + label[1:]


def is_user_owned_domain(user: Any | None, domain: str) -> bool:
    """True when the analyzed host matches the account website/company host."""
    target = _host(domain)
    if not target or user is None:
        return False
    for raw in (
        getattr(user, "website_url", None),
        getattr(user, "company", None),
    ):
        if not raw:
            continue
        raw_s = str(raw)
        host = _host(raw_s if ("." in raw_s or "://" in raw_s) else None)
        if not host:
            continue
        if target == host or target.endswith("." + host) or host.endswith("." + target):
            return True
    return False


def resolve_measured_brand(
    *,
    user: Any | None,
    domain: str,
    scraped: dict[str, Any] | None = None,
) -> str:
    """Brand to probe for SoV measured — must match the *analyzed site*.

    Prefer crawl entity / domain label. Account ``company`` is only used when
    the user is auditing their own site; otherwise Nike audits were probing
    ``centropic.ai`` and always returned 0 mentions → UI looked all-Stimato.
    """
    scraped = scraped if isinstance(scraped, dict) else {}
    entity = ""
    ent = scraped.get("entity")
    if isinstance(ent, dict):
        entity = str(ent.get("brand_name") or "").strip()
    title = str(scraped.get("title") or "").strip()
    domain_brand = brand_from_domain(domain)
    if is_user_owned_domain(user, domain):
        company = str(getattr(user, "company", None) or "").strip() if user else ""
        # Prefer human company name over a bare domain string in company field.
        if company and "." not in company:
            return company
        return entity or company or domain_brand or domain
    if entity:
        return entity
    if title:
        token = title.split("|")[0].split("-")[0].split("–")[0].strip()
        # Ignore titles that are just a hostname / URL remnant.
        hostish = _host(token) or (
            token.lower()[4:] if token.lower().startswith("www.") else ""
        )
        if (
            token
            and len(token.split()) <= 3
            and "." not in token
            and not hostish
        ):
            return token
    return domain_brand or domain


__all__ = [
    "measured_sov_available",
    "run_citation_monitor",
    "run_measured_sov",
    "user_can_run_measured",
    "should_run_measured",
    "brand_from_domain",
    "is_user_owned_domain",
    "resolve_measured_brand",
]
