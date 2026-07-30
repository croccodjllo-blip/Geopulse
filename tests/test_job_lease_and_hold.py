from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import AnalysisJob, CreditLedger, User, app, db, ensure_schema
from services.jobs import (
    claim_next_job,
    complete_job,
    fail_job,
    heartbeat_job,
    reclaim_stale_jobs,
)
from services.usage_billing import (
    InsufficientCreditError,
    get_balance_cents,
    hold_credit,
    release_hold,
    consume_hold,
    release_job_hold,
)


def _user(email: str, balance: int = 1000) -> User:
    u = User(
        email=email,
        name="T",
        plan="free",
        credit_balance_cents=balance,
        credit_held_cents=0,
    )
    u.set_password("x" * 12)
    db.session.add(u)
    db.session.commit()
    return u


def test_fail_job_does_not_overwrite_done():
    with app.app_context():
        ensure_schema()
        u = _user("fail-done@example.com")
        from services.jobs import enqueue_analysis

        enqueue_analysis(
            db.session, AnalysisJob, user_id=u.id, url="https://example.com/x", max_pages=2
        )
        claimed = claim_next_job(db.session, AnalysisJob)
        assert claimed is not None
        assert complete_job(db.session, claimed, site_id=None) is True
        db.session.refresh(claimed)
        assert claimed.status == "done"
        assert fail_job(db.session, claimed, "boom") is False
        db.session.refresh(claimed)
        assert claimed.status == "done"


def test_complete_job_requires_lease():
    with app.app_context():
        ensure_schema()
        u = _user("lease-complete@example.com")
        from services.jobs import enqueue_analysis

        enqueue_analysis(
            db.session, AnalysisJob, user_id=u.id, url="https://example.com/lease", max_pages=2
        )
        claimed = claim_next_job(db.session, AnalysisJob)
        assert claimed is not None
        # Simulate reclaim stealing the lease
        claimed.lease_token = None
        db.session.commit()
        assert complete_job(db.session, claimed, site_id=None) is False
        db.session.refresh(claimed)
        assert claimed.status == "running"


def test_zombie_complete_loses_to_new_lease():
    with app.app_context():
        ensure_schema()
        u = _user("zombie@example.com")
        from services.jobs import enqueue_analysis

        enqueue_analysis(
            db.session, AnalysisJob, user_id=u.id, url="https://example.com/z", max_pages=2
        )
        first = claim_next_job(db.session, AnalysisJob)
        assert first is not None
        old_lease = first.lease_token
        # Soft-reclaim then re-claim
        first.status = "pending"
        first.lease_token = None
        first.started_at = None
        db.session.commit()
        second = claim_next_job(db.session, AnalysisJob)
        assert second is not None
        assert second.lease_token != old_lease
        # Zombie tries to complete with the old lease token
        assert complete_job(db.session, second, site_id=None, lease_token=old_lease) is False
        db.session.refresh(second)
        assert second.status == "running"
        assert complete_job(db.session, second, site_id=None) is True


def test_heartbeat_prevents_reclaim():
    with app.app_context():
        ensure_schema()
        u = _user("hb@example.com")
        from services.jobs import enqueue_analysis

        enqueue_analysis(
            db.session, AnalysisJob, user_id=u.id, url="https://example.com/hb", max_pages=2
        )
        claimed = claim_next_job(db.session, AnalysisJob)
        assert claimed is not None
        assert heartbeat_job(db.session, claimed) is True
        claimed.started_at = datetime.now(timezone.utc) - timedelta(minutes=40)
        db.session.commit()
        n = reclaim_stale_jobs(db.session, AnalysisJob, older_than_minutes=12)
        assert n == 0
        db.session.refresh(claimed)
        assert claimed.status == "running"


def test_abandon_releases_hold_via_callback():
    with app.app_context():
        ensure_schema()
        u = _user("abandon@example.com", balance=500)
        from services.jobs import enqueue_analysis
        from services.jobs import MAX_JOB_ATTEMPTS

        hold_credit(db.session, CreditLedger, u, amount_cents=200, job_id=1)
        db.session.commit()
        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=u.id,
            url="https://example.com/abandon",
            max_pages=2,
            held_cents=200,
        )
        job.status = "running"
        job.attempt_count = MAX_JOB_ATTEMPTS
        job.started_at = datetime.now(timezone.utc) - timedelta(minutes=40)
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=40)
        db.session.commit()

        def on_abandon(j):
            owner = db.session.get(User, j.user_id)
            release_job_hold(db.session, owner, j)

        n = reclaim_stale_jobs(
            db.session, AnalysisJob, older_than_minutes=12, on_abandon=on_abandon
        )
        assert n == 1
        db.session.refresh(u)
        db.session.refresh(job)
        assert job.status == "error"
        assert job.held_cents == 0
        assert u.credit_held_cents == 0
        assert get_balance_cents(u) == 500


def test_hold_and_release_credit():
    with app.app_context():
        ensure_schema()
        u = _user("hold@example.com")
        assert get_balance_cents(u) == 1000
        held = hold_credit(db.session, CreditLedger, u, amount_cents=250, job_id=1)
        db.session.commit()
        db.session.refresh(u)
        assert held == 250
        assert get_balance_cents(u) == 750
        consume_hold(db.session, u, amount_cents=100)
        db.session.commit()
        db.session.refresh(u)
        assert u.credit_held_cents == 150
        release_hold(db.session, u, amount_cents=150)
        db.session.commit()
        db.session.refresh(u)
        assert u.credit_held_cents == 0
        assert get_balance_cents(u) == 1000


def test_hold_credit_rejects_over_reserve():
    with app.app_context():
        ensure_schema()
        u = _user("overhold@example.com", balance=100)
        hold_credit(db.session, CreditLedger, u, amount_cents=80, job_id=1)
        db.session.commit()
        db.session.refresh(u)
        try:
            hold_credit(db.session, CreditLedger, u, amount_cents=50, job_id=2)
            assert False, "expected InsufficientCreditError"
        except InsufficientCreditError:
            pass
        db.session.refresh(u)
        assert u.credit_held_cents == 80
