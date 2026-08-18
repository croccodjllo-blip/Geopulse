"""Plus checkout price €19.99 excl. tax on public pricing surfaces."""

from __future__ import annotations

from app import PLUS_LIST_EUR, PLUS_MONTHLY_EUR, PLUS_YEARLY_EUR, app


def test_plus_price_constants():
    assert PLUS_LIST_EUR == 19.99
    assert PLUS_MONTHLY_EUR == 19.99
    assert PLUS_YEARLY_EUR == 191.90


def test_pricing_shows_plus_1999(monkeypatch):
    monkeypatch.setenv("PAYMENTS_PROVIDER", "paddle")
    monkeypatch.setenv("PADDLE_API_KEY", "test")
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_01m0a1m24m4qbsv548y2pyws2x")
    client = app.test_client()
    html = client.get("/prezzi").get_data(as_text=True)
    assert "19,99" in html
    assert "14,99" not in html
    assert "Tasse escluse" in html
    free_block = html.split('id="free"', 1)[1].split('id="plus"', 1)[0]
    assert "Tasse escluse" not in free_block
    # No strikethrough offer when list == monthly.
    assert "price-offer__list" not in html


def test_landing_shows_plus_1999():
    html = app.test_client().get("/").get_data(as_text=True)
    assert "19,99" in html
    assert "14,99" not in html
    assert "Tasse escluse" in html
