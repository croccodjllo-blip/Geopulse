"""In-process metrics + optional Sentry hooks for SaaS ops."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from typing import Any

from flask import Flask, g, request

_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)
_timings_ms: dict[str, list[float]] = defaultdict(list)
_started_at = time.time()

log = logging.getLogger("centropic.metrics")


def incr(name: str, n: int = 1) -> None:
    with _lock:
        _counters[name] += n


def observe_ms(name: str, duration_ms: float, *, keep: int = 200) -> None:
    with _lock:
        bucket = _timings_ms[name]
        bucket.append(duration_ms)
        if len(bucket) > keep:
            del bucket[: len(bucket) - keep]


def snapshot() -> dict[str, Any]:
    with _lock:
        timings: dict[str, Any] = {}
        for key, values in _timings_ms.items():
            if not values:
                continue
            timings[key] = {
                "count": len(values),
                "p50_ms": sorted(values)[len(values) // 2],
                "max_ms": max(values),
            }
        return {
            "uptime_s": int(time.time() - _started_at),
            "counters": dict(_counters),
            "timings": timings,
        }


def configure_metrics(app: Flask) -> None:
    """Wire request metrics; optionally init Sentry if SENTRY_DSN is set."""
    from centropic.config import METRICS_ENABLED, SENTRY_DSN

    if SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration

            sentry_sdk.init(
                dsn=SENTRY_DSN,
                integrations=[FlaskIntegration()],
                traces_sample_rate=float(os.getenv("SENTRY_TRACES", "0.05")),
                send_default_pii=False,
            )
            app.logger.info("Sentry initialized")
        except Exception:
            app.logger.exception("Sentry init failed")

    if not METRICS_ENABLED:
        return

    @app.before_request
    def _metrics_start() -> None:
        g._metrics_t0 = time.monotonic()

    @app.after_request
    def _metrics_end(response):  # type: ignore[no-untyped-def]
        t0 = getattr(g, "_metrics_t0", None)
        if t0 is not None:
            observe_ms("http.request", (time.monotonic() - t0) * 1000)
        incr(f"http.status.{response.status_code}")
        path = request.path or ""
        if path.startswith("/billing/"):
            incr("http.billing")
            if "webhook" in path:
                incr("billing.webhook_hit")
        if path.startswith("/api/"):
            incr("http.api")
        if path.startswith("/dashboard"):
            incr("http.dashboard")
        return response
