"""Security fixes H1–H3 / M1–M4: lease debit, redirects, password, welcome gate."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import (
    AnalysisJob,
    CreditLedger,
    User,
    app,
    db,
    ensure_schema,
)
from services.security import password_policy_error, safe_next_url
from services.usage_billing import debit_leased_job_usage, hold_credit


def _user(email: str, *, balance: int = 500) -> User:
    u = User(
        email=email,
        name="T",
        plan="free",
        credit_balance_cents=balance,
        credit_held_cents=0,
        password_hash="x",
        welcome_credit_granted=False,
    )
    u.set_password("SecurePass1!")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    with app.test_client() as c:
        with app.app_context():
            ensure_schema()
        yield c


def test_safe_next_url_blocks_encoded_open_redirects():
    assert safe_next_url("/%2f%2fevil.test") == "/"
    assert safe_next_url("/%2F%2Fevil.test/phish") == "/"
    assert safe_next_url("/%252f%252fevil.test") == "/"
    assert safe_next_url("//evil.test") == "/"
    assert safe_next_url("/dashboard?job=1") == "/dashboard?job=1"


def test_password_policy_requires_letter_and_digit():
    assert password_policy_error("short") is not None
    assert password_policy_error("abcdefghij") is not None  # no digit
    assert password_policy_error("1234567890") is not None  # no letter
    assert password_policy_error("abcdefghij1") is None


def test_debit_leased_job_usage_refuses_stolen_lease():
    with app.app_context():
        ensure_schema()
        u = _user("lease-debit@example.com", balance=500)
        hold_credit(db.session, CreditLedger, u, amount_cents=200, job_id=1)
        db.session.commit()
        job = AnalysisJob(
            user_id=u.id,
            url="https://example.com/lease",
            max_pages=2,
            status="running",
            lease_token="owner-token",
            held_cents=200,
            billed_cents=0,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            heartbeat_at=datetime.now(timezone.utc),
            attempt_count=1,
        )
        db.session.add(job)
        db.session.commit()

        with pytest.raises(RuntimeError, match="lease lost"):
            debit_leased_job_usage(
                db.session,
                CreditLedger,
                AnalysisJob,
                u,
                job,
                lease_token="wrong-token",
                cost_eur_cents=50,
                description="test",
            )
        db.session.rollback()
        db.session.refresh(u)
        assert u.credit_balance_cents == 500


def test_debit_leased_job_usage_atomic_success():
    with app.app_context():
        ensure_schema()
        u = _user("lease-ok@example.com", balance=500)
        hold_credit(db.session, CreditLedger, u, amount_cents=200, job_id=1)
        db.session.commit()
        job = AnalysisJob(
            user_id=u.id,
            url="https://example.com/ok",
            max_pages=2,
            status="running",
            lease_token="good-token",
            held_cents=200,
            billed_cents=0,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            heartbeat_at=datetime.now(timezone.utc),
            attempt_count=1,
        )
        db.session.add(job)
        db.session.commit()

        debit_leased_job_usage(
            db.session,
            CreditLedger,
            AnalysisJob,
            u,
            job,
            lease_token="good-token",
            cost_eur_cents=40,
            description="test ok",
        )
        db.session.commit()
        db.session.refresh(u)
        db.session.refresh(job)
        assert u.credit_balance_cents == 460
        assert job.billed_cents == 40
        assert job.held_cents == 160


def test_register_does_not_grant_welcome_without_verify(client):
    email = "nofarm@example.com"
    resp = client.post(
        "/register",
        data={
            "name": "No Farm",
            "email": email,
            "password": "SecurePass1!",
            "confirm": "SecurePass1!",
            "accept_terms": "y",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        assert u is not None
        assert int(u.credit_balance_cents or 0) == 0
        assert not bool(u.welcome_credit_granted)


def test_register_anti_enumeration(client):
    with app.app_context():
        _user("exists@example.com")
    resp = client.post(
        "/register",
        data={
            "name": "Dup",
            "email": "exists@example.com",
            "password": "SecurePass1!",
            "confirm": "SecurePass1!",
            "accept_terms": "y",
        },
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)
    assert "già registrata" not in body.lower()


def test_verify_email_grants_welcome_once(monkeypatch, client):
    with app.app_context():
        ensure_schema()
        u = _user("verify-me@example.com", balance=0)
        raw = u.issue_verify_token(hours=48)
        db.session.commit()
        uid = u.id

    monkeypatch.setattr("app.mail_configured", lambda: True)
    monkeypatch.setattr("app.WELCOME_CREDIT_CENTS", 200)

    resp = client.get(f"/verify-email/{raw}", follow_redirects=False)
    assert resp.status_code in (302, 303)
    with app.app_context():
        u = db.session.get(User, uid)
        assert u.email_verified_at is not None
        assert bool(u.welcome_credit_granted)
        assert int(u.credit_balance_cents) == 200
    resp2 = client.get(f"/verify-email/{raw}", follow_redirects=False)
    assert resp2.status_code in (302, 303)
    with app.app_context():
        u = db.session.get(User, uid)
        assert int(u.credit_balance_cents) == 200
