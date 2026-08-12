"""HTTP views — dashboard domain."""

from __future__ import annotations

from typing import Any

from flask import Flask

# Architecture catalog: endpoints owned by this domain module.
ROUTE_CATALOG = [
    'dashboard_geo_ui',
    'dashboard',
    'dashboard_analyze_confirmed',
    'dashboard_competitors_suggest',
    'dashboard_job_status',
    'dashboard_guide',
    'dashboard_settings',
    'dashboard_verify',
    'dashboard_verify_rescan',
    'download_whitelabel',
    'download_whitelabel_html',
    'dashboard_history',
    'download_pack',
    'email_pack',
    'set_rescan_schedule',
    'site_history',
    'download_run_pack',
    'export_history_csv',
    'export_all_sites_zip'
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
                "dashboard",
                endpoint,
            )
