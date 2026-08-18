"""Alert webhook secrets sealed at rest (Fernet)."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.alerts import dispatch_alerts, sign_payload
from services.webhook_crypto import (
    is_sealed_webhook_secret,
    reveal_webhook_secret,
    reset_webhook_crypto_for_tests,
    seal_webhook_secret,
    store_webhook_secret,
    upgrade_webhook_secret_if_plaintext,
    webhook_secret_is_set,
)


@pytest.fixture(autouse=True)
def _crypto_env(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-flask-secret-for-webhook-crypto")
    reset_webhook_crypto_for_tests()
    yield
    reset_webhook_crypto_for_tests()


def test_seal_roundtrip_and_prefix():
    sealed = seal_webhook_secret("super-secret-value")
    assert is_sealed_webhook_secret(sealed)
    assert "super-secret-value" not in sealed
    assert reveal_webhook_secret(sealed) == "super-secret-value"


def test_store_clear_tokens():
    assert store_webhook_secret("-") is None
    assert store_webhook_secret("clear") is None
    assert store_webhook_secret("DELETE") is None
    assert store_webhook_secret("  ") is None
    sealed = store_webhook_secret("abc123")
    assert is_sealed_webhook_secret(sealed)


def test_reveal_legacy_plaintext():
    assert reveal_webhook_secret("legacy-plain") == "legacy-plain"
    assert webhook_secret_is_set("legacy-plain") is True
    assert webhook_secret_is_set("") is False


def test_upgrade_plaintext_row():
    user = SimpleNamespace(id=1, webhook_secret="legacy-plain")
    commits: list[int] = []

    class Sess:
        def commit(self):
            commits.append(1)

        def rollback(self):
            pass

    assert upgrade_webhook_secret_if_plaintext(user, Sess()) is True
    assert is_sealed_webhook_secret(user.webhook_secret)
    assert reveal_webhook_secret(user.webhook_secret) == "legacy-plain"
    assert commits == [1]
    # Second pass is no-op.
    assert upgrade_webhook_secret_if_plaintext(user, Sess()) is False


def test_dispatch_signs_with_revealed_secret(monkeypatch):
    sealed = seal_webhook_secret("hook-sekrit")
    user = SimpleNamespace(
        id=9,
        email="a@example.com",
        plan="plus",
        is_admin=False,
        is_pro=True,
        alert_email_enabled=False,
        webhook_url="https://hooks.example.com/h",
        webhook_secret=sealed,
    )
    site = SimpleNamespace(id=1, url="https://ex.com/", domain="ex.com")
    findings = [
        {
            "title": "Alert: regressione score",
            "severity": "critical",
            "detail": "down",
            "category": "diff",
        }
    ]

    captured: dict = {}

    def _fake_deliver(*, url, secret, payload, timeout=12):
        captured["secret"] = secret
        captured["url"] = url
        return {"ok": True, "status": 204}

    monkeypatch.setattr("services.alerts.deliver_webhook", _fake_deliver)
    monkeypatch.setattr("services.alerts.mail_configured", lambda: False)

    out = dispatch_alerts(user=user, site=site, findings=findings)
    assert out["webhook"]["ok"] is True
    assert captured["secret"] == "hook-sekrit"
    assert sign_payload("hook-sekrit", b"{}")  # smoke


def test_dispatch_upgrades_legacy_plaintext(monkeypatch):
    user = SimpleNamespace(
        id=10,
        email="b@example.com",
        plan="plus",
        is_admin=False,
        is_pro=True,
        alert_email_enabled=False,
        webhook_url="https://hooks.example.com/h",
        webhook_secret="legacy-sekrit",
    )
    site = SimpleNamespace(id=2, url="https://ex.com/", domain="ex.com")
    findings = [
        {
            "title": "Alert: regressione score",
            "severity": "warn",
            "detail": "x",
            "category": "diff",
        }
    ]
    session = MagicMock()

    monkeypatch.setattr(
        "services.alerts.deliver_webhook",
        lambda **kw: {"ok": True, "status": 200},
    )
    monkeypatch.setattr("services.alerts.mail_configured", lambda: False)

    dispatch_alerts(
        user=user, site=site, findings=findings, db_session=session
    )
    assert is_sealed_webhook_secret(user.webhook_secret)
    assert reveal_webhook_secret(user.webhook_secret) == "legacy-sekrit"
    session.commit.assert_called()
