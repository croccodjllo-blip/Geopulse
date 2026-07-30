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


def test_release_hold_race_does_not_zero_all_holds(monkeypatch):
    """H3: concurrent release must not clamp unrelated holds to 0."""
    with app.app_context():
        ensure_schema()
        u = _user("race-hold@example.com", balance=1000)
        hold_credit(db.session, CreditLedger, u, amount_cents=300, job_id=1)
        db.session.commit()
        # DB holds 50 (other job still reserved); stale caller still thinks 200.
        u.credit_held_cents = 50
        db.session.commit()
        monkeypatch.setattr(
            "services.usage_billing.get_held_cents",
            lambda _user: 200,
        )
        released = release_hold(db.session, u, amount_cents=200)
        db.session.commit()
        db.session.refresh(u)
        assert released == 0
        assert u.credit_held_cents == 50


def test_deduct_credit_respects_other_job_holds():
    """H4: cannot spend into another job's reserved hold."""
    from services.usage_billing import deduct_credit

    with app.app_context():
        ensure_schema()
        u = _user("deduct-hold@example.com", balance=200)
        hold_credit(db.session, CreditLedger, u, amount_cents=150, job_id=1)
        db.session.commit()
        db.session.refresh(u)
        # Spendable is 50; without reserved_cents, deduct 100 must fail.
        try:
            deduct_credit(
                db.session,
                CreditLedger,
                u,
                analysis_run_id=None,
                cost_eur_cents=100,
                reserved_cents=0,
            )
            assert False, "expected InsufficientCreditError"
        except InsufficientCreditError:
            pass
        db.session.refresh(u)
        assert u.credit_balance_cents == 200
        # Same debit allowed when this job's hold covers it.
        deduct_credit(
            db.session,
            CreditLedger,
            u,
            analysis_run_id=None,
            cost_eur_cents=100,
            reserved_cents=150,
        )
        db.session.commit()
        db.session.refresh(u)
        assert u.credit_balance_cents == 100


def test_soft_reclaim_fails_when_partially_billed():
    """H2: soft reclaim must not re-queue jobs that already billed."""
    with app.app_context():
        ensure_schema()
        u = _user("billed-reclaim@example.com", balance=500)
        hold_credit(db.session, CreditLedger, u, amount_cents=200, job_id=1)
        db.session.commit()
        from services.jobs import enqueue_analysis

        job = enqueue_analysis(
            db.session,
            AnalysisJob,
            user_id=u.id,
            url="https://example.com/billed",
            max_pages=2,
            held_cents=200,
        )
        job.status = "running"
        job.attempt_count = 1
        job.billed_cents = 40
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
        db.session.refresh(job)
        db.session.refresh(u)
        assert job.status == "error"
        assert job.held_cents == 0
        assert u.credit_held_cents == 0
        assert "doppia fatturazione" in (job.error or "").lower() or "parziale" in (
            job.error or ""
        ).lower()


def test_has_sufficient_credit_for_job_counts_hold():
    """H1: worker preflight treats this job's hold as available."""
    from services.usage_billing import (
        CostEstimate,
        has_sufficient_credit,
        has_sufficient_credit_for_job,
    )

    with app.app_context():
        ensure_schema()
        u = _user("job-credit@example.com", balance=200)
        hold_credit(db.session, CreditLedger, u, amount_cents=180, job_id=1)
        db.session.commit()
        db.session.refresh(u)
        est = CostEstimate(
            raw_cost_usd_micro=0.0,
            service_cost_usd_micro=0.0,
            service_cost_eur_cents=100,
        )
        assert has_sufficient_credit(u, est) is False
        assert has_sufficient_credit_for_job(u, est, reserved_cents=180) is True
