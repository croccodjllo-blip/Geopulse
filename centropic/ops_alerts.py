"""Sentry ops signals for analyze queue health (fail soft if SDK off)."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Dedupe noisy health polls: at most one stale alert per window.
_STALE_LAST_TS = 0.0
_STALE_COOLDOWN_S = 300.0


def _capture(message: str, *, level: str = "error", **extras: Any) -> None:
    try:
        import sentry_sdk
    except Exception:
        logger.warning("ops alert (no sentry sdk): %s %s", message, extras)
        return
    try:
        # Sentry 2.x: new_scope; older SDKs still expose push_scope.
        scope_cm = getattr(sentry_sdk, "new_scope", None) or sentry_sdk.push_scope
        with scope_cm() as scope:
            scope.set_level(level)
            for key, value in extras.items():
                scope.set_extra(key, value)
            scope.set_tag("centropic.ops", "1")
            sentry_sdk.capture_message(message, level=level)
    except Exception:
        logger.exception("sentry capture_message failed: %s", message)


def report_analyze_job_failed(
    *,
    job_id: int,
    user_id: int | None,
    error: str,
    phase: str | None = None,
) -> None:
    _capture(
        f"analyze_job_failed id={job_id}",
        level="error",
        job_id=job_id,
        user_id=user_id,
        error=(error or "")[:500],
        progress_phase=phase or "",
    )


def report_stale_running_jobs(count: int, *, stale_after_minutes: int) -> None:
    """Emit at most once per cooldown when stale_running > 0."""
    global _STALE_LAST_TS
    if count <= 0:
        return
    now = time.monotonic()
    if now - _STALE_LAST_TS < _STALE_COOLDOWN_S:
        return
    _STALE_LAST_TS = now
    _capture(
        f"analyze_stale_running count={count}",
        level="warning",
        stale_running=count,
        stale_after_minutes=stale_after_minutes,
    )
