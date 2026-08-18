"""Shared HTTP/API rate limiter (Redis preferred; SQLite host-local fallback).

Backends (``RATE_LIMIT_BACKEND``):
  auto   — Redis when ``REDIS_URL`` is reachable, else SQLite (default)
  redis  — require Redis (fail closed at boot in prod unless fallback allowed)
  sqlite — single-host SQLite WAL (legacy / no Redis)
  memory — process-local only (dev/test)

Multi-host SaaS: use Redis so login/analyze/API budgets are shared across
Gunicorn and app nodes. SQLite remains the same-host fallback when Redis
blips (``RATE_LIMIT_REDIS_FALLBACK=sqlite``, default) so a Redis outage does
not open unlimited traffic or lock out all logins.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Atomic sliding-window: purge → count → maybe ZADD.
_REDIS_ALLOW_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[2])
local n = redis.call('ZCARD', KEYS[1])
if n >= tonumber(ARGV[3]) then
  return 0
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[5]))
return 1
"""


class RateLimiter(Protocol):
    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool: ...

    def remaining(self, key: str, *, limit: int, window_seconds: int) -> int: ...


class MemoryRateLimiter:
    """Limiter per-processo (dev / fallback esplicito)."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._events[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def remaining(self, key: str, *, limit: int, window_seconds: int) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._events[key]
            while q and q[0] < cutoff:
                q.popleft()
            return max(0, limit - len(q))


class SqliteRateLimiter:
    """Sliding window su SQLite — coerente tra processi sullo stesso host."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_events (
                    bucket TEXT NOT NULL,
                    ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_rate_bucket_ts "
                "ON rate_events(bucket, ts)"
            )

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        "DELETE FROM rate_events WHERE bucket = ? AND ts < ?",
                        (key, cutoff),
                    )
                    row = conn.execute(
                        "SELECT COUNT(*) FROM rate_events WHERE bucket = ?",
                        (key,),
                    ).fetchone()
                    count = int(row[0] if row else 0)
                    if count >= limit:
                        conn.execute("COMMIT")
                        return False
                    conn.execute(
                        "INSERT INTO rate_events(bucket, ts) VALUES (?, ?)",
                        (key, now),
                    )
                    conn.execute("COMMIT")
                    return True
                except Exception:
                    conn.execute("ROLLBACK")
                    raise

    def remaining(self, key: str, *, limit: int, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM rate_events WHERE bucket = ? AND ts < ?",
                    (key, cutoff),
                )
                row = conn.execute(
                    "SELECT COUNT(*) FROM rate_events WHERE bucket = ?",
                    (key,),
                ).fetchone()
                count = int(row[0] if row else 0)
                return max(0, limit - count)


class RedisRateLimiter:
    """Sliding-window limiter shared across hosts via Redis sorted sets."""

    def __init__(
        self,
        redis_client: Any,
        *,
        key_prefix: str | None = None,
        fallback: RateLimiter | None = None,
    ) -> None:
        self._r = redis_client
        self._prefix = (
            key_prefix
            if key_prefix is not None
            else (os.getenv("RATE_LIMIT_REDIS_PREFIX") or "centropic:rl:").strip()
            or "centropic:rl:"
        )
        self._fallback = fallback
        self._script = _REDIS_ALLOW_LUA

    def _redis_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def _ttl_seconds(self, window_seconds: int) -> int:
        return max(60, int(window_seconds) * 2)

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - max(1, int(window_seconds))
        member = f"{os.getpid()}:{now}:{time.time_ns()}:{uuid.uuid4().hex[:8]}"
        rkey = self._redis_key(key)
        try:
            allowed = self._r.eval(
                self._script,
                1,
                rkey,
                str(now),
                str(cutoff),
                str(max(1, int(limit))),
                member,
                str(self._ttl_seconds(window_seconds)),
            )
            return int(allowed) == 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis rate limit error key=%s err=%s", key, exc)
            if self._fallback is not None:
                return self._fallback.allow(
                    key, limit=limit, window_seconds=window_seconds
                )
            # Fail-closed on abuse path when no fallback: deny.
            return False

    def remaining(self, key: str, *, limit: int, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - max(1, int(window_seconds))
        rkey = self._redis_key(key)
        try:
            pipe = self._r.pipeline()
            pipe.zremrangebyscore(rkey, "-inf", cutoff)
            pipe.zcard(rkey)
            _removed, n = pipe.execute()
            return max(0, int(limit) - int(n or 0))
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis rate limit remaining error key=%s err=%s", key, exc)
            if self._fallback is not None:
                return self._fallback.remaining(
                    key, limit=limit, window_seconds=window_seconds
                )
            return 0


def _default_db_path() -> str:
    base = os.getenv("RATE_LIMIT_DB") or ""
    if base.strip():
        return base.strip()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(root, "instance", "rate_limit.db")


def _allow_memory_fallback() -> bool:
    if (os.getenv("ALLOW_MEMORY_RATE_LIMITER") or "").strip() in {"1", "true", "yes"}:
        return True
    if (os.getenv("FLASK_DEBUG") or "0").strip() == "1":
        return True
    if (os.getenv("PYTEST_CURRENT_TEST") or "").strip():
        return True
    return False


def rate_limit_backend() -> str:
    raw = (os.getenv("RATE_LIMIT_BACKEND") or "auto").strip().lower()
    if raw in {"redis", "shared"}:
        return "redis"
    if raw in {"sqlite", "db"}:
        return "sqlite"
    if raw in {"memory", "mem"}:
        return "memory"
    return "auto"


def _redis_fallback_mode() -> str:
    raw = (os.getenv("RATE_LIMIT_REDIS_FALLBACK") or "sqlite").strip().lower()
    if raw in {"deny", "none", "fail", "closed"}:
        return "deny"
    if raw in {"memory", "mem"}:
        return "memory"
    return "sqlite"


def _build_sqlite() -> SqliteRateLimiter:
    return SqliteRateLimiter(_default_db_path())


def _build_fallback_for_redis() -> RateLimiter | None:
    mode = _redis_fallback_mode()
    if mode == "deny":
        return None
    if mode == "memory":
        if _allow_memory_fallback():
            return MemoryRateLimiter()
        logger.warning(
            "RATE_LIMIT_REDIS_FALLBACK=memory blocked in prod; using sqlite fallback"
        )
    try:
        return _build_sqlite()
    except Exception as exc:  # noqa: BLE001
        if _allow_memory_fallback():
            logger.warning("sqlite rate-limit fallback failed (%s); memory", exc)
            return MemoryRateLimiter()
        raise


def build_limiter() -> RateLimiter:
    backend = rate_limit_backend()

    if backend == "memory":
        if not _allow_memory_fallback():
            raise RuntimeError(
                "RATE_LIMIT_BACKEND=memory requires ALLOW_MEMORY_RATE_LIMITER=1 "
                "or FLASK_DEBUG=1"
            )
        return MemoryRateLimiter()

    if backend in {"redis", "auto"}:
        from services.redis_client import get_redis, redis_url

        if backend == "redis" or redis_url():
            client = get_redis(ping=True)
            if client is not None:
                fallback = _build_fallback_for_redis()
                logger.info(
                    "Rate limiter backend=redis prefix=%s fallback=%s",
                    (os.getenv("RATE_LIMIT_REDIS_PREFIX") or "centropic:rl:").strip()
                    or "centropic:rl:",
                    type(fallback).__name__ if fallback else "deny",
                )
                return RedisRateLimiter(client, fallback=fallback)
            if backend == "redis":
                # Explicit redis required — try sqlite only if fallback allows.
                fallback = _build_fallback_for_redis()
                if fallback is not None:
                    logger.warning(
                        "RATE_LIMIT_BACKEND=redis but Redis unavailable; "
                        "using %s fallback",
                        type(fallback).__name__,
                    )
                    return fallback
                raise RuntimeError(
                    "RATE_LIMIT_BACKEND=redis but Redis is unavailable and "
                    "RATE_LIMIT_REDIS_FALLBACK=deny"
                )
            logger.info("Rate limiter auto: Redis unavailable; using sqlite")

    try:
        limiter_impl: RateLimiter = _build_sqlite()
        logger.info("Rate limiter backend=sqlite path=%s", _default_db_path())
        return limiter_impl
    except Exception as exc:
        if _allow_memory_fallback():
            logger.warning(
                "Rate limiter SQLite unavailable (%s); using in-memory fallback",
                exc,
            )
            return MemoryRateLimiter()
        raise RuntimeError(
            f"Rate limiter DB non scrivibile ({_default_db_path()}). "
            "Monta RATE_LIMIT_DB, abilita REDIS_URL, oppure "
            "ALLOW_MEMORY_RATE_LIMITER=1 solo in dev."
        ) from exc


def rebuild_limiter() -> RateLimiter:
    """Rebuild module-level ``limiter`` (tests / after env change)."""
    global limiter
    limiter = build_limiter()
    return limiter


# Keep alias for older imports/tests.
RateLimiterMemory = MemoryRateLimiter

limiter = build_limiter()
