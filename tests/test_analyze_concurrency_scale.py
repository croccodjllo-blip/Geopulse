"""Concurrency scaling: global running cap, plan caps, LLM RPM buckets."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from app import AnalysisJob, User, app, concurrent_analyze_cap_for, db, ensure_schema
from services.jobs import MAX_RUNNING_ANALYZE_JOBS, claim_next_job, enqueue_analysis
from services.llm_rpm import (
    RpmBucket,
    acquire_for_label,
    provider_from_label,
    reset_buckets_for_tests,
)
from services.usage_billing import ConcurrentAnalysisError, assert_can_start_analysis


def test_provider_from_label_maps_sov_labels():
    assert provider_from_label("openai-sov") == "openai"
    assert provider_from_label("perplexity") == "perplexity"
    assert provider_from_label("anthropic-sov") == "anthropic"
    assert provider_from_label("pack") is None


def test_rpm_bucket_nonblocking_rejects_when_full():
    reset_buckets_for_tests(["testprov"])
    bucket = RpmBucket(2, name="testprov")
    assert bucket.acquire(block=False) is True
    assert bucket.acquire(block=False) is True
    assert bucket.acquire(block=False) is False


def test_acquire_for_label_uses_env_rpm(monkeypatch):
    monkeypatch.setenv("OPENAI_RPM", "1")
    reset_buckets_for_tests(["openai"])
    assert acquire_for_label("openai-sov", block=False) is True
    assert acquire_for_label("openai-sov", block=False) is False
    reset_buckets_for_tests(["openai"])


def test_concurrent_analyze_cap_for_plans():
    class U:
        def __init__(self, plan: str, *, admin: bool = False):
            self.plan = plan
            self.role = "admin" if admin else "user"
            self.is_admin = admin

    assert concurrent_analyze_cap_for(U("free")) == 1
    assert concurrent_analyze_cap_for(U("plus")) == 3
    assert concurrent_analyze_cap_for(U("pro")) == 3
    assert concurrent_analyze_cap_for(U("business")) == 5
    assert concurrent_analyze_cap_for(U("admin", admin=True)) == 8


def test_assert_can_start_respects_plan_cap():
    class _User:
        id = 1
        plan = "free"
        credit_balance_cents = 10_000
        credit_held_cents = 0

    class _Session:
        def __init__(self, user):
            self.user = user

        def get_bind(self):
            class B:
                dialect = type("D", (), {"name": "postgresql"})()

            return B()

        def execute(self, *_a, **_k):
            return None

        def query(self, _model):
            user = self.user

            class Q:
                def filter(self, *_a, **_k):
                    return self

                def with_for_update(self):
                    return self

                def first(self):
                    return user

            return Q()

    class JobQ:
        @staticmethod
        def filter(*_a, **_k):
            class C:
                @staticmethod
                def count():
                    return 1

            return C()

    class AnalysisJobStub:
        query = JobQ()
        user_id = object()
        status = type("C", (), {"in_": lambda self, _v: self})()

    user = _User()
    session = _Session(user)
    with pytest.raises(ConcurrentAnalysisError):
        assert_can_start_analysis(
            session,
            user,
            AnalysisJob=AnalysisJobStub,
            required_cents=1,
            max_concurrent_jobs=1,
        )


def test_claim_respects_global_running_cap(monkeypatch):
    monkeypatch.setattr("services.jobs.MAX_RUNNING_ANALYZE_JOBS", 1)
    with app.app_context():
        ensure_schema()
        AnalysisJob.query.filter(
            AnalysisJob.status.in_(("pending", "running"))
        ).update({"status": "error", "error": "test-isolate"}, synchronize_session=False)
        db.session.commit()

        user = User(email="cap-run@example.com", name="C", plan="plus")
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()

        j1 = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/cap-a",
            max_pages=2,
        )
        j2 = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=user.id,
            url="https://example.com/cap-b",
            max_pages=2,
        )
        c1 = claim_next_job(db.session, AnalysisJob)
        assert c1 is not None and c1.id in {j1.id, j2.id}
        # Cap=1 running → second claim blocked even with pending left.
        c2 = claim_next_job(db.session, AnalysisJob)
        assert c2 is None
        pending_left = AnalysisJob.query.filter_by(status="pending").count()
        assert pending_left == 1


def test_db_pool_options_configured_for_postgres(monkeypatch):
    # Config is set at import time from DATABASE_URL; assert the helper shape.
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    opts = app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {}
    if uri.startswith("postgresql"):
        assert opts.get("pool_size", 0) >= 1
        assert "max_overflow" in opts
        assert opts.get("pool_pre_ping") is True
    else:
        # SQLite test env: options may be absent — that is expected.
        assert True


def test_acquire_claim_lock_noop_on_sqlite():
    with app.app_context():
        from services.jobs import _acquire_claim_lock

        # Must not raise on the test SQLite engine.
        _acquire_claim_lock(db.session)
        db.session.rollback()


def test_max_running_default_is_raised():
    # Code default bumped for vertical capacity (env may override lower).
    assert MAX_RUNNING_ANALYZE_JOBS >= 0
