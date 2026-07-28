from __future__ import annotations

import os
import tempfile

from services.rate_limit import SqliteRateLimiter


def test_sqlite_limiter_shared_budget():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rl.db")
        a = SqliteRateLimiter(path)
        b = SqliteRateLimiter(path)
        assert a.allow("k", limit=2, window_seconds=60) is True
        assert b.allow("k", limit=2, window_seconds=60) is True
        assert a.allow("k", limit=2, window_seconds=60) is False
        assert b.remaining("k", limit=2, window_seconds=60) == 0
