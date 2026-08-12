"""Client-side RPM token buckets for LLM providers (shared API keys)."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Iterable

logger = logging.getLogger(__name__)

_PROVIDER_ENV = {
    "openai": "OPENAI_RPM",
    "perplexity": "PERPLEXITY_RPM",
    "anthropic": "ANTHROPIC_RPM",
    "gemini": "GEMINI_RPM",
    "xai": "XAI_RPM",
    "copilot": "COPILOT_RPM",
}

# Conservative defaults — raise via env when provider quotas allow.
_PROVIDER_DEFAULTS = {
    "openai": 60,
    "perplexity": 30,
    "anthropic": 40,
    "gemini": 60,
    "xai": 30,
    "copilot": 30,
}


class RpmBucket:
    """Sliding-window requests-per-minute limiter (process-local)."""

    def __init__(self, rpm: int, *, name: str = "llm") -> None:
        self.rpm = max(1, int(rpm))
        self.name = name
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self, *, block: bool = True) -> bool:
        while True:
            with self._lock:
                now = time.monotonic()
                cutoff = now - 60.0
                self._timestamps = [t for t in self._timestamps if t >= cutoff]
                if len(self._timestamps) < self.rpm:
                    self._timestamps.append(now)
                    return True
                if not block:
                    return False
                wait = 60.0 - (now - self._timestamps[0]) + 0.05
            wait = max(0.05, min(wait, 5.0))
            logger.debug("rpm wait provider=%s sleep=%.2fs", self.name, wait)
            time.sleep(wait)


_BUCKETS: dict[str, RpmBucket] = {}
_BUCKETS_LOCK = threading.Lock()


def _rpm_for(provider: str) -> int:
    key = (provider or "").strip().lower()
    env_name = _PROVIDER_ENV.get(key)
    default = _PROVIDER_DEFAULTS.get(key, 60)
    if not env_name:
        return default
    try:
        return max(1, int(os.getenv(env_name, str(default)) or default))
    except (TypeError, ValueError):
        return default


def get_bucket(provider: str) -> RpmBucket:
    key = (provider or "openai").strip().lower() or "openai"
    with _BUCKETS_LOCK:
        bucket = _BUCKETS.get(key)
        if bucket is None:
            bucket = RpmBucket(_rpm_for(key), name=key)
            _BUCKETS[key] = bucket
        return bucket


def acquire_rpm(provider: str, *, block: bool = True) -> bool:
    """Block until a request slot is available for ``provider``."""
    return get_bucket(provider).acquire(block=block)


def provider_from_label(label: str) -> str | None:
    """Map call_with_retries labels like ``openai-sov`` → ``openai``."""
    low = (label or "").strip().lower()
    for name in _PROVIDER_ENV:
        if low == name or low.startswith(f"{name}-") or low.startswith(f"{name}_"):
            return name
    return None


def acquire_for_label(label: str, *, block: bool = True) -> bool:
    provider = provider_from_label(label)
    if not provider:
        return True
    return acquire_rpm(provider, block=block)


def reset_buckets_for_tests(providers: Iterable[str] | None = None) -> None:
    """Clear cached buckets (tests only)."""
    with _BUCKETS_LOCK:
        if providers is None:
            _BUCKETS.clear()
            return
        for p in providers:
            _BUCKETS.pop(str(p).lower(), None)
