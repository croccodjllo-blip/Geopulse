"""Regression: SoV usage debit must survive running from a worker thread.

Citation probes for measured Share of Voice run in a ThreadPoolExecutor
(services/citation_monitor.py). Each engine's usage callback re-enters
``app.app_context()`` from that worker thread, which — under Flask-
SQLAlchemy's default thread-local scoped session — hands back a *different*
``db.session`` than the one that originally loaded the ``User``/``AnalysisJob``
row on the analyze worker's own thread. Passing that stale, cross-session
instance into ``session.refresh()`` (inside ``deduct_credit``) blows up with
``InvalidRequestError: Instance ... is not persistent within this Session``,
which aborted live analyze jobs in production (see job usage debit failures).

The fix (app.py ``_job_usage_cb``) re-fetches the user via
``db.session.get(User, user.id)`` after entering the callback's own app
context. This test reproduces the failure mode directly against
``debit_leased_job_usage`` and proves the re-fetch pattern fixes it.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import InvalidRequestError

from app import AnalysisJob, CreditLedger, User, app, db, ensure_schema
from services.usage_billing import debit_leased_job_usage, hold_credit


def _make_user_and_job(email: str) -> tuple[int, int]:
    with app.app_context():
        ensure_schema()
        u = User(
            email=email,
            name="T",
            plan="plus",
            credit_balance_cents=1000,
            credit_held_cents=0,
            password_hash="x",
        )
        u.set_password("SecurePass1!")
        db.session.add(u)
        db.session.commit()
        hold_credit(db.session, CreditLedger, u, amount_cents=200, job_id=1)
        job = AnalysisJob(
            user_id=u.id,
            url="https://example.com/cross-thread",
            max_pages=2,
            status="running",
            lease_token="worker-token",
            held_cents=200,
            billed_cents=0,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            heartbeat_at=datetime.now(timezone.utc),
            attempt_count=1,
        )
        db.session.add(job)
        db.session.commit()
        return u.id, job.id


def test_stale_cross_session_user_raises_invalid_request_error():
    """Documents the exact production failure: no re-fetch -> broken session."""
    user_id, job_id = _make_user_and_job("cross-thread-bug@example.com")

    with app.app_context():
        ensure_schema()
        stale_user = db.session.get(User, user_id)

    outcome: dict[str, BaseException | None] = {"exc": None}

    def _worker() -> None:
        with app.app_context():
            job = db.session.get(AnalysisJob, job_id)
            try:
                debit_leased_job_usage(
                    db.session,
                    CreditLedger,
                    AnalysisJob,
                    stale_user,  # loaded on a different thread's session
                    job,
                    lease_token="worker-token",
                    cost_eur_cents=50,
                    description="test",
                )
            except BaseException as exc:  # noqa: BLE001
                outcome["exc"] = exc

    t = threading.Thread(target=_worker)
    t.start()
    t.join(timeout=10)

    assert isinstance(outcome["exc"], InvalidRequestError)
    assert "not persistent" in str(outcome["exc"])


def test_refetching_user_in_worker_thread_fixes_debit():
    """The applied fix: db.session.get(User, user.id) inside the new context."""
    user_id, job_id = _make_user_and_job("cross-thread-fixed@example.com")

    outcome: dict[str, object] = {"exc": None, "debited": None}

    def _worker() -> None:
        with app.app_context():
            thread_user = db.session.get(User, user_id)
            job = db.session.get(AnalysisJob, job_id)
            try:
                outcome["debited"] = debit_leased_job_usage(
                    db.session,
                    CreditLedger,
                    AnalysisJob,
                    thread_user,
                    job,
                    lease_token="worker-token",
                    cost_eur_cents=50,
                    description="test",
                )
                db.session.commit()
            except BaseException as exc:  # noqa: BLE001
                outcome["exc"] = exc

    t = threading.Thread(target=_worker)
    t.start()
    t.join(timeout=10)

    assert outcome["exc"] is None
    assert outcome["debited"] == 50
    with app.app_context():
        refreshed = db.session.get(User, user_id)
        assert refreshed.credit_balance_cents == 950
