"""P1 audit fixes: atomic reclaim seize + SMTP-down register gate."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-audit-p1")

from app import AnalysisJob as RealAnalysisJob
from app import User, app, ensure_schema
from services.jobs import _try_begin_reclaim


def _holder(update_result: int):
    class _FakeQuery:
        def filter(self, *a, **k):
            return self

        def update(self, fields, synchronize_session=False):
            self.fields = fields
            return update_result

    q = _FakeQuery()

    class _Holder:
        query = q
        __mapper__ = object()
        id = RealAnalysisJob.id
        status = RealAnalysisJob.status
        lease_token = RealAnalysisJob.lease_token
        heartbeat_at = RealAnalysisJob.heartbeat_at
        started_at = RealAnalysisJob.started_at

    return _Holder, q


def test_try_begin_reclaim_skips_when_update_loses_race():
    """Live heartbeat wins: conditional UPDATE returns 0 → skip reclaim."""
    job = SimpleNamespace(id=42, lease_token="alive", status="running")
    Holder, _q = _holder(0)
    db_session = MagicMock()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert (
        _try_begin_reclaim(
            db_session,
            Holder,
            job,
            expected_lease="alive",
            cutoff=cutoff,
        )
        is False
    )
    db_session.rollback.assert_called()


def test_try_begin_reclaim_wins_and_sets_reclaim_lease():
    job = SimpleNamespace(id=43, lease_token="dead", status="running")
    Holder, q = _holder(1)
    ok = _try_begin_reclaim(
        MagicMock(),
        Holder,
        job,
        expected_lease="dead",
        cutoff=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    assert ok is True
    assert str(job.lease_token).startswith("reclaim:")
    assert str(q.fields["lease_token"]).startswith("reclaim:")


def test_register_refuses_when_mail_down_outside_dev(monkeypatch):
    """Production-like: no SMTP/Resend → no auto-verify hatch."""
    app.config["TESTING"] = False
    monkeypatch.setenv("FLASK_DEBUG", "0")
    monkeypatch.setattr("app.mail_configured", lambda: False)
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        ensure_schema()
    client = app.test_client()
    email = "p1-nomail@example.com"
    resp = client.post(
        "/register",
        data={
            "name": "No Mail",
            "email": email,
            "password": "SecurePass1!",
            "confirm": "SecurePass1!",
            "accept_terms": "y",
            "phone_prefix": "+39",
            "phone": "3331234567",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200  # form re-rendered with error
    html = resp.get_data(as_text=True)
    assert "non disponibile" in html.lower() or "email non attivo" in html.lower()
    with app.app_context():
        assert User.query.filter_by(email=email).first() is None
    app.config["TESTING"] = True
    monkeypatch.setenv("FLASK_DEBUG", "1")


def test_register_dev_hatch_still_works_when_testing(monkeypatch):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    monkeypatch.setattr("app.mail_configured", lambda: False)
    monkeypatch.setattr("app.limiter.allow", lambda *a, **k: True)
    with app.app_context():
        ensure_schema()
    client = app.test_client()
    email = "p1-devhatch@example.com"
    resp = client.post(
        "/register",
        data={
            "name": "Dev Hatch",
            "email": email,
            "password": "SecurePass1!",
            "confirm": "SecurePass1!",
            "accept_terms": "y",
            "phone_prefix": "+39",
            "phone": "3339998877",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        assert u is not None
        assert u.email_verified_at is not None
