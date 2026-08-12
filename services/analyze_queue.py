"""Redis LIST dispatch for analyze jobs (DB remains source of truth).

Enable with::

    REDIS_URL=redis://127.0.0.1:6379/0
    ANALYZE_QUEUE_BACKEND=redis

Priority lanes (BRPOP order)::

    p0  Business / admin
    p1  Plus
    p2  Free / anonymous
    legacy single list (ANALYZE_QUEUE_KEY) drained last for back-compat

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


def priority_for_plan(plan: str | None = None, *, is_admin: bool = False) -> int:
    """0 = highest (Business), 1 = Plus, 2 = Free."""
    if is_admin:
        return 0
    raw = (plan or "free").strip().lower()
    if raw in {"business", "admin"}:
        return 0
    if raw in {"plus", "pro"}:
        return 1
    return 2


def queue_key_for_priority(priority: int) -> str:
    pri = max(0, min(2, int(priority)))
    return f"{QUEUE_KEY}:p{pri}"


def priority_queue_keys() -> list[str]:
    """BRPOP / depth order: p0 → p1 → p2 → legacy flat key."""
    return [
        queue_key_for_priority(0),
        queue_key_for_priority(1),
        queue_key_for_priority(2),
        QUEUE_KEY,
    ]


def dispatch_analyze_job(
    job_id: int,
    *,
    plan: str | None = None,
    priority: int | None = None,
    is_admin: bool = False,
) -> bool:
    """Push ``job_id`` onto the plan priority Redis list."""
    if queue_backend() != "redis":
        return False
    from services.redis_client import get_redis

    client = get_redis()
    if client is None:
        return False
    pri = (
        int(priority)
        if priority is not None
        else priority_for_plan(plan, is_admin=is_admin)
    )
    key = queue_key_for_priority(pri)
    try:
        client.lpush(key, str(int(job_id)))
        try:
            client.publish(NOTIFY_CHANNEL, str(int(job_id)))
        except Exception:  # noqa: BLE001
            pass
        return True
    except Exception:
        logger.exception("dispatch_analyze_job failed job_id=%s", job_id)
        return False


def pop_analyze_job(*, timeout_seconds: float = 2.0) -> int | None:
    """Blocking pop preferring Business → Plus → Free → legacy."""
    if queue_backend() != "redis":
        return None
    from services.redis_client import get_redis

    client = get_redis()
    if client is None:
        return None
    try:
        timeout = max(1, int(round(float(timeout_seconds))))
        keys = priority_queue_keys()
        item = client.brpop(keys, timeout=timeout)
        if not item:
            return None
        raw = item[1] if isinstance(item, (list, tuple)) else item
        return int(raw)
    except Exception:
        logger.exception("pop_analyze_job failed")
        return None


def try_pop_analyze_job() -> int | None:
    """Non-blocking pop across priority lanes."""
    if queue_backend() != "redis":
        return None
    from services.redis_client import get_redis

    client = get_redis()
    if client is None:
        return None
    try:
        for key in priority_queue_keys():
            raw = client.lpop(key)
            if raw is not None:
                return int(raw)
        return None
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
    """Total pending ids across all priority lanes (incl. legacy)."""
    from services.redis_client import get_redis

    client = get_redis(ping=False)
    if client is None:
        return None
    try:
        total = 0
        for key in priority_queue_keys():
            total += int(client.llen(key) or 0)
        return total
    except Exception:
        return None


def queue_depth_by_priority() -> dict[str, int] | None:
    from services.redis_client import get_redis

    client = get_redis(ping=False)
    if client is None:
        return None
    try:
        out: dict[str, int] = {}
        for key in priority_queue_keys():
            out[key] = int(client.llen(key) or 0)
        return out
    except Exception:
        return None


def requeue_pending_jobs(
    job_ids: list[int],
    *,
    plan: str | None = None,
    priority: int | None = None,
) -> int:
    """Re-dispatch pending ids (safety net after Redis flush)."""
    n = 0
    for jid in job_ids:
        if dispatch_analyze_job(int(jid), plan=plan, priority=priority):
            n += 1
    return n


def measured_shed_due_to_queue(*, depth: int | None = None) -> bool:
    """True when analyze backlog is high enough to skip measured SoV."""
    if os.getenv("MEASURED_SHED_ENABLE", "1") != "1":
        return False
    threshold = max(1, int(os.getenv("MEASURED_SHED_QUEUE_DEPTH", "40")))
    if depth is None:
        depth = queue_depth()
    if depth is None:
        return False
    return int(depth) >= threshold
