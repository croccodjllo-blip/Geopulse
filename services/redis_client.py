"""Shared Redis client for analyze queue + LLM RPM (optional)."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_CLIENT: Any | None = None
_CLIENT_FAILED = False


def redis_url() -> str:
    return (os.getenv("REDIS_URL") or "").strip()


def redis_enabled() -> bool:
    return bool(redis_url())


def get_redis(*, ping: bool = True) -> Any | None:
    """Return a Redis client or None when disabled/unavailable."""
    global _CLIENT, _CLIENT_FAILED
    url = redis_url()
    if not url:
        return None
    if _CLIENT_FAILED and _CLIENT is None:
        return None
    if _CLIENT is not None:
        return _CLIENT
    try:
        import redis as redis_lib
    except ImportError:
        logger.warning("redis package not installed; REDIS_URL ignored")
        _CLIENT_FAILED = True
        return None
    try:
        client = redis_lib.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
            health_check_interval=30,
        )
        if ping:
            client.ping()
        _CLIENT = client
        _CLIENT_FAILED = False
        return _CLIENT
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis unavailable (%s): %s", url.split("@")[-1], exc)
        _CLIENT_FAILED = True
        _CLIENT = None
        return None


def reset_redis_client_for_tests() -> None:
    global _CLIENT, _CLIENT_FAILED
    _CLIENT = None
    _CLIENT_FAILED = False
