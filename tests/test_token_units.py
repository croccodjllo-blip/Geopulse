"""GEO token display helpers (1 token = €0.10 = 10 cents)."""

from __future__ import annotations

from services.token_units import (
    BUSINESS_MONTHLY_CREDIT_CENTS,
    BUSINESS_MONTHLY_TOKENS,
    GEO_TOKEN_EUR_CENTS,
    GEO_TOKENS_PER_EURO,
    PLUS_MONTHLY_CREDIT_CENTS,
    PLUS_MONTHLY_TOKENS,
    cents_to_tokens,
    format_token_amount,
    format_tokens_short,
    tokens_to_cents,
)


def test_one_token_is_ten_cents():
    assert GEO_TOKEN_EUR_CENTS == 10
    assert GEO_TOKENS_PER_EURO == 10
    assert PLUS_MONTHLY_TOKENS == 100
    assert PLUS_MONTHLY_CREDIT_CENTS == 1000
    assert BUSINESS_MONTHLY_TOKENS == 400
    assert BUSINESS_MONTHLY_CREDIT_CENTS == 4000
    assert cents_to_tokens(1000) == 100.0
    assert tokens_to_cents(100) == 1000
    assert tokens_to_cents(600) == 6000


def test_format_token_amount_whole_and_fractional():
    assert format_token_amount(0) == "0 token"
    assert format_token_amount(1000) == "100 token"
    assert format_token_amount(3) == "0,3 token"
    assert format_token_amount(-20, signed=True) == "−2 token"
    assert format_token_amount(1000, signed=True) == "+100 token"
    assert format_token_amount(1000, with_unit=False) == "100"


def test_format_tokens_short():
    assert format_tokens_short(0) == "0 tok"
    assert format_tokens_short(1250) == "125 tok"
    assert format_tokens_short(3) == "0,3 tok"
