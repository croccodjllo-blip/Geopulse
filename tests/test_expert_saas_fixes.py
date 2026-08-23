"""Regression suite for expert SaaS critical fixes."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import (
    PRIVILEGE_ROLES,
    User,
    active_analyze_job_for_url,
    admin_set_plan,
    app,
    clear_privilege_role,
    db,
    ensure_schema,
)
from services.gsc import gsc_status
from services.js_crawl import _chromium_dns_pin_args
from services.paddle_billing import assert_paddle_env_matches_site
from services.sov_budget import sov_budget_status
from services.usage_billing import is_unlimited_user


def test_gsc_available_with_credentials_when_oauth_shipped(monkeypatch):
    """Credentials alone used to hide the connector; OAuth connect is now live."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    import services.gsc as gsc

    gsc.reload_gsc_env()
    with app.test_request_context("/"):
        status = gsc.gsc_status()
    assert status["available"] is True
    assert status.get("connected") is False


def test_sov_budget_default_is_capped(monkeypatch):
    monkeypatch.delenv("SOV_DAILY_BUDGET_CENTS", raising=False)
    status = sov_budget_status(object(), 10)
    assert status["unlimited"] is False
    assert status["budget_cents"] == 5000


def test_paddle_sandbox_blocked_on_prod_url():
    with pytest.raises(RuntimeError, match="PADDLE_ENV=sandbox"):
        assert_paddle_env_matches_site(
            public_site_url="https://centropic.ai",
            flask_debug=False,
            allow_sandbox_on_prod=False,
        )


def test_paddle_sandbox_allowed_in_debug():
    assert_paddle_env_matches_site(
        public_site_url="https://centropic.ai",
        flask_debug=True,
        allow_sandbox_on_prod=False,
    )


def test_clear_privilege_role_strips_internal():
    user = SimpleNamespace(role="internal", plan="free")
    clear_privilege_role(user)
    assert user.role is None
    assert "internal" in PRIVILEGE_ROLES


def test_admin_set_plan_clears_internal(monkeypatch):
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"internal-{uuid4().hex}@example.com",
            name="Internal",
            plan="free",
            role="internal",
            credit_balance_cents=0,
        )
        user.set_password("x" * 12)
        db.session.add(user)
        db.session.commit()
        assert is_unlimited_user(user) is True

        # Simulate demotion path without HTTP (direct helper + commit).
        user.plan = "free"
        clear_privilege_role(user)
        db.session.commit()
        db.session.refresh(user)
        assert user.role is None
        assert is_unlimited_user(user) is False


def test_js_crawl_dns_pin_args_maps_hostname(monkeypatch):
    monkeypatch.setattr(
        "services.js_crawl.resolve_public_ips",
        lambda host: ["203.0.113.10"],
    )
    args = _chromium_dns_pin_args("https://example.com/path")
    assert any("MAP example.com 203.0.113.10" in a for a in args)


def test_paddle_plus_grant_no_user_returns_500(monkeypatch):
    secret = "pdl_ntfsec_plus_nouser"
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", secret)
    from services import paddle_billing as pb

    body_obj = {
        "event_type": "transaction.completed",
        "data": {
            "id": f"txn_plus_nouser_{uuid4().hex[:8]}",
            "status": "completed",
            "customer_id": "ctm_missing_plus",
            "custom_data": {},
            "items": [{"price": {"id": "pri_plus_x"}, "quantity": 1}],
        },
    }
    body = json.dumps(body_obj).encode("utf-8")
    ts = str(int(time.time()))
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    header = f"ts={ts};h1={h1}"

    monkeypatch.setattr(pb, "transaction_grants_plus", lambda data: True)
    monkeypatch.setattr(pb, "transaction_grants_business", lambda data: False)
    monkeypatch.setattr("app.transaction_grants_plus", lambda data: True)
    monkeypatch.setattr("app.transaction_grants_business", lambda data: False)

    with app.app_context():
        ensure_schema()
        client = app.test_client()
        resp = client.post(
            "/billing/paddle-webhook",
            data=body,
            headers={"Paddle-Signature": header, "Content-Type": "application/json"},
        )
        assert resp.status_code == 500
        assert resp.get_json().get("error") == "no_user"
