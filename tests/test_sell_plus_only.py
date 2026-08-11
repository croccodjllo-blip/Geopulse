"""Plus-only GTM gate: Business checkout stays closed by default."""

from __future__ import annotations

from services.paddle_billing import paddle_business_enabled, sell_plus_only


def test_sell_plus_only_defaults_on(monkeypatch):
    monkeypatch.delenv("SELL_PLUS_ONLY", raising=False)
    monkeypatch.setenv("PADDLE_PRICE_BUSINESS_MONTHLY", "pri_business")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    # Module constants are loaded at import; patch helpers' env reads via reload path.
    assert sell_plus_only() is True


def test_paddle_business_disabled_when_sell_plus_only(monkeypatch):
    monkeypatch.setenv("SELL_PLUS_ONLY", "1")
    monkeypatch.setenv("PADDLE_PRICE_BUSINESS_MONTHLY", "pri_business")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setenv("PADDLE_CLIENT_TOKEN", "test_client")
    import services.paddle_billing as pb

    monkeypatch.setattr(pb, "PADDLE_PRICE_BUSINESS", "pri_business")
    monkeypatch.setattr(pb, "PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setattr(pb, "PADDLE_CLIENT_TOKEN", "test_client")
    assert paddle_business_enabled() is False


def test_paddle_business_can_open_when_sell_plus_only_off(monkeypatch):
    monkeypatch.setenv("SELL_PLUS_ONLY", "0")
    import services.paddle_billing as pb

    monkeypatch.setattr(pb, "PADDLE_PRICE_BUSINESS", "pri_business")
    monkeypatch.setattr(pb, "PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setattr(pb, "PADDLE_CLIENT_TOKEN", "test_client")
    assert sell_plus_only() is False
    assert paddle_business_enabled() is True
