"""Paddle billing helpers and webhook signature."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from services import paddle_billing as pb
from services.billing import payments_enabled, payments_provider, stripe_enabled


def test_verify_webhook_signature_ok(monkeypatch):
    secret = "pdl_ntfsec_test"
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", secret)
    # Reload module constants would need re-import; pass secret explicitly.
    body = json.dumps({"event_type": "transaction.completed", "data": {"id": "txn_1"}})
    ts = str(int(time.time()))
    signed = f"{ts}:{body}".encode("utf-8")
    h1 = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    header = f"ts={ts};h1={h1}"
    assert pb.verify_webhook_signature(body.encode("utf-8"), header, secret=secret)


def test_verify_webhook_signature_bad(monkeypatch):
    body = b'{"event_type":"x"}'
    assert not pb.verify_webhook_signature(
        body, "ts=1;h1=deadbeef", secret="secret"
    )


def test_extract_user_id():
    assert pb.extract_user_id({"centropic_user_id": "42"}) == 42
    assert pb.extract_user_id({"geopulse_user_id": "7"}) == 7
    assert pb.extract_user_id({}) is None


def test_plan_from_paddle_status():
    from datetime import datetime, timedelta, timezone

    assert pb.plan_from_paddle_subscription_status("active") == "plus"
    assert pb.plan_from_paddle_subscription_status("canceled") == "free"
    # past_due without timestamp → fail closed
    assert pb.plan_from_paddle_subscription_status("past_due") == "free"
    now = datetime(2026, 7, 30, tzinfo=timezone.utc)
    assert (
        pb.plan_from_paddle_subscription_status(
            "past_due", past_due_at=now - timedelta(days=1), now=now
        )
        == "plus"
    )
    assert (
        pb.plan_from_paddle_subscription_status(
            "past_due", past_due_at=now - timedelta(days=10), now=now
        )
        == "free"
    )


def test_payments_provider_prefers_paddle(monkeypatch):
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_plus")
    monkeypatch.setenv("PADDLE_CLIENT_TOKEN", "test_token")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_PLUS_MONTHLY", raising=False)
    # Re-bind module-level constants used by paddle_enabled
    monkeypatch.setattr(pb, "PADDLE_PRICE_PLUS", "pri_plus")
    monkeypatch.setattr(pb, "PADDLE_CLIENT_TOKEN", "test_token")
    monkeypatch.setattr(pb, "PADDLE_API_KEY", "")
    assert pb.paddle_enabled()
    assert payments_provider() == "paddle"
    assert payments_enabled()


def test_client_config_shape(monkeypatch):
    monkeypatch.setattr(pb, "PADDLE_PRICE_PLUS", "pri_plus")
    monkeypatch.setattr(pb, "PADDLE_CLIENT_TOKEN", "test_token")
    monkeypatch.setattr(pb, "PADDLE_API_KEY", "")
    monkeypatch.setattr(pb, "PADDLE_ENV", "sandbox")
    cfg = pb.client_config()
    assert cfg["enabled"] is True
    assert cfg["overlay"] is True
    assert cfg["environment"] == "sandbox"
    assert cfg["pricePlus"] == "pri_plus"


def test_topup_price_map(monkeypatch):
    monkeypatch.setenv("PADDLE_PRICE_TOPUP_2000", "pri_2000")
    assert pb.paddle_topup_price_id(2000) == "pri_2000"
    assert pb.paddle_topup_price_id(123) is None


def test_transaction_grants_plus_ignores_custom_data(monkeypatch):
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_plus_real")
    # Attacker sets custom_data.product=plus on a cheap one-time item.
    data = {
        "custom_data": {"product": "plus", "centropic_user_id": "1"},
        "items": [{"price_id": "pri_topup_1000", "price": {"id": "pri_topup_1000"}}],
    }
    assert pb.transaction_grants_plus(data) is False


def test_transaction_grants_plus_by_price_id(monkeypatch):
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_plus_real")
    data = {
        "subscription_id": "sub_1",
        "custom_data": {},
        "items": [{"price": {"id": "pri_plus_real", "billing_cycle": {"interval": "month"}}}],
    }
    assert pb.transaction_grants_plus(data) is True


def test_topup_cents_from_price_id_not_custom_data(monkeypatch):
    monkeypatch.setenv("PADDLE_PRICE_TOPUP_1000", "pri_1000")
    monkeypatch.setenv("PADDLE_PRICE_TOPUP_5000", "pri_5000")
    data = {
        "custom_data": {"product": "topup", "topup_cents": "5000"},
        "items": [{"price_id": "pri_1000"}],
        "details": {"totals": {"grand_total": "1000"}},
    }
    assert pb.topup_cents_for_transaction(data) == 1000


def test_transaction_gross_cents_no_custom_data_fallback():
    data = {
        "custom_data": {"topup_cents": "10000"},
        "details": {"totals": {}},
    }
    assert pb.transaction_gross_cents(data) is None
    data2 = {"details": {"totals": {"grand_total": "500"}}}
    assert pb.transaction_gross_cents(data2) == 500
