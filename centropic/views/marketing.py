"""HTTP views — marketing domain."""

from __future__ import annotations

from typing import Any

from flask import Flask

# Architecture catalog: endpoints owned by this domain module.
ROUTE_CATALOG = [
    'privacy',
    'terms',
    'refunds',
    'about',
    'contact',
    'sample_report',
    'agencies',
    'status_page',
    'site_guide',
    'methodology',
    'guide_llms_txt',
    'guide_schema_ai',
    'guide_score_vs_sov',
    'index',
    'set_language',
    'product',
    'pricing',
    'pricing_alias',
    'pro_interest',
    'faq'
]


def register(app: Flask, runtime: Any) -> None:
    """Validate domain endpoints are bound on the application.

    Route handlers currently live in ``app`` (compatibility). This module is
    the architectural owner — handlers migrate here without changing endpoints.
    """
    for endpoint in ROUTE_CATALOG:
        if endpoint not in app.view_functions:
            app.logger.warning(
                "centropic.views.%s: missing endpoint %s",
                "marketing",
                endpoint,
            )
