"""Dedicated measured SoV queue + Redis slot semaphore."""

from __future__ import annotations

from services.jobs import enqueue_analysis
from services.measured_queue import (
    acquire_measured_slot,
    dispatch_measured_job,
    measured_defer_enabled,
    measured_queue_keys,
    release_measured_slot,
    try_pop_measured_job,
)
from services.redis_client import reset_redis_client_for_tests

from app import AnalysisJob, User, app, db, ensure_schema
from tests.test_analyze_redis_queue import _FakeRedis


def test_measured_defer_default_on(monkeypatch):
    monkeypatch.delenv("MEASURED_DEFER", raising=False)
    assert measured_defer_enabled() is True
    monkeypatch.setenv("MEASURED_DEFER", "0")
    assert measured_defer_enabled() is False


def test_measured_queue_priority_and_slots(monkeypatch):
    reset_redis_client_for_tests()
    fake = _FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("ANALYZE_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("MAX_CONCURRENT_MEASURED", "2")
    monkeypatch.setattr("services.redis_client.get_redis", lambda ping=True: fake)

    assert dispatch_measured_job(1, plan="plus") is True
    assert dispatch_measured_job(2, plan="business") is True
    # Business p0 before Plus p1
    assert try_pop_measured_job() == 2
    assert try_pop_measured_job() == 1
    assert set(measured_queue_keys()) == {
        "centropic:analyze:measured:p0",
        "centropic:analyze:measured:p1",
    }

    t1 = acquire_measured_slot()
    t2 = acquire_measured_slot()
    assert t1 and t2
    assert acquire_measured_slot() is None
    release_measured_slot(t1)
    t3 = acquire_measured_slot()
    assert t3 is not None
    release_measured_slot(t2)
    release_measured_slot(t3)
    reset_redis_client_for_tests()


def test_enqueue_measured_source_uses_measured_lane(monkeypatch):
    reset_redis_client_for_tests()
    fake = _FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("ANALYZE_QUEUE_BACKEND", "redis")
    monkeypatch.setattr("services.redis_client.get_redis", lambda ping=True: fake)

    with app.app_context():
        ensure_schema()
        user = User(email="meas-q@example.com", name="M", plan="plus")
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/meas",
            max_pages=1,
            run_measured=True,
            source="measured",
            plan="plus",
        )
        assert try_pop_measured_job() == job.id
    reset_redis_client_for_tests()
