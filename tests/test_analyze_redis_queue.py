"""Redis analyze queue + shared LLM RPM."""

from __future__ import annotations

from services.analyze_queue import (
    dispatch_analyze_job,
    pop_batch,
    priority_for_plan,
    queue_backend,
    queue_key_for_priority,
    try_pop_analyze_job,
)
from services.jobs import MAX_RUNNING_ANALYZE_JOBS, claim_next_job, enqueue_analysis
from services.llm_rpm import RedisRpmBucket, reset_buckets_for_tests
from services.redis_client import reset_redis_client_for_tests
from services.sov_load import max_concurrent_measured, should_shed_measured

from app import AnalysisJob, User, app, db, ensure_schema


class _FakeRedis:
    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.published: list[tuple[str, str]] = []

    def ping(self):
        return True

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, str(value))
        return len(self.lists[key])

    def lpop(self, key):
        q = self.lists.get(key) or []
        if not q:
            return None
        return q.pop(0)

    def brpop(self, keys, timeout=0):
        if isinstance(keys, (str, bytes)):
            key_list = [keys]
        else:
            key_list = list(keys)
        for key in key_list:
            val = self.lpop(key)
            if val is not None:
                return (key, val)
        return None

    def llen(self, key):
        return len(self.lists.get(key) or [])

    def publish(self, channel, message):
        self.published.append((channel, str(message)))
        return 1

    def pipeline(self):
        return _FakePipe(self)

    def zrange(self, key, start, end, withscores=False):
        items = sorted((self.zsets.get(key) or {}).items(), key=lambda kv: kv[1])
        sliced = items[start : end + 1] if end >= 0 else items[start:]
        if withscores:
            return [(m, s) for m, s in sliced]
        return [m for m, _ in sliced]

    def zrem(self, key, *members):
        z = self.zsets.setdefault(key, {})
        n = 0
        for m in members:
            if str(m) in z:
                del z[str(m)]
                n += 1
            elif m in z:
                del z[m]
                n += 1
        return n

    def zcard(self, key):
        return len(self.zsets.get(key) or {})

    def zadd(self, key, mapping):
        z = self.zsets.setdefault(key, {})
        z.update({str(k): float(v) for k, v in mapping.items()})
        return len(mapping)

    def zremrangebyscore(self, key, min_s, max_s):
        z = self.zsets.setdefault(key, {})
        drop = [m for m, s in z.items() if s <= max_s]
        for m in drop:
            del z[m]
        return len(drop)

    def expire(self, key, ttl):
        return True


class _FakePipe:
    def __init__(self, r: _FakeRedis):
        self.r = r
        self.ops: list = []

    def zremrangebyscore(self, key, min_s, max_s):
        self.ops.append(("zrem", key, min_s, max_s))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        out = []
        for op in self.ops:
            if op[0] == "zrem":
                _, key, _min_s, max_s = op
                z = self.r.zsets.setdefault(key, {})
                drop = [m for m, s in z.items() if s <= max_s]
                for m in drop:
                    del z[m]
                out.append(len(drop))
            elif op[0] == "zcard":
                out.append(len(self.r.zsets.get(op[1]) or {}))
            elif op[0] == "zadd":
                _, key, mapping = op
                z = self.r.zsets.setdefault(key, {})
                z.update(mapping)
                out.append(len(mapping))
            elif op[0] == "expire":
                out.append(True)
        self.ops.clear()
        return out


import pytest


@pytest.fixture
def fake_redis(monkeypatch):
    reset_redis_client_for_tests()
    reset_buckets_for_tests()
    fake = _FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("ANALYZE_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("LLM_RPM_BACKEND", "redis")
    monkeypatch.setattr("services.redis_client.get_redis", lambda ping=True: fake)
    # analyze_queue imports get_redis from redis_client inside functions
    yield fake
    reset_redis_client_for_tests()
    reset_buckets_for_tests()


def test_queue_backend_redis(monkeypatch):
    monkeypatch.setenv("ANALYZE_QUEUE_BACKEND", "redis")
    assert queue_backend() == "redis"


def test_dispatch_and_pop(fake_redis):
    assert dispatch_analyze_job(42, plan="plus") is True
    assert try_pop_analyze_job() == 42
    assert try_pop_analyze_job() is None


def test_priority_business_before_free(fake_redis):
    assert priority_for_plan("free") == 2
    assert priority_for_plan("plus") == 1
    assert priority_for_plan("business") == 0
    dispatch_analyze_job(10, plan="free")
    dispatch_analyze_job(20, plan="business")
    dispatch_analyze_job(30, plan="plus")
    # Business (p0) wins over Plus (p1) and Free (p2)
    assert try_pop_analyze_job() == 20
    assert try_pop_analyze_job() == 30
    assert try_pop_analyze_job() == 10


def test_pop_batch_drains(fake_redis):
    dispatch_analyze_job(1, plan="plus")
    dispatch_analyze_job(2, plan="plus")
    dispatch_analyze_job(3, plan="plus")
    # Same lane LPUSH prepends → pop order 3,2,1
    batch = pop_batch(2, block_timeout=1)
    assert batch == [3, 2]
    assert try_pop_analyze_job() == 1


def test_enqueue_dispatches_to_redis(fake_redis):
    with app.app_context():
        ensure_schema()
        AnalysisJob.query.filter(
            AnalysisJob.status.in_(("pending", "running"))
        ).update({"status": "error", "error": "isolate"}, synchronize_session=False)
        db.session.commit()
        user = User(email="redis-q@example.com", name="R", plan="plus")
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/redis-q",
            max_pages=2,
            plan="plus",
        )
        assert try_pop_analyze_job() == job.id
        assert queue_key_for_priority(1) in fake_redis.lists


def test_claim_preferred_job_id(fake_redis):
    with app.app_context():
        ensure_schema()
        AnalysisJob.query.filter(
            AnalysisJob.status.in_(("pending", "running"))
        ).update({"status": "error", "error": "isolate"}, synchronize_session=False)
        db.session.commit()
        user = User(email="prefer@example.com", name="P", plan="plus")
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/p1",
            max_pages=1,
            plan="plus",
        )
        j2 = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/p2",
            max_pages=1,
            plan="plus",
        )
        claimed = claim_next_job(db.session, AnalysisJob, preferred_job_id=j2.id)
        assert claimed is not None
        assert claimed.id == j2.id


def test_scale_defaults_target_100():
    assert MAX_RUNNING_ANALYZE_JOBS >= 100 or MAX_RUNNING_ANALYZE_JOBS == 0
    assert max_concurrent_measured() >= 100 or max_concurrent_measured() == 0


def test_measured_shed_by_queue_depth(fake_redis, monkeypatch):
    monkeypatch.setenv("MEASURED_SHED_ENABLE", "1")
    monkeypatch.setenv("MEASURED_SHED_QUEUE_DEPTH", "2")
    monkeypatch.setenv("MAX_CONCURRENT_MEASURED", "100")
    for i in range(3):
        dispatch_analyze_job(100 + i, plan="plus")
    assert should_shed_measured(AnalysisJob=None) is True


def test_redis_rpm_bucket_caps(fake_redis):
    bucket = RedisRpmBucket(2, name="openai", redis_client=fake_redis)
    assert bucket.acquire(block=False) is True
    assert bucket.acquire(block=False) is True
    assert bucket.acquire(block=False) is False
