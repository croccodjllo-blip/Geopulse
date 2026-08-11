"""Rate limiter condiviso tra worker Gunicorn (SQLite WAL).

In produzione il fallback in-memory è disabilitato (fail-closed al boot):
con Gunicorn multi-worker i limiti per-processo sono aggirabili.
Dev/test: ALLOW_MEMORY_RATE_LIMITER=1 oppure FLASK_DEBUG=1.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

logger = logging.getLogger(__name__)


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
    # Pytest / unit tests import app with FLASK_DEBUG=1 via conftest; keep explicit.
    if (os.getenv("PYTEST_CURRENT_TEST") or "").strip():
        return True
    return False


def build_limiter() -> MemoryRateLimiter | SqliteRateLimiter:
    path = _default_db_path()
    try:
        return SqliteRateLimiter(path)
    except Exception as exc:
        if _allow_memory_fallback():
            logger.warning(
                "Rate limiter SQLite unavailable (%s); using in-memory fallback",
                exc,
            )
            return MemoryRateLimiter()
        raise RuntimeError(
            f"Rate limiter DB non scrivibile ({path}). "
            "Monta RATE_LIMIT_DB o imposta ALLOW_MEMORY_RATE_LIMITER=1 solo in dev."
        ) from exc


# Alias storico
RateLimiter = MemoryRateLimiter

limiter = build_limiter()
