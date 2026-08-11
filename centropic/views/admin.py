"""HTTP views — admin domain."""

from __future__ import annotations

from typing import Any

from flask import Flask

# Architecture catalog: endpoints owned by this domain module.
ROUTE_CATALOG = [
    'admin_topup_user',
    'admin_home',
    'admin_set_plan',
    'admin_retry_job',
    'admin_refund_job',
    'admin_cancel_job'
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
                "admin",
                endpoint,
            )
