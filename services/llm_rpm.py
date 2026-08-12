"""Client-side RPM token buckets for LLM providers (shared API keys).

Backends:
  memory (default) — process-local sliding window
  redis — shared across Gunicorn / analyze workers via REDIS_URL
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Iterable, Protocol

logger = logging.getLogger(__name__)

_PROVIDER_ENV = {
    "openai": "OPENAI_RPM",
    "perplexity": "PERPLEXITY_RPM",
    "anthropic": "ANTHROPIC_RPM",
    "gemini": "GEMINI_RPM",
    "xai": "XAI_RPM",
    "copilot": "COPILOT_RPM",
}

_PROVIDER_DEFAULTS = {
    "openai": 60,
    "perplexity": 30,
    "anthropic": 40,
    "gemini": 60,
    "xai": 30,
    "copilot": 30,
}


class RpmLimiter(Protocol):
    def acquire(self, *, block: bool = True) -> bool: ...


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


class RedisRpmBucket:
    """Sliding-window RPM shared via Redis sorted set."""

    def __init__(self, rpm: int, *, name: str, redis_client: object) -> None:
        self.rpm = max(1, int(rpm))
        self.name = name
        self._r = redis_client
        self._key = f"centropic:llm_rpm:{name}"

    def acquire(self, *, block: bool = True) -> bool:
        member_base = f"{os.getpid()}"
        while True:
            now = time.time()
            cutoff = now - 60.0
            try:
                pipe = self._r.pipeline()
                pipe.zremrangebyscore(self._key, 0, cutoff)
                pipe.zcard(self._key)
                _removed, n = pipe.execute()
                if int(n) < self.rpm:
                    member = f"{member_base}:{now}:{time.time_ns()}"
                    pipe2 = self._r.pipeline()
                    pipe2.zadd(self._key, {member: now})
                    pipe2.expire(self._key, 120)
                    pipe2.execute()
                    return True
                if not block:
                    return False
                oldest = self._r.zrange(self._key, 0, 0, withscores=True)
                if oldest:
                    wait = 60.0 - (now - float(oldest[0][1])) + 0.05
                else:
                    wait = 0.1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "redis rpm fallback to sleep provider=%s err=%s", self.name, exc
                )
                wait = 0.25
                if not block:
                    return False
            time.sleep(max(0.05, min(float(wait), 5.0)))


_BUCKETS: dict[str, RpmLimiter] = {}
_BUCKETS_LOCK = threading.Lock()


def rpm_backend() -> str:
    raw = (os.getenv("LLM_RPM_BACKEND") or "memory").strip().lower()
    if raw in {"redis", "shared"}:
        return "redis"
    return "memory"


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


def get_bucket(provider: str) -> RpmLimiter:
    key = (provider or "openai").strip().lower() or "openai"
    with _BUCKETS_LOCK:
        bucket = _BUCKETS.get(key)
        if bucket is not None:
            return bucket
        rpm = _rpm_for(key)
        if rpm_backend() == "redis":
            from services.redis_client import get_redis

            client = get_redis()
            if client is not None:
                bucket = RedisRpmBucket(rpm, name=key, redis_client=client)
                _BUCKETS[key] = bucket
                return bucket
            logger.warning("LLM_RPM_BACKEND=redis but Redis down; using memory for %s", key)
        bucket = RpmBucket(rpm, name=key)
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
