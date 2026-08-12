"""Referral bonus grants only when the invitee activates Plus."""

from __future__ import annotations

from datetime import datetime, timezone

from app import CreditLedger, User, app, db, ensure_schema, maybe_grant_referral_bonus_for_plus
from services.growth import REFERRAL_BONUS_CENTS


def _user(email: str, *, plan: str = "free", referred_by: int | None = None) -> User:
    u = User(
        email=email,
        name="T",
        plan=plan,
        credit_balance_cents=0,
        password_hash="x",
        email_verified_at=datetime.now(timezone.utc),
        referred_by=referred_by,
        referral_code=email.split("@")[0][:10],
    )
    u.set_password("SecurePass1!")
    db.session.add(u)
    db.session.commit()
    return u


def test_referral_bonus_only_on_plus_not_verify_or_business():
    with app.app_context():
        ensure_schema()
        referrer = _user("ref-owner@example.com")
        invitee = _user("invitee@example.com", referred_by=referrer.id)

        assert maybe_grant_referral_bonus_for_plus(invitee) is False
        db.session.refresh(referrer)
        assert int(referrer.credit_balance_cents) == 0

        invitee.plan = "business"
        db.session.commit()
        assert maybe_grant_referral_bonus_for_plus(invitee) is False
        db.session.refresh(referrer)
        assert int(referrer.credit_balance_cents) == 0

        invitee.plan = "plus"
        db.session.commit()
        assert maybe_grant_referral_bonus_for_plus(invitee) is True
        db.session.commit()
        db.session.refresh(referrer)
        assert int(referrer.credit_balance_cents) == REFERRAL_BONUS_CENTS
        assert (
            CreditLedger.query.filter_by(stripe_payment_intent=f"referral:{invitee.id}").count()
            == 1
        )

        # Idempotent
        assert maybe_grant_referral_bonus_for_plus(invitee) is False
        db.session.refresh(referrer)
        assert int(referrer.credit_balance_cents) == REFERRAL_BONUS_CENTS


def test_verify_email_does_not_grant_referral(monkeypatch):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    monkeypatch.setattr("app.mail_configured", lambda: True)

    with app.app_context():
        ensure_schema()
        referrer = _user("ref2@example.com")
        invitee = _user("invitee2@example.com", referred_by=referrer.id)
        invitee.email_verified_at = None
        raw = invitee.issue_verify_token(hours=48)
        db.session.commit()
        ref_id = referrer.id
        inv_id = invitee.id

    with app.test_client() as client:
        resp = client.get(f"/verify-email/{raw}", follow_redirects=False)
        assert resp.status_code in (302, 303)

    with app.app_context():
        referrer = db.session.get(User, ref_id)
        invitee = db.session.get(User, inv_id)
        assert invitee.email_verified_at is not None
        assert int(referrer.credit_balance_cents) == 0
        assert (
            CreditLedger.query.filter_by(stripe_payment_intent=f"referral:{inv_id}").count()
            == 0
        )
        assert (invitee.plan or "").lower() == "free"
