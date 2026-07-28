"""Minimal structured logging + request correlation."""

from __future__ import annotations

import secrets
import time

from flask import Flask, g, request


def new_request_id() -> str:
    return secrets.token_hex(8)


def configure_app_logging(app: Flask) -> None:
    """Attach request-id middleware and structured access log line."""

    @app.before_request
    def _bind_request_id() -> None:
        rid = (request.headers.get("X-Request-Id") or "").strip()[:32]
        g.request_id = rid or new_request_id()
        g._req_start = time.monotonic()

    @app.after_request
    def _emit_access_log(response):  # type: ignore[no-untyped-def]
        rid = getattr(g, "request_id", "-")
        response.headers["X-Request-Id"] = rid
        started = getattr(g, "_req_start", None)
        dur_ms = int((time.monotonic() - started) * 1000) if started else -1
        # Evita rumore su health/static
        path = request.path or ""
        if path not in {"/health"} and not path.startswith("/static/"):
            app.logger.info(
                "request id=%s method=%s path=%s status=%s dur_ms=%s",
                rid,
                request.method,
                path,
                response.status_code,
                dur_ms,
            )
        return response
