"""HTTP views — billing domain."""

from __future__ import annotations

from typing import Any

from flask import Flask

# Architecture catalog: endpoints owned by this domain module.
ROUTE_CATALOG = [
    'billing_checkout',
    'billing_portal',
    'billing_success',
    'billing_paddle_webhook',
    'billing_webhook',
    'topup_credit_page',
    'topup_checkout',
    'topup_success',
    'billing_topup_webhook'
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
                "billing",
                endpoint,
            )
