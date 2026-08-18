"""Rate limiter backends: SQLite host-local + Redis shared."""

from __future__ import annotations

import os
import tempfile

from services.rate_limit import (
    MemoryRateLimiter,
    RedisRateLimiter,
    SqliteRateLimiter,
    rate_limit_backend,
)
from services.redis_client import reset_redis_client_for_tests


class _FakeRedis:
    """Minimal sorted-set + EVAL stub for RedisRateLimiter unit tests."""

    def __init__(self) -> None:
        self._z: dict[str, dict[str, float]] = {}

    def eval(self, script: str, numkeys: int, *args: object) -> int:
        assert numkeys == 1
        key = str(args[0])
        now = float(args[1])
        cutoff = float(args[2])
        limit = int(args[3])
        member = str(args[4])
        ttl = int(args[5])  # noqa: F841 — expire tracked loosely
        z = self._z.setdefault(key, {})
        for m, score in list(z.items()):
            if score < cutoff:
                del z[m]
        if len(z) >= limit:
            return 0
        z[member] = now
        return 1

    def pipeline(self) -> "_FakePipe":
        return _FakePipe(self)

    def zremrangebyscore(self, key: str, _min: object, cutoff: object) -> int:
        z = self._z.get(key) or {}
        cut = float(cutoff)
        removed = 0
        for m, score in list(z.items()):
            if score <= cut:
                del z[m]
                removed += 1
        self._z[key] = z
        return removed

    def zcard(self, key: str) -> int:
        return len(self._z.get(key) or {})

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        z = self._z.setdefault(key, {})
        z.update({str(k): float(v) for k, v in mapping.items()})
        return len(mapping)

    def expire(self, key: str, _ttl: int) -> bool:
        return True


class _FakePipe:
    def __init__(self, r: _FakeRedis) -> None:
        self._r = r
        self._ops: list[tuple] = []

    def zremrangebyscore(self, key: str, mn: object, cutoff: object) -> "_FakePipe":
        self._ops.append(("zrem", key, mn, cutoff))
        return self

    def zcard(self, key: str) -> "_FakePipe":
        self._ops.append(("zcard", key))
        return self

    def zadd(self, key: str, mapping: dict[str, float]) -> "_FakePipe":
        self._ops.append(("zadd", key, mapping))
        return self

    def expire(self, key: str, ttl: int) -> "_FakePipe":
        self._ops.append(("expire", key, ttl))
        return self

    def execute(self) -> list[object]:
        out: list[object] = []
        for op in self._ops:
            if op[0] == "zrem":
                out.append(self._r.zremrangebyscore(op[1], op[2], op[3]))
            elif op[0] == "zcard":
                out.append(self._r.zcard(op[1]))
            elif op[0] == "zadd":
                out.append(self._r.zadd(op[1], op[2]))
            elif op[0] == "expire":
                out.append(self._r.expire(op[1], op[2]))
        self._ops.clear()
        return out


def test_sqlite_limiter_shared_budget():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rl.db")
        a = SqliteRateLimiter(path)
        b = SqliteRateLimiter(path)
        assert a.allow("k", limit=2, window_seconds=60) is True
        assert b.allow("k", limit=2, window_seconds=60) is True
        assert a.allow("k", limit=2, window_seconds=60) is False
        assert b.remaining("k", limit=2, window_seconds=60) == 0


def test_redis_limiter_shared_budget():
    fake = _FakeRedis()
    a = RedisRateLimiter(fake, key_prefix="test:rl:")
    b = RedisRateLimiter(fake, key_prefix="test:rl:")
    assert a.allow("login:1", limit=2, window_seconds=60) is True
    assert b.allow("login:1", limit=2, window_seconds=60) is True
    assert a.allow("login:1", limit=2, window_seconds=60) is False
    assert b.remaining("login:1", limit=2, window_seconds=60) == 0


def test_redis_limiter_falls_back_on_error():
    class Boom:
        def eval(self, *_a, **_k):
            raise RuntimeError("redis down")

    mem = MemoryRateLimiter()
    lim = RedisRateLimiter(Boom(), fallback=mem)
    assert lim.allow("x", limit=1, window_seconds=60) is True
    assert lim.allow("x", limit=1, window_seconds=60) is False


def test_redis_limiter_fail_closed_without_fallback():
    class Boom:
        def eval(self, *_a, **_k):
            raise RuntimeError("redis down")

    lim = RedisRateLimiter(Boom(), fallback=None)
    assert lim.allow("x", limit=100, window_seconds=60) is False


def test_build_limiter_auto_prefers_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "auto")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/15")
    monkeypatch.setenv("ALLOW_MEMORY_RATE_LIMITER", "1")
    reset_redis_client_for_tests()

    monkeypatch.setattr("services.redis_client.get_redis", lambda *, ping=True: fake)
    monkeypatch.setattr("services.redis_client.redis_url", lambda: "redis://x")

    import services.rate_limit as rl

    lim = rl.build_limiter()
    assert isinstance(lim, RedisRateLimiter)
    assert lim.allow("auto-k", limit=1, window_seconds=30) is True
    assert lim.allow("auto-k", limit=1, window_seconds=30) is False


def test_rate_limit_backend_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    assert rate_limit_backend() == "redis"
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "sqlite")
    assert rate_limit_backend() == "sqlite"
