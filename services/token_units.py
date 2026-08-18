"""GEO token display helpers.

Internal ledger stays in EUR cents. Product unit for users:

  1 GEO token == 10 EUR cents == €0.10
  10 token == €1.00
  100 token == €10.00 (base pack rate)

Subscriptions:
  Plus      → ``PLUS_MONTHLY_TOKENS`` (100) each billing cycle
  Business  → ``BUSINESS_MONTHLY_TOKENS`` (400) each billing cycle

The €50 pack grants a light bonus (550 token for €50 = €55 face value).
Top-ups are sold only to Plus / Business (and Admin) accounts.
"""

from __future__ import annotations


GEO_TOKEN_EUR_CENTS = 10
GEO_TOKENS_PER_EURO = 10
PLUS_MONTHLY_TOKENS = 100
PLUS_MONTHLY_CREDIT_CENTS = PLUS_MONTHLY_TOKENS * GEO_TOKEN_EUR_CENTS
BUSINESS_MONTHLY_TOKENS = 400
BUSINESS_MONTHLY_CREDIT_CENTS = BUSINESS_MONTHLY_TOKENS * GEO_TOKEN_EUR_CENTS


def cents_to_tokens(cents: int | None) -> float:
    """Convert ledger cents to GEO tokens."""
    return float(int(cents or 0)) / float(GEO_TOKEN_EUR_CENTS)


def tokens_to_cents(tokens: int | float | None) -> int:
    return int(round(float(tokens or 0) * GEO_TOKEN_EUR_CENTS))


def _format_token_number(tokens: float) -> str:
    """Italian-style number: thousands ``.``, decimal ``,`` when needed."""
    if abs(tokens - round(tokens)) < 1e-9:
        n = int(round(tokens))
        return f"{n:,}".replace(",", ".")
    # Keep one decimal for fractional analysis costs.
    return f"{tokens:.1f}".replace(".", ",")


def format_token_amount(
    cents: int | None, *, with_unit: bool = True, signed: bool = False
) -> str:
    """Human-readable token amount for UI from ledger cents."""
    raw = int(cents or 0)
    tokens = cents_to_tokens(abs(raw))
    sign = ""
    if signed and raw > 0:
        sign = "+"
    elif raw < 0:
        sign = "−"
    body = _format_token_number(tokens)
    if with_unit:
        return f"{sign}{body} token"
    return f"{sign}{body}"


def format_tokens_short(cents: int | None) -> str:
    """Compact sidebar form, e.g. ``125 tok`` or ``0,3 tok``."""
    body = _format_token_number(cents_to_tokens(cents))
    return f"{body} tok"
