"""Plus list €19.99 with offer €14.99 on public pricing surfaces."""

from __future__ import annotations

from app import PLUS_LIST_EUR, PLUS_MONTHLY_EUR, app


def test_plus_offer_constants():
    assert PLUS_LIST_EUR == 19.99
    assert PLUS_MONTHLY_EUR == 14.99


def test_pricing_shows_list_and_offer(monkeypatch):
    monkeypatch.setenv("PAYMENTS_PROVIDER", "paddle")
    monkeypatch.setenv("PADDLE_API_KEY", "test")
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_test_monthly")
    client = app.test_client()
    html = client.get("/prezzi").get_data(as_text=True)
    assert "19,99" in html
    assert "14,99" in html
    assert "price-offer__list" in html
    assert "price-offer__row" in html
    assert "price-offer__amount" in html
    assert "<s>19,99" in html or "<s>19,99&nbsp;€</s>" in html
    # Offer amount uses <strong>, not a nested span that inherits /mese sizing.
    assert 'class="price-offer__now"' not in html


def test_landing_shows_plus_offer():
    html = app.test_client().get("/").get_data(as_text=True)
    assert "19,99" in html
    assert "14,99" in html
    assert "price-offer__list" in html
