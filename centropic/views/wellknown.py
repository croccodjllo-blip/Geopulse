"""HTTP views — wellknown domain."""

from __future__ import annotations

from typing import Any

from flask import Flask

# Architecture catalog: endpoints owned by this domain module.
ROUTE_CATALOG = [
    'health',
    'llms_txt',
    'ai_txt',
    'humans_txt',
    'security_txt',
    'robots_txt',
    'sitemap_xml',
    'ads_txt',
    'favicon_svg',
    'favicon_ico'
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
                "wellknown",
                endpoint,
            )
