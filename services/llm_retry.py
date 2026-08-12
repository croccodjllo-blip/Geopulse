"""Retry helpers for LLM / HTTP providers (429 rate limits, transient 5xx)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _is_rate_limit(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "RateLimit" in name or "TooManyRequests" in name:
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status == 429:
        return True
    msg = str(exc).lower()
    return "rate limit" in msg or "429" in msg or "too many requests" in msg


def _retry_after_seconds(exc: BaseException, attempt: int, *, base: float = 0.4) -> float:
    """Honor Retry-After when present; else exponential backoff with jitter."""
    headers = getattr(exc, "headers", None) or {}
    if isinstance(headers, dict):
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw is not None:
            try:
                return max(0.05, float(raw))
            except (TypeError, ValueError):
                pass
    # response.response.headers for openai SDK
    resp = getattr(exc, "response", None)
    if resp is not None:
        h = getattr(resp, "headers", None) or {}
        raw = None
        try:
            raw = h.get("retry-after") or h.get("Retry-After")
        except Exception:
            raw = None
        if raw is not None:
            try:
                return max(0.05, float(raw))
            except (TypeError, ValueError):
                pass
    delay = base * (2 ** max(0, attempt)) + random.uniform(0, 0.25)
    return min(8.0, delay)


def call_with_retries(
    fn: Callable[[], T],
    *,
    retries: int = 4,
    label: str = "llm",
    retry_on: Callable[[BaseException], bool] | None = None,
) -> T:
    """Call ``fn`` with retries on rate-limit / transient errors."""
    from services.llm_rpm import acquire_for_label
    from services.llm_tpm import acquire_tpm_for_label

    predicate = retry_on or _is_rate_limit
    last: BaseException | None = None
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        try:
            # Client-side RPM before each attempt (shared API keys across jobs).
            acquire_for_label(label)
            acquire_tpm_for_label(label)
            return fn()
        except Exception as exc:  # noqa: BLE001 — provider SDKs vary
            last = exc
            if attempt >= attempts - 1 or not predicate(exc):
                raise
            wait = _retry_after_seconds(exc, attempt)
            logger.warning(
                "%s rate-limited/transient (attempt %s/%s): %s — sleep %.2fs",
                label,
                attempt + 1,
                attempts,
                str(exc)[:160],
                wait,
            )
            time.sleep(wait)
    assert last is not None
    raise last


def http_should_retry(status_code: int) -> bool:
    return status_code == 429 or status_code in {500, 502, 503, 504}


def probe_pacing_seconds() -> float:
    """Optional delay between sequential probe prompts (ms via env)."""
    import os

    try:
        ms = float(os.getenv("LLM_PROBE_PACING_MS", "250") or "250")
    except (TypeError, ValueError):
        ms = 250.0
    return max(0.0, ms / 1000.0)
