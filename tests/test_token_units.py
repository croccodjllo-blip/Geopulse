"""GEO token display helpers (1 token = 1 EUR cent)."""

from __future__ import annotations

from services.token_units import (
    GEO_TOKEN_EUR_CENTS,
    GEO_TOKENS_PER_EURO,
    cents_to_tokens,
    format_token_amount,
    format_tokens_short,
    tokens_to_cents,
)


def test_one_to_one_with_cents():
    assert GEO_TOKEN_EUR_CENTS == 1
    assert GEO_TOKENS_PER_EURO == 100
    assert cents_to_tokens(1250) == 1250
    assert tokens_to_cents(1000) == 1000


def test_format_token_amount_italian_thousands():
    assert format_token_amount(0) == "0 token"
    assert format_token_amount(1) == "1 token"
    assert format_token_amount(1250) == "1.250 token"
    assert format_token_amount(-42, signed=True) == "−42 token"
    assert format_token_amount(100, signed=True) == "+100 token"
    assert format_token_amount(1000, with_unit=False) == "1.000"


def test_format_tokens_short():
    assert format_tokens_short(0) == "0 tok"
    assert format_tokens_short(1250) == "1.250 tok"
