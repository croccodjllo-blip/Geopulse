"""HTTP views — api domain."""

from __future__ import annotations

from typing import Any

from flask import Flask

# Architecture catalog: endpoints owned by this domain module.
ROUTE_CATALOG = [
    'api_v1_analyze',
    'api_v1_sites',
    'api_v1_site_edge',
    'api_v1_site_edge_cms_bundle'
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
                "api",
                endpoint,
            )
