"""Sentry SDK bootstrap for Centropic (Flask)."""

from __future__ import annotations

import logging
import os
from typing import Any


def sentry_dsn() -> str:
    return (os.getenv("SENTRY_DSN") or "").strip()


def sentry_environment() -> str:
    explicit = (os.getenv("SENTRY_ENVIRONMENT") or "").strip()
    if explicit:
        return explicit
    if (os.getenv("FLASK_DEBUG") or "0").strip() == "1":
        return "development"
    return "production"


def sentry_release() -> str | None:
    for key in ("SENTRY_RELEASE", "GIT_SHA", "SOURCE_VERSION"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return None


def _traces_sampler(sampling_context: dict[str, Any]) -> float:
    """Keep SoV/billing signal; drop health/static noise."""
    try:
        rate = float(os.getenv("SENTRY_TRACES", "0.05") or "0.05")
    except ValueError:
        rate = 0.05
    rate = max(0.0, min(1.0, rate))
    wsgi = sampling_context.get("wsgi_environ") or {}
    path = str(wsgi.get("PATH_INFO") or "")
    if path in {"/health", "/favicon.ico", "/robots.txt", "/ads.txt", "/ai.txt"}:
        return 0.0
    if path.startswith("/static/"):
        return 0.0
    return rate


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    # Drop expected client disconnects / bot noise if tagged as such later.
    return event


def init_sentry(app: Any | None = None) -> bool:
    """Initialize Sentry when SENTRY_DSN is set. Returns True if active."""
    dsn = sentry_dsn()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except Exception:
        if app is not None:
            app.logger.exception("Sentry SDK import failed")
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=sentry_environment(),
            release=sentry_release(),
            integrations=[
                FlaskIntegration(transaction_style="url"),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            traces_sampler=_traces_sampler,
            send_default_pii=False,
            before_send=_before_send,
        )
        if app is not None:
            app.logger.info(
                "Sentry initialized env=%s release=%s",
                sentry_environment(),
                sentry_release() or "-",
            )
        return True
    except Exception:
        if app is not None:
            app.logger.exception("Sentry init failed")
        return False
