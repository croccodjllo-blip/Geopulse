from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import AnalysisJob, CreditLedger, User, app, db, ensure_schema
from services.jobs import claim_next_job, complete_job, fail_job, heartbeat_job, reclaim_stale_jobs
from services.usage_billing import (
    get_balance_cents,
    hold_credit,
    release_hold,
    consume_hold,
)


def _user(email: str) -> User:
    u = User(email=email, name="T", plan="free", credit_balance_cents=1000, credit_held_cents=0)
    u.set_password("x" * 12)
    db.session.add(u)
    db.session.commit()
    return u


def test_fail_job_does_not_overwrite_done():
    with app.app_context():
        ensure_schema()
        u = _user("fail-done@example.com")
        from services.jobs import enqueue_analysis

        job = enqueue_analysis(
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


def test_heartbeat_prevents_reclaim():
    with app.app_context():
        ensure_schema()
        u = _user("hb@example.com")
        from services.jobs import enqueue_analysis

        job = enqueue_analysis(
            db.session, AnalysisJob, user_id=u.id, url="https://example.com/hb", max_pages=2
        )
        claimed = claim_next_job(db.session, AnalysisJob)
        assert claimed is not None
        assert heartbeat_job(db.session, claimed) is True
        # Force started_at old but heartbeat fresh
        claimed.started_at = datetime.now(timezone.utc) - timedelta(minutes=40)
        db.session.commit()
        n = reclaim_stale_jobs(db.session, AnalysisJob, older_than_minutes=12)
        assert n == 0
        db.session.refresh(claimed)
        assert claimed.status == "running"


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
