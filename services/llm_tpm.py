"""Client-side TPM (tokens-per-minute) gates for LLM providers.

Mirrors ``services.llm_rpm``: memory sliding window by default, Redis sorted
set when ``LLM_TPM_BACKEND=redis`` so Gunicorn + analyze workers share one
budget per API key.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Iterable, Protocol

logger = logging.getLogger(__name__)

_PROVIDER_ENV = {
    "openai": "OPENAI_TPM",
    "perplexity": "PERPLEXITY_TPM",
    "anthropic": "ANTHROPIC_TPM",
    "gemini": "GEMINI_TPM",
    "xai": "XAI_TPM",
    "copilot": "COPILOT_TPM",
}

# Conservative defaults — below typical provider hard caps so multi-host
# workers pace themselves before the vendor 429s.
_PROVIDER_DEFAULTS = {
    "openai": 200_000,
    "perplexity": 80_000,
    "anthropic": 100_000,
    "gemini": 200_000,
    "xai": 80_000,
    "copilot": 80_000,
}


class TpmLimiter(Protocol):
    def acquire(self, tokens: int, *, block: bool = True) -> bool: ...


class TpmBucket:
    """Sliding-window tokens-per-minute limiter (process-local)."""

    def __init__(self, tpm: int, *, name: str = "llm") -> None:
        self.tpm = max(1, int(tpm))
        self.name = name
        self._events: list[tuple[float, int]] = []
        self._lock = threading.Lock()

    def acquire(self, tokens: int, *, block: bool = True) -> bool:
        need = max(1, int(tokens))
        while True:
            with self._lock:
                now = time.monotonic()
                cutoff = now - 60.0
                self._events = [(t, n) for t, n in self._events if t >= cutoff]
                used = sum(n for _, n in self._events)
                if used + need <= self.tpm:
                    self._events.append((now, need))
                    return True
                if not block:
                    return False
                wait = 60.0 - (now - self._events[0][0]) + 0.05 if self._events else 0.1
            time.sleep(max(0.05, min(float(wait), 5.0)))
            logger.debug("tpm wait provider=%s sleep=%.2fs need=%s", self.name, wait, need)


class RedisTpmBucket:
    """Sliding-window TPM shared via Redis sorted set.

    Member format: ``{pid}:{unix}:{ns}:{tokens}`` with score = unix timestamp.
    """

    def __init__(self, tpm: int, *, name: str, redis_client: object) -> None:
        self.tpm = max(1, int(tpm))
        self.name = name
        self._r = redis_client
        self._key = f"centropic:llm_tpm:{name}"

    @staticmethod
    def _tokens_from_member(member: str) -> int:
        try:
            return max(0, int(str(member).rsplit(":", 1)[-1]))
        except (TypeError, ValueError):
            return 0

    def acquire(self, tokens: int, *, block: bool = True) -> bool:
        need = max(1, int(tokens))
        member_base = f"{os.getpid()}"
        while True:
            now = time.time()
            cutoff = now - 60.0
            try:
                pipe = self._r.pipeline()
                pipe.zremrangebyscore(self._key, 0, cutoff)
                pipe.zrange(self._key, 0, -1)
                _removed, members = pipe.execute()
                used = sum(self._tokens_from_member(m) for m in (members or []))
                if used + need <= self.tpm:
                    member = f"{member_base}:{now}:{time.time_ns()}:{need}"
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
                    "redis tpm fallback to sleep provider=%s err=%s", self.name, exc
                )
                wait = 0.25
                if not block:
                    return False
            time.sleep(max(0.05, min(float(wait), 5.0)))


_BUCKETS: dict[str, TpmLimiter] = {}
_BUCKETS_LOCK = threading.Lock()


def tpm_backend() -> str:
    raw = (os.getenv("LLM_TPM_BACKEND") or "memory").strip().lower()
    if raw in {"redis", "shared"}:
        return "redis"
    if raw in {"off", "none", "0", "disabled"}:
        return "off"
    return "memory"


def _tpm_for(provider: str) -> int:
    key = (provider or "").strip().lower()
    env_name = _PROVIDER_ENV.get(key)
    default = _PROVIDER_DEFAULTS.get(key, 200_000)
    if not env_name:
        return default
    try:
        return max(1, int(os.getenv(env_name, str(default)) or default))
    except (TypeError, ValueError):
        return default


def reserve_tokens_default() -> int:
    """Tokens reserved before an LLM call when the caller does not estimate."""
    try:
        from services.usage_billing import MAX_TOKENS_PER_CALL

        base = int(MAX_TOKENS_PER_CALL)
    except Exception:
        base = 1500
    try:
        override = os.getenv("LLM_TPM_RESERVE_TOKENS")
        if override is not None and str(override).strip() != "":
            return max(1, int(override))
    except (TypeError, ValueError):
        pass
    # Input + max output headroom.
    return max(1, base + 800)


def get_bucket(provider: str) -> TpmLimiter | None:
    if tpm_backend() == "off":
        return None
    key = (provider or "openai").strip().lower() or "openai"
    with _BUCKETS_LOCK:
        bucket = _BUCKETS.get(key)
        if bucket is not None:
            return bucket
        tpm = _tpm_for(key)
        if tpm_backend() == "redis":
            from services.redis_client import get_redis

            client = get_redis()
            if client is not None:
                bucket = RedisTpmBucket(tpm, name=key, redis_client=client)
                _BUCKETS[key] = bucket
                return bucket
            logger.warning("LLM_TPM_BACKEND=redis but Redis down; using memory for %s", key)
        bucket = TpmBucket(tpm, name=key)
        _BUCKETS[key] = bucket
        return bucket


def acquire_tpm(provider: str, tokens: int | None = None, *, block: bool = True) -> bool:
    """Block until ``tokens`` fit in the provider TPM window."""
    bucket = get_bucket(provider)
    if bucket is None:
        return True
    need = reserve_tokens_default() if tokens is None else max(1, int(tokens))
    return bucket.acquire(need, block=block)


def acquire_tpm_for_label(
    label: str, tokens: int | None = None, *, block: bool = True
) -> bool:
    from services.llm_rpm import provider_from_label

    provider = provider_from_label(label)
    if not provider:
        return True
    return acquire_tpm(provider, tokens, block=block)


def reset_tpm_buckets_for_tests(providers: Iterable[str] | None = None) -> None:
    with _BUCKETS_LOCK:
        if providers is None:
            _BUCKETS.clear()
            return
        for p in providers:
            _BUCKETS.pop(str(p).lower(), None)
