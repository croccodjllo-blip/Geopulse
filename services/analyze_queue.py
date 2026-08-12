"""Redis LIST dispatch for analyze jobs (DB remains source of truth).

Enable with::

    REDIS_URL=redis://127.0.0.1:6379/0
    ANALYZE_QUEUE_BACKEND=redis

When disabled, workers keep claiming via Postgres FIFO only.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

QUEUE_KEY = (os.getenv("ANALYZE_QUEUE_KEY") or "centropic:analyze:queue").strip()
NOTIFY_CHANNEL = (os.getenv("ANALYZE_QUEUE_NOTIFY") or "centropic:analyze:notify").strip()


def queue_backend() -> str:
    raw = (os.getenv("ANALYZE_QUEUE_BACKEND") or "db").strip().lower()
    if raw in {"redis", "list", "rq"}:
        return "redis"
    return "db"


def redis_queue_enabled() -> bool:
    if queue_backend() != "redis":
        return False
    from services.redis_client import get_redis

    return get_redis(ping=False) is not None or bool(
        (os.getenv("REDIS_URL") or "").strip()
    )


def dispatch_analyze_job(job_id: int) -> bool:
    """Push ``job_id`` onto the Redis list. Returns True if dispatched."""
    if queue_backend() != "redis":
        return False
    from services.redis_client import get_redis

    client = get_redis()
    if client is None:
        return False
    try:
        client.lpush(QUEUE_KEY, str(int(job_id)))
        try:
            client.publish(NOTIFY_CHANNEL, str(int(job_id)))
        except Exception:  # noqa: BLE001
            pass
        return True
    except Exception:
        logger.exception("dispatch_analyze_job failed job_id=%s", job_id)
        return False


def pop_analyze_job(*, timeout_seconds: float = 2.0) -> int | None:
    """Blocking pop of next job id. None on idle timeout / Redis down."""
    if queue_backend() != "redis":
        return None
    from services.redis_client import get_redis

    client = get_redis()
    if client is None:
        return None
    try:
        timeout = max(1, int(round(float(timeout_seconds))))
        item = client.brpop(QUEUE_KEY, timeout=timeout)
        if not item:
            return None
        # brpop → (key, value)
        raw = item[1] if isinstance(item, (list, tuple)) else item
        return int(raw)
    except Exception:
        logger.exception("pop_analyze_job failed")
        return None


def try_pop_analyze_job() -> int | None:
    """Non-blocking pop (LPOP)."""
    if queue_backend() != "redis":
        return None
    from services.redis_client import get_redis

    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.lpop(QUEUE_KEY)
        if raw is None:
            return None
        return int(raw)
    except Exception:
        logger.exception("try_pop_analyze_job failed")
        return None


def pop_batch(max_n: int, *, block_timeout: float = 2.0) -> list[int]:
    """Collect up to ``max_n`` ids: drain with LPOP, then one BRPOP if empty."""
    out: list[int] = []
    n = max(1, int(max_n))
    for _ in range(n):
        jid = try_pop_analyze_job()
        if jid is None:
            break
        out.append(jid)
    if out:
        return out
    jid = pop_analyze_job(timeout_seconds=block_timeout)
    if jid is not None:
        out.append(jid)
    return out


def queue_depth() -> int | None:
    from services.redis_client import get_redis

    client = get_redis(ping=False)
    if client is None:
        return None
    try:
        return int(client.llen(QUEUE_KEY))
    except Exception:
        return None


def requeue_pending_jobs(job_ids: list[int]) -> int:
    """Re-dispatch pending ids (safety net after Redis flush)."""
    n = 0
    for jid in job_ids:
        if dispatch_analyze_job(int(jid)):
            n += 1
    return n
