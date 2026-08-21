"""Google Search Console OAuth connect tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app import User, app, db, ensure_schema
from services import gsc as gsc_mod
from services.gsc import (
    apply_token_payload,
    build_authorization_url,
    gsc_status,
    persist_connection_from_code,
    user_has_gsc_connection,
)
from services.webhook_crypto import reset_webhook_crypto_for_tests


@pytest.fixture(autouse=True)
def _crypto(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key-for-gsc-oauth-xxxxxxxx")
    reset_webhook_crypto_for_tests()
    yield
    reset_webhook_crypto_for_tests()


def test_gsc_available_when_oauth_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    gsc_mod.reload_gsc_env()
    with app.test_request_context("/"):
        status = gsc_status(user=None)
    assert status["available"] is True
    assert status["connected"] is False
    assert status["reason"]


def test_gsc_unavailable_without_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    gsc_mod.reload_gsc_env()
    with app.test_request_context("/"):
        status = gsc_status()
    assert status["available"] is False
    assert status["connected"] is False


def test_authorization_url_contains_offline_consent(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    gsc_mod.reload_gsc_env()
    with app.test_request_context("/"):
        url = build_authorization_url(
            state="abc",
            redirect_uri="https://centropic.ai/dashboard/gsc/callback",
        )
    assert "accounts.google.com" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "webmasters.readonly" in url
    assert "state=abc" in url


def test_apply_token_payload_seals_and_status_connected(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    gsc_mod.reload_gsc_env()
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"gsc-{uuid4().hex}@example.com",
            name="GSC",
            plan="plus",
            credit_balance_cents=1000,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        apply_token_payload(
            user,
            {
                "access_token": "ya29.access-test",
                "refresh_token": "1//refresh-test",
                "expires_in": 3600,
            },
        )
        user.gsc_account_email = "owner@example.com"
        db.session.commit()
        assert user_has_gsc_connection(user)
        assert str(user.gsc_refresh_token or "").startswith("enc:v1:")
        with app.test_request_context("/"):
            status = gsc_status(user)
        assert status["available"] is True
        assert status["connected"] is True
        assert status["email"] == "owner@example.com"


def test_connect_route_requires_plus(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    gsc_mod.reload_gsc_env()
    with app.app_context():
        ensure_schema()
        app.config["WTF_CSRF_ENABLED"] = False
        user = User(
            email=f"gsc-free-{uuid4().hex}@example.com",
            name="Free",
            plan="free",
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)
        resp = client.post("/dashboard/gsc/connect", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "/prezzi" in (resp.headers.get("Location") or "")


def test_connect_route_redirects_to_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    gsc_mod.reload_gsc_env()
    with app.app_context():
        ensure_schema()
        app.config["WTF_CSRF_ENABLED"] = False
        user = User(
            email=f"gsc-plus-{uuid4().hex}@example.com",
            name="Plus",
            plan="plus",
            credit_balance_cents=5000,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)
        resp = client.post("/dashboard/gsc/connect", follow_redirects=False)
        assert resp.status_code in (302, 303)
        loc = resp.headers.get("Location") or ""
        assert "accounts.google.com" in loc
        with client.session_transaction() as sess:
            assert sess.get("gsc_oauth_state")


def test_callback_rejects_bad_state(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    gsc_mod.reload_gsc_env()
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"gsc-cb-{uuid4().hex}@example.com",
            name="CB",
            plan="plus",
            credit_balance_cents=5000,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["session_version"] = int(getattr(user, "session_version", 0) or 0)
            sess["gsc_oauth_state"] = "expected-state"
        resp = client.get(
            "/dashboard/gsc/callback?code=x&state=wrong",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        assert "impostazioni" in (resp.headers.get("Location") or "")


def test_persist_connection_from_code_mocks_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    gsc_mod.reload_gsc_env()

    def _exchange(code, redirect_uri=None):
        return {
            "access_token": "ya29.mock",
            "refresh_token": "1//mock-refresh",
            "expires_in": 3600,
        }

    monkeypatch.setattr(gsc_mod, "exchange_code_for_tokens", _exchange)
    monkeypatch.setattr(gsc_mod, "fetch_account_email", lambda tok: "gsc@example.com")
    monkeypatch.setattr(
        gsc_mod, "list_gsc_sites", lambda tok: ["sc-domain:example.com"]
    )

    with app.app_context():
        ensure_schema()
        user = User(
            email=f"gsc-persist-{uuid4().hex}@example.com",
            name="P",
            plan="plus",
            credit_balance_cents=5000,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        info = persist_connection_from_code(
            user, "auth-code", db_session=db.session
        )
        assert info["email"] == "gsc@example.com"
        assert info["sites"] == ["sc-domain:example.com"]
        assert user_has_gsc_connection(user)
        with app.test_request_context("/"):
            st = gsc_status(user)
        assert st["connected"] is True
