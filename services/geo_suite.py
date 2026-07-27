"""Orchestratore analisi GEO/AIO avanzate (P0–P2).

Esegue moduli opzionali e restituisce findings + signals da fondere nel result.
"""

from __future__ import annotations

import logging
from typing import Any

from services.citability import analyze_citability
from services.entity_graph import build_entity_graph
from services.llms_lint import lint_ai_txt, lint_llms_txt
from services.locale_suite import analyze_locales
from services.local_pack import analyze_local_signals
from services.publish_verify import verify_published_pack
from services.schema_validator import validate_schema_quality
from services.citation_monitor import run_citation_monitor

logger = logging.getLogger(__name__)


def run_geo_suite(
    *,
    result: dict[str, Any],
    user: Any | None = None,
    previous_run: Any | None = None,
    run_measured: bool = False,
    prompts: list[str] | None = None,
) -> dict[str, Any]:
    """Arricchisce result in-place; ritorna anche il blocco signals extras."""
    scraped = result.get("scraped") or {}
    probes = result.get("probes") or {}
    pages = result.get("pages") or scraped.get("crawled_pages") or []
    findings: list[dict[str, Any]] = list(result.get("findings") or [])
    signals = dict(result.get("signals") or {})
    extras: dict[str, Any] = {}

    # --- Always-on analyses (cheap) ---
    try:
        graph = build_entity_graph(scraped=scraped, pages=pages)
        extras["entity_graph"] = graph
        findings.extend(graph.get("findings") or [])
    except Exception:
        logger.exception("entity_graph failed")

    try:
        cite = analyze_citability(scraped=scraped, pages=pages)
        extras["citability"] = cite
        findings.extend(cite.get("findings") or [])
    except Exception:
        logger.exception("citability failed")

    try:
        schema = validate_schema_quality(scraped=scraped)
        extras["schema_quality"] = schema
        findings.extend(schema.get("findings") or [])
    except Exception:
        logger.exception("schema_validator failed")

    try:
        locales = analyze_locales(scraped=scraped, pages=pages)
        extras["locales"] = locales
        findings.extend(locales.get("findings") or [])
    except Exception:
        logger.exception("locale_suite failed")

    try:
        local = analyze_local_signals(scraped=scraped)
        extras["local_pack"] = local
        findings.extend(local.get("findings") or [])
    except Exception:
        logger.exception("local_pack failed")

    try:
        llms_probe = probes.get("llms") or {}
        ai_probe = probes.get("ai") or {}
        llms_lint = lint_llms_txt(llms_probe.get("snippet") or "", present=bool(llms_probe.get("ok")))
        ai_lint = lint_ai_txt(ai_probe.get("snippet") or "", present=bool(ai_probe.get("ok")))
        extras["llms_lint"] = llms_lint
        extras["ai_lint"] = ai_lint
        findings.extend(llms_lint.get("findings") or [])
        findings.extend(ai_lint.get("findings") or [])
    except Exception:
        logger.exception("llms/ai lint failed")

    # --- Publish verify vs previous pack ---
    try:
        verify = verify_published_pack(
            probes=probes,
            previous_run=previous_run,
            scraped=scraped,
        )
        extras["publish_verify"] = verify
        findings.extend(verify.get("findings") or [])
    except Exception:
        logger.exception("publish_verify failed")

    # --- Measured citation monitor (Plus / when requested) ---
    if run_measured:
        try:
            brand = ""
            domain = scraped.get("domain") or ""
            if user is not None:
                brand = getattr(user, "company", None) or ""
            brand = brand or (scraped.get("entity") or {}).get("brand_name") or domain
            competitors = result.get("competitors") or []
            monitored = run_citation_monitor(
                brand=str(brand),
                domain=str(domain),
                prompts=prompts,
                competitors=competitors,
            )
            extras["sov_measured"] = monitored
            signals["sov_measured"] = monitored
            findings.extend(monitored.get("findings") or [])
        except Exception:
            logger.exception("citation_monitor failed")

    signals.update({k: v for k, v in extras.items() if k != "sov_measured" or "sov_measured" not in signals})
    result["findings"] = findings
    result["signals"] = signals
    result["geo_suite"] = extras
    return extras
