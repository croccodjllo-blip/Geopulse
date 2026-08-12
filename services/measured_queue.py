"""Dedicated Redis queue + slot semaphore for measured (LLM) SoV jobs.

Crawl/Stimato/pack stay on ``services.analyze_queue`` priority lanes.
Measured follow-ups use::

    centropic:analyze:measured:p0   # Business
    centropic:analyze:measured:p1   # Plus

Enable with the same ``ANALYZE_QUEUE_BACKEND=redis`` + ``REDIS_URL``.
Disable defer with ``MEASURED_DEFER=0`` (measured runs inline again).
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any

logger = logging.getLogger(__name__)

MEASURED_QUEUE_KEY = (
    os.getenv("MEASURED_QUEUE_KEY") or "centropic:analyze:measured"
).strip()
MEASURED_SLOT_KEY = (
    os.getenv("MEASURED_SLOT_KEY") or "centropic:measured:slots"
).strip()
MEASURED_SLOT_HOLD_KEY = (
    os.getenv("MEASURED_SLOT_HOLD_KEY") or "centropic:measured:holds"
).strip()


def measured_defer_enabled() -> bool:
    return os.getenv("MEASURED_DEFER", "1") == "1"


def max_concurrent_measured() -> int:
    return max(0, int(os.getenv("MAX_CONCURRENT_MEASURED", "16")))


def _priority_for_plan(plan: str | None = None, *, is_admin: bool = False) -> int:
    from services.analyze_queue import priority_for_plan

    # Measured is Plus+ only — Free never lands here; map Free→p1 anyway.
    pri = priority_for_plan(plan, is_admin=is_admin)
    return 0 if pri == 0 else 1


def measured_queue_keys() -> list[str]:
    return [
        f"{MEASURED_QUEUE_KEY}:p0",
        f"{MEASURED_QUEUE_KEY}:p1",
    ]


def queue_key_for_plan(plan: str | None = None, *, is_admin: bool = False) -> str:
    pri = _priority_for_plan(plan, is_admin=is_admin)
    return f"{MEASURED_QUEUE_KEY}:p{pri}"


def _client():
    from services.analyze_queue import redis_queue_enabled
    from services.redis_client import get_redis

    if not redis_queue_enabled():
        return None
    return get_redis()


def dispatch_measured_job(
    job_id: int,
    *,
    plan: str | None = None,
    is_admin: bool = False,
) -> bool:
    client = _client()
    if client is None:
        return False
    key = queue_key_for_plan(plan, is_admin=is_admin)
    try:
        client.lpush(key, str(int(job_id)))
        return True
    except Exception:
        logger.exception("dispatch_measured_job failed job_id=%s", job_id)
        return False


def try_pop_measured_job() -> int | None:
    client = _client()
    if client is None:
        return None
    try:
        for key in measured_queue_keys():
            raw = client.lpop(key)
            if raw is not None:
                return int(raw)
        return None
    except Exception:
        logger.exception("try_pop_measured_job failed")
        return None


def pop_measured_job(*, timeout_seconds: float = 1.0) -> int | None:
    client = _client()
    if client is None:
        return None
    try:
        timeout = max(1, int(round(float(timeout_seconds))))
        item = client.brpop(measured_queue_keys(), timeout=timeout)
        if not item:
            return None
        raw = item[1] if isinstance(item, (list, tuple)) else item
        return int(raw)
    except Exception:
        logger.exception("pop_measured_job failed")
        return None


def pop_measured_batch(max_n: int, *, block_timeout: float = 1.0) -> list[int]:
    out: list[int] = []
    n = max(1, int(max_n))
    for _ in range(n):
        jid = try_pop_measured_job()
        if jid is None:
            break
        out.append(jid)
    if out or float(block_timeout) <= 0:
        return out
    jid = pop_measured_job(timeout_seconds=block_timeout)
    if jid is not None:
        out.append(jid)
    return out


def measured_queue_depth() -> int | None:
    client = _client()
    if client is None:
        return None
    try:
        return sum(int(client.llen(k) or 0) for k in measured_queue_keys())
    except Exception:
        return None


def acquire_measured_slot(*, ttl_seconds: int = 3600) -> str | None:
    """Reserve one global measured slot. Returns lease token or None."""
    cap = max_concurrent_measured()
    if cap <= 0:
        return f"unlimited:{secrets.token_hex(4)}"
    client = _client()
    if client is None:
        # No Redis: allow (DB shed still applies via sov_load fallback).
        return f"local:{secrets.token_hex(4)}"
    token = secrets.token_hex(8)
    try:
        # Hold set members expire so crashed workers free slots.
        now = _now_score()
        pipe = client.pipeline()
        pipe.zremrangebyscore(MEASURED_SLOT_HOLD_KEY, 0, now - ttl_seconds)
        pipe.zadd(MEASURED_SLOT_HOLD_KEY, {token: now})
        pipe.zcard(MEASURED_SLOT_HOLD_KEY)
        pipe.expire(MEASURED_SLOT_HOLD_KEY, max(60, ttl_seconds * 2))
        results = pipe.execute()
        active = int(results[2] or 0)
        if active > cap:
            client.zrem(MEASURED_SLOT_HOLD_KEY, token)
            return None
        return token
    except Exception:
        logger.exception("acquire_measured_slot failed")
        return None


def release_measured_slot(token: str | None) -> None:
    if not token or str(token).startswith("unlimited:"):
        return
    if str(token).startswith("local:"):
        return
    client = _client()
    if client is None:
        return
    try:
        client.zrem(MEASURED_SLOT_HOLD_KEY, token)
    except Exception:
        logger.exception("release_measured_slot failed token=%s", token)


def measured_slots_in_use() -> int | None:
    client = _client()
    if client is None:
        return None
    try:
        client.zremrangebyscore(MEASURED_SLOT_HOLD_KEY, 0, _now_score() - 3600)
        return int(client.zcard(MEASURED_SLOT_HOLD_KEY) or 0)
    except Exception:
        return None


def _now_score() -> float:
    import time

    return float(time.time())


def should_shed_for_queue_depth(*, crawl_depth: int | None = None) -> bool:
    """Shed/defer when crawl backlog is high (reuse analyze_queue threshold)."""
    if os.getenv("MEASURED_SHED_ENABLE", "1") != "1":
        return False
    threshold = max(1, int(os.getenv("MEASURED_SHED_QUEUE_DEPTH", "40")))
    if crawl_depth is None:
        try:
            from services.analyze_queue import queue_depth

            crawl_depth = queue_depth()
        except Exception:
            crawl_depth = None
    if crawl_depth is None:
        return False
    return int(crawl_depth) >= threshold
