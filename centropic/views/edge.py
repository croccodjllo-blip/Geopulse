"""HTTP views — Edge Signals public + dashboard controls."""

from __future__ import annotations

from typing import Any

from flask import Flask

ROUTE_CATALOG = [
    "edge_llms_txt",
    "edge_robots_txt",
    "edge_organization_jsonld",
    "edge_signals_json",
    "edge_meta",
    "edge_enable",
    "edge_disable",
    "edge_rotate",
]


def register(app: Flask, runtime: Any) -> None:
    """Edge routes remain bound by ``app``; this module owns the domain contract.

    Handlers are defined in ``runtime`` (app.py) for endpoint stability. Domain
    helpers and future migrations land here.
    """
    # Promote helpers onto this module for architectural access.
    for name in (
        "_edge_site_or_404",
        "_edge_client_key",
        "_edge_rate_limited",
        "_edge_response",
        "_edge_full_access",
    ):
        if hasattr(runtime, name):
            globals()[name] = getattr(runtime, name)

    for endpoint in ROUTE_CATALOG:
        if endpoint not in app.view_functions:
            app.logger.warning("edge view missing endpoint %s", endpoint)
